"""
Modèle analytique (gratuit) de la latence et des ressources d'une configuration.

Il ne remplace pas Catapult : il sert à CLASSER les candidats (gain de cycles par ressource) et à ÉCARTER
ceux qui ne peuvent rien gagner (ex. 5 MAC/cycle alors que la RAM d'entrée ne fournit que 2 lectures
par cycle). Après chaque synthèse, il est recalé : facteur mesuré / prédit par bloc et par mode
(pipeliné ou non), décalage mesuré - prédit pour chaque ressource.

Ordres de grandeur (cnn.v1, aucune directive) : 4 c-steps par itération de MAC_N, + 1 par itération de
MAC_M -> 4,24 cycles par MAC ; ReLU 3 cycles par valeur ; max-pool 27 cycles par sortie (9 lectures x 3).
MAC pipelinées (CONV_CO à II, boucles aplaties) : une itération de la boucle aplatie par II cycles, soit
    sorties x ceil(C_IN / ci) x K x ceil(K / un) x II        (un, ci : déroulages de MAC_N, MAC_CI)
vérifié à l'école (run 20261125-164257) : layer2 x2 -> 4608 x 64 x 5 x 3 = 4 423 680 (Catapult : 4 423 685).
Le II réel ne descend pas sous lectures de la carte d'entrée par itération / lectures possibles par cycle.
Performance (objectif « perf ») : J = latence + débit, débit = bloc le plus lent (les blocs se recouvrent).
"""

from __future__ import annotations

import math
import re

from . import paths
from .space import BLOCKS, CONV, PAR_SPLIT, Config, Knobs

# Calcul du réseau (noyau 5x5)
MACS = {"layer1": 24 * 24 * 64 * 3 * 25, "layer2": 12 * 12 * 32 * 64 * 25,
        "layer3": 6 * 6 * 20 * 32 * 25, "dense": 180 * 10}
CONV_OUT = {"layer1": 24 * 24 * 64, "layer2": 12 * 12 * 32, "layer3": 6 * 6 * 20}
POOL_OUT = {"layer1": 12 * 12 * 64, "layer2": 6 * 6 * 32, "layer3": 3 * 3 * 20}
C_IN = {"layer1": 3, "layer2": 64, "layer3": 32}
K = 5


def ii_min(k: Knobs) -> int:
    """II atteignable au mieux : lectures de la carte d'entrée par itération / lectures possibles par cycle."""
    un, ci = PAR_SPLIT[k.par]
    return max(k.ii, math.ceil(un * ci / k.in_ports()))


def perf(blocks: dict, goal: str) -> float:
    """Critère à minimiser : latence (objectif cost) ou latence + débit (objectif perf)."""
    lat = sum(blocks.values())
    return lat + max(blocks.values()) if goal == "perf" else lat

CYCLES_PER_MAC_SEQ = 4.24
FILL = 30                           # remplissage d'un pipeline (cycles)

# Formes d'un RAMB18 (profondeur x largeur) : une mémoire prend la moins coûteuse
BRAM18_SHAPES = ((16384, 1), (8192, 2), (4096, 4), (2048, 9), (1024, 18), (512, 36))


def bram18(depth: int, width: int, banks: int = 1) -> int:
    d = math.ceil(depth / banks)
    return banks * min(math.ceil(d / sd) * math.ceil(width / sw) for sd, sw in BRAM18_SHAPES)


def read_widths() -> dict:
    """Largeur W de chaque format de cpp/config.hpp : {'IN': 15, 'K1': 12, ...}."""
    text = (paths.CPP / "config.hpp").read_text()
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"#define\s+(\w+)_W\s+(-?\d+)", text)}


class Model:
    def __init__(self, limits):
        self.limits = limits
        w = read_widths()
        self.width = w
        self.lat_factor = {}        # (bloc, pipeliné ?) -> mesuré / prédit
        self.offset = {"bram": 0.0, "dsp": 0.0, "lut": 0.0}

    # ---------------- latence ----------------
    def raw_block_latency(self, block: str, k: Knobs) -> float:
        if block == "dense":
            return MACS["dense"] * (1 if k.pipe else CYCLES_PER_MAC_SEQ) + FILL
        if k.pipe:
            un, ci = PAR_SPLIT[k.par]
            iters = CONV_OUT[block] * math.ceil(C_IN[block] / ci) * K * math.ceil(K / un)
            mac = iters * ii_min(k) + FILL
        else:
            mac = MACS[block] * CYCLES_PER_MAC_SEQ / min(k.par, k.in_ports())
        relu = CONV_OUT[block] * (1 if k.pp else 3)
        pool = POOL_OUT[block] * (9 if k.pp else 27)
        return mac + relu + pool

    def block_latency(self, block: str, k: Knobs) -> float:
        return self.raw_block_latency(block, k) * self.lat_factor.get((block, k.pipe), 1.0)

    def blocks(self, cfg: Config) -> dict:
        return {b: self.block_latency(b, k) for b, k in cfg.blocks.items()}

    def latency(self, cfg: Config) -> float:
        return sum(self.blocks(cfg).values())

    # ---------------- ressources ----------------
    def raw_resources(self, cfg: Config) -> dict:
        w = self.width
        b = cfg.blocks
        # cartes (entrée de chaque bloc en in_banks() bancs), copies locales des canaux (pooled, x), ROM
        mem = [(1728, w["IN"], b["layer1"].in_banks()), (36864, w["CONV1"], 1), (4608, w["CONV2"], 1),
               (720, w["CONV3"], 1), (9216, w["POOL1"], 1), (9216, w["POOL1"], b["layer2"].in_banks()),
               (1152, w["POOL2"], 1), (1152, w["POOL2"], b["layer3"].in_banks()),
               (4800, w["K1"], b["layer1"].par), (51200, w["K2"], b["layer2"].par),
               (16000, w["K3"], b["layer3"].par), (1800, w["FCK"], 1)]
        bram = sum(bram18(d, wd, bk) for d, wd, bk in mem)
        bram += cfg.chan * (bram18(9216, w["POOL1"]) + bram18(1152, w["POOL2"]))
        dsp = sum(b[x].par for x in CONV) + 1
        lut = 2500 + sum(400 * b[x].par + 300 * b[x].pp + 500 * b[x].pipe for x in CONV) + 300 * b["dense"].pipe
        return {"bram": bram, "dsp": dsp, "lut": lut}

    def resources(self, cfg: Config) -> dict:
        r = self.raw_resources(cfg)
        return {k: max(0.0, v + self.offset[k]) for k, v in r.items()}

    def cost(self, cfg: Config) -> float:
        """Coût prédit (même échelle que Limits.cost : somme des fractions de budget)."""
        return self.limits.cost(self.resources(cfg))

    # ---------------- recalage sur un résultat Catapult ----------------
    def calibrate(self, cfg: Config, res: dict, reference: bool = False):
        for b, lat in (res.get("blocks") or {}).items():
            pred = self.raw_block_latency(b, cfg.blocks[b])
            if lat and pred:
                self.lat_factor[(b, cfg.blocks[b].pipe)] = lat / pred
        if reference:
            raw = self.raw_resources(cfg)
            for k in self.offset:
                if res.get(k) is not None:
                    self.offset[k] = res[k] - raw[k]
