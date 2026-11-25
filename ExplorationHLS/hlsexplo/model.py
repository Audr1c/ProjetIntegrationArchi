"""
Modèle analytique (gratuit) de la latence et des ressources d'une configuration.

Il ne remplace pas Catapult : il sert à CLASSER les candidats (gain de cycles par ressource) et à ÉCARTER
ceux qui ne peuvent rien gagner (ex. 5 MAC/cycle alors que la RAM d'entrée ne fournit que 2 lectures
par cycle). Après chaque synthèse, il est recalé : facteur mesuré / prédit par bloc et par mode
(pipeliné ou non), décalage mesuré - prédit pour chaque ressource.

Ordres de grandeur (cnn.v1, aucune directive) : 4 c-steps par itération de MAC_N, + 1 par itération de
MAC_M -> 4,24 cycles par MAC ; ReLU 3 cycles par valeur ; max-pool 27 cycles par sortie (9 lectures x 3).
"""

from __future__ import annotations

import math
import re

from . import paths
from .space import BLOCKS, CONV, Config, Knobs

# Calcul du réseau (noyau 5x5)
MACS = {"layer1": 24 * 24 * 64 * 3 * 25, "layer2": 12 * 12 * 32 * 64 * 25,
        "layer3": 6 * 6 * 20 * 32 * 25, "dense": 180 * 10}
CONV_OUT = {"layer1": 24 * 24 * 64, "layer2": 12 * 12 * 32, "layer3": 6 * 6 * 20}
POOL_OUT = {"layer1": 12 * 12 * 64, "layer2": 6 * 6 * 32, "layer3": 3 * 3 * 20}

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
        ports = 2 if k.dp else 1
        if k.pipe:
            ii = max(k.ii, math.ceil(k.par / ports))       # lectures de la carte d'entrée par cycle
            mac = MACS[block] / k.par * ii + FILL
        else:
            mac = MACS[block] * CYCLES_PER_MAC_SEQ / min(k.par, ports)
        relu = CONV_OUT[block] * (1 if k.pp else 3)
        pool = POOL_OUT[block] * (9 if k.pp else 27)
        return mac + relu + pool

    def block_latency(self, block: str, k: Knobs) -> float:
        return self.raw_block_latency(block, k) * self.lat_factor.get((block, k.pipe), 1.0)

    def latency(self, cfg: Config) -> float:
        return sum(self.block_latency(b, k) for b, k in cfg.blocks.items())

    # ---------------- ressources ----------------
    def raw_resources(self, cfg: Config) -> dict:
        w = self.width
        b = cfg.blocks
        mem = [(1728, w["IN"], 1), (36864, w["CONV1"], 1), (4608, w["CONV2"], 1), (720, w["CONV3"], 1),
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
