"""
Espace de recherche : réglages (« boutons ») de chaque bloc, échelle de montée, replis, et leur
traduction en directives Catapult.

Un bloc = une fonction #pragma hls_design de cpp/cnn.cpp (layer1, layer2, layer3, dense).
Réglages d'un bloc de convolution (classe Knobs) :
    pp    ReLU et max-pool pipelinés (II = 1 sur RELU et POOL_CO)
    pipe  MAC pipelinés : II sur CONV_CO. Catapult aplatit alors toutes les boucles internes
          (manuel, PIPELINE_INIT_INTERVAL, « Nested Loop Pipelining ») : une MAC démarre tous les II cycles
    ii    intervalle d'initiation du pipeline des MAC
    par   MAC en parallèle (PAR_SPLIT) : 2 = MAC_N déroulée par 2 (5 MAC en 3 cycles), 5 = MAC_N déroulée,
          10 = MAC_N déroulée + MAC_CI par 2. La ROM des poids est entrelacée en `par` bancs : les poids lus
          ensemble (n consécutifs, canaux d'entrée à 25 d'écart) tombent toujours dans des bancs différents
    dp    RAM double port (Xilinx BLOCK_DPRAM_RBW) pour la carte d'entrée et la carte de sortie du bloc
    xin   carte d'entrée découpée en bancs (INTERLEAVE 2 ou 5) : layer2/3 lisent la copie LOCALE `x` du canal
          (x = in.read() dans cnn.cpp ; un canal, lui, n'accepte pas INTERLEAVE), layer1 l'interface `image`.
          5 pixels consécutifs -> 5 bancs différents : 5 MAC/cycle à II = 1 ; avec dp, 10 lectures/cycle
Bloc dense : seul `pipe` compte (II = 1 sur FC_ROW).
Réglage global : chan = STAGE_REPLICATION des canaux pool1_chan et pool2_chan (1 = mémoire simple,
2 = ping-pong : les couches travaillent sur des images successives, mémoire doublée).
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, replace

BLOCKS = ("layer1", "layer2", "layer3", "dense")
CONV = ("layer1", "layer2", "layer3")
SHORT = {"layer1": "L1", "layer2": "L2", "layer3": "L3", "dense": "FC"}

# Tableaux de chaque bloc (noms de cpp/cnn.cpp)
ROM_OF = {"layer1": "ker1", "layer2": "ker2", "layer3": "ker3"}
OUT_MAP = {"layer1": "image2", "layer2": "image4", "layer3": "image6"}
IN_MAP = {"layer1": "image", "layer2": "x", "layer3": "x"}     # carte réellement lue par les MAC
PAR_SPLIT = {1: (1, 1), 2: (2, 1), 5: (5, 1), 10: (5, 2)}      # par -> (déroulage MAC_N, déroulage MAC_CI)
CHANNELS = ("pool1_chan", "pool2_chan")

RAM_DP = "Xilinx_RAMS.BLOCK_DPRAM_RBW"


# ============================================================
# Réglages
# ============================================================

@dataclass(frozen=True)
class Knobs:
    pp: bool = False
    pipe: bool = False
    ii: int = 1
    par: int = 1
    dp: bool = False
    xin: bool = False

    def in_banks(self) -> int:
        """Bancs de la carte d'entrée (1 si elle n'est pas découpée)."""
        return (2 if self.par == 2 else 5) if self.xin else 1

    def in_ports(self) -> int:
        """Lectures de la carte d'entrée possibles par cycle."""
        return self.in_banks() * (2 if self.dp else 1)

    def short(self, block: str) -> str:
        """Résumé lisible : « II1 ×2 DP pp », « — » si rien n'est réglé."""
        if block == "dense":
            return f"II{self.ii}" if self.pipe else "—"
        parts = []
        if self.pipe:
            parts.append(f"II{self.ii}")
        if self.par > 1:
            parts.append(f"×{self.par}")
        if self.dp:
            parts.append("DP")
        if self.xin:
            parts.append(f"E{self.in_banks()}")
        if self.pp:
            parts.append("pp")
        return " ".join(parts) or "—"


class Config:
    """Réglages de tous les blocs + canaux. Immuable : with_block() renvoie une nouvelle configuration."""

    def __init__(self, blocks: dict | None = None, chan: int = 1):
        self.blocks = {b: (blocks or {}).get(b, Knobs()) for b in BLOCKS}
        self.chan = chan

    def with_block(self, block: str, knobs: Knobs) -> "Config":
        b = dict(self.blocks)
        b[block] = knobs
        return Config(b, self.chan)

    def with_chan(self, chan: int) -> "Config":
        return Config(self.blocks, chan)

    def to_json(self) -> dict:
        return {"blocks": {b: asdict(k) for b, k in self.blocks.items()}, "chan": self.chan}

    @staticmethod
    def from_json(d: dict) -> "Config":
        return Config({b: Knobs(**k) for b, k in d["blocks"].items()}, d.get("chan", 1))

    def key(self) -> str:
        return json.dumps(self.to_json(), sort_keys=True)

    def label(self) -> str:
        """Une ligne : « L1 II1 · L2 II1 ×2 DP · L3 — · FC — »."""
        return " · ".join(f"{SHORT[b]} {k.short(b)}" for b, k in self.blocks.items()) + \
            (f" · ping-pong" if self.chan == 2 else "")

    def __eq__(self, other):
        return isinstance(other, Config) and self.key() == other.key()

    def __hash__(self):
        return hash(self.key())


# ============================================================
# Montée (rendre plus rapide) et replis (rendre moins coûteux)
# ============================================================

@dataclass(frozen=True)
class Rung:
    """Un barreau de l'échelle d'un bloc : réglages à poser, puis variantes essayées dans l'ordre
    (la suivante seulement si Catapult échoue sur la précédente, par ex. II impossible)."""
    name: str
    sets: dict
    variants: tuple = ({},)


LADDER = (
    Rung("ReLU + pool pipelinés", {"pp": True}),
    Rung("MAC pipelinées", {"pipe": True}, ({"ii": 1}, {"ii": 2})),
    Rung("2 MAC/cycle + RAM double port", {"pipe": True, "par": 2, "dp": True}, ({"ii": 1}, {"ii": 2})),
    Rung("5 MAC/cycle, entrée en 5 bancs", {"pipe": True, "par": 5, "dp": True, "xin": True}, ({"ii": 1}, {"ii": 2})),
    Rung("10 MAC/cycle (MAC_N + MAC_CI/2)", {"pipe": True, "par": 10, "dp": True, "xin": True},
         ({"ii": 1}, {"ii": 2})),
)
DENSE_LADDER = (Rung("perceptron pipeliné", {"pipe": True}, ({"ii": 1},)),)


def ladder(block: str) -> tuple:
    return DENSE_LADDER if block == "dense" else LADDER


def rung_done(k: Knobs, rung: Rung) -> bool:
    """Le bloc a déjà (au moins) ce que pose le barreau."""
    for f, v in rung.sets.items():
        cur = getattr(k, f)
        if isinstance(v, bool):
            if cur != v:
                return False
        elif cur < v:                  # par : 5 inclut 2
            return False
    return True


def apply_rung(k: Knobs, rung: Rung, variant: dict) -> Knobs:
    return replace(k, **rung.sets, **variant)


def trim_moves(cfg: Config) -> list:
    """Replis possibles depuis cfg : [(bloc, description, nouvelle config)], du plus économe au moins économe."""
    moves = []
    for b, k in cfg.blocks.items():
        if k.par > 1:
            lower = {10: 5, 5: 2, 2: 1}[k.par]
            k2 = replace(k, par=lower, dp=k.dp if lower > 1 else False, xin=k.xin and lower >= 5,
                         ii=1 if lower > 1 else k.ii)
            moves.append((b, f"×{k.par} → ×{lower}", cfg.with_block(b, k2)))
        if k.dp and k.par == 1:
            moves.append((b, "RAM double port → simple", cfg.with_block(b, replace(k, dp=False))))
        if k.pipe and k.par == 1:
            moves.append((b, "pipeline retiré", cfg.with_block(b, replace(k, pipe=False, ii=1))))
        if k.pp:
            moves.append((b, "ReLU/pool séquentiels", cfg.with_block(b, replace(k, pp=False))))
    if cfg.chan == 2:
        moves.append(("canaux", "ping-pong → mémoire simple", cfg.with_chan(1)))
    return moves


# ============================================================
# Chemins Catapult découverts sur le projet de base
# ============================================================

# Instance de fonction (paramètres de dimension seulement, stables quels que soient les formats) -> bloc
INSTANCE_BLOCK = (
    ("convolution_feature<3,24,24,64,", "layer1"), ("relu<36864,", "layer1"), ("max_pool<64,24,24,", "layer1"),
    ("convolution_feature<64,12,12,32,", "layer2"), ("relu<4608,", "layer2"), ("max_pool<32,12,12,", "layer2"),
    ("convolution_feature<32,6,6,20,", "layer3"), ("relu<720,", "layer3"), ("max_pool<20,6,6,", "layer3"),
    ("m_acc_hwc<", "dense"),
)


class Discovery:
    """
    Chemins exacts des boucles et des mémoires, lus dans les fichiers écrits par le projet de base :
        loops.txt      <chemin>/MERGEABLE <valeur>    (directive get /.../* -match glob ... -MERGEABLE)
        resources.txt  <chemin>/MAP_TO_MODULE <valeur>
    Une boucle s'appelle par ex. /cnn/layer2/core/core:rlp/main/<...>/convolution_feature<64,12,...>:MAC_N :
    on la range sous (bloc, label). Le bloc vient du chemin (/layer2/) ou, à défaut, de l'instance.
    """

    def __init__(self, loops: dict | None = None, resources: dict | None = None, resource_paths: list | None = None):
        self.loops = loops or {}          # (bloc, label) -> chemin
        self.resources = resources or {}  # nom du tableau -> premier chemin trouvé
        self.resource_paths = resource_paths or list(self.resources.values())   # tous (x existe dans 2 blocs)

    @staticmethod
    def _entries(text: str, directive: str) -> list:
        """Chemins trouvés dans le fichier : tout mot qui commence par / (éventuellement entre accolades Tcl),
        suffixe /<directive> retiré. Accepte la forme plate (chemin, valeur sur des lignes séparées ou non)."""
        out = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for path in re.findall(r"\{(/[^}]*)\}|(/\S+)", line):
                path = (path[0] or path[1]).strip()
                suffix = "/" + directive
                if path.endswith(suffix):
                    path = path[: -len(suffix)]
                out.append(path)
        return out

    @classmethod
    def parse(cls, loops_txt: str, resources_txt: str) -> "Discovery":
        """Une boucle labellisée s'appelle LABEL (manuel Catapult, « Labels ») ou <fonction>:LABEL selon
        l'endroit : on prend ce qui suit le dernier « : » du dernier segment, s'il est en MAJUSCULES."""
        d = cls()
        for path in cls._entries(loops_txt, "MERGEABLE"):
            last = path.rsplit("/", 1)[-1]
            inst, _, label = last.rpartition(":")
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", label):
                continue
            block = cls._block_of(path, inst)
            if block:
                d.loops.setdefault((block, label), path)
        for path in cls._entries(resources_txt, "MAP_TO_MODULE"):
            name = cls._res_name(path)
            if name and path.endswith((":rsc", ":cns")):
                d.resources.setdefault(name, path)
                d.resource_paths.append(path)
        return d

    @staticmethod
    def _res_name(path: str) -> str:
        """/cnn/layer2:inst/core/x.data:rsc -> x ; /cnn/layer2:inst/ker2.v.rom:rsc -> ker2"""
        return path.rsplit("/", 1)[-1].split(":")[0].split(".")[0]

    @staticmethod
    def _block_of(path: str, inst: str) -> str | None:
        m = re.search(r"/(layer[123]|dense)(/|$|:)", path)
        if m:
            return m.group(1)
        flat = path.replace(" ", "")
        for prefix, block in INSTANCE_BLOCK:        # instance n'importe où dans le chemin
            if prefix in flat:
                return block
        return None

    def to_json(self) -> dict:
        return {"loops": {f"{b}:{l}": p for (b, l), p in self.loops.items()}, "resources": self.resources,
                "resource_paths": self.resource_paths}

    @staticmethod
    def from_json(d: dict) -> "Discovery":
        return Discovery({tuple(k.split(":", 1)): p for k, p in d["loops"].items()}, d["resources"],
                         d.get("resource_paths"))

    def loop(self, block: str, label: str) -> list:
        p = self.loops.get((block, label))
        return [p] if p else []

    def resource(self, name: str, block: str | None = None) -> list:
        """Chemin découvert (celui du bloc demandé si le nom existe dans plusieurs blocs), sinon les chemins
        probables (essayés dans l'ordre par explo_try)."""
        hits = [p for p in self.resource_paths if self._res_name(p) == name]
        if block:
            mine = [p for p in hits if f"/{block}:" in p or f"/{block}/" in p]
            hits = mine or [p for p in hits if not re.search(r"/(layer[123]|dense)[:/]", p)]
        if hits:
            return hits[:1]
        guesses = [f"/cnn/{name}:cns", f"/cnn/{name}:rsc"]
        if block:
            # forme réelle relevée à l'école (2026-11-25) d'abord : /cnn/layer2:inst/core/x.data:rsc
            guesses = [f"/cnn/{block}:inst/core/{name}:rsc", f"/cnn/{block}:inst/core/{name}.data:rsc",
                       f"/cnn/{block}:inst/{name}.v.rom:rsc",
                       f"/cnn/{block}/core/{name}:rsc", f"/{block}/core/{name}:rsc",
                       f"/cnn/{block}/{name}.v.rom:rsc", f"/cnn/{block}/core/{name}.v.rom:rsc"] + guesses
        return guesses


# ============================================================
# Directives
# ============================================================

@dataclass
class Directive:
    paths: list          # chemins candidats, le premier accepté gagne
    args: str            # ex. "-PIPELINE_INIT_INTERVAL 1"
    what: str            # pour le journal : « layer2 MAC pipelinées »
    essential: bool = True   # refusée -> le résultat ne correspond pas à la config (statut « refusé »)


def directives(cfg: Config, disc: Discovery) -> list:
    out = []
    for b in CONV:
        k = cfg.blocks[b]
        if k.pp:
            out.append(Directive(disc.loop(b, "RELU"), "-PIPELINE_INIT_INTERVAL 1", f"{b} ReLU pipelinée"))
            out.append(Directive(disc.loop(b, "POOL_CO"), "-PIPELINE_INIT_INTERVAL 1", f"{b} max-pool pipeliné"))
        if k.pipe:
            out.append(Directive(disc.loop(b, "CONV_CO"), f"-PIPELINE_INIT_INTERVAL {k.ii}", f"{b} MAC pipelinées"))
        if k.par > 1:
            un, ci = PAR_SPLIT[k.par]
            out.append(Directive(disc.loop(b, "MAC_N"), f"-UNROLL {'yes' if un == 5 else un}", f"{b} MAC_N x{un}"))
            if ci > 1:
                out.append(Directive(disc.loop(b, "MAC_CI"), f"-UNROLL {ci}", f"{b} MAC_CI x{ci}"))
            out.append(Directive(disc.resource(ROM_OF[b], b), f"-INTERLEAVE {k.par}",
                                 f"{b} poids en {k.par} bancs"))
        if k.xin:
            out.append(Directive(disc.resource(IN_MAP[b], b), f"-INTERLEAVE {k.in_banks()}",
                                 f"{b} entrée en {k.in_banks()} bancs"))
        if k.dp:
            out.append(Directive(disc.resource(OUT_MAP[b], b), f"-MAP_TO_MODULE {RAM_DP}", f"{b} sortie double port"))
            out.append(Directive(disc.resource(IN_MAP[b], b), f"-MAP_TO_MODULE {RAM_DP}", f"{b} entrée double port"))
    if cfg.blocks["dense"].pipe:
        out.append(Directive(disc.loop("dense", "FC_ROW"), f"-PIPELINE_INIT_INTERVAL {cfg.blocks['dense'].ii}",
                             "perceptron pipeliné"))
    for ch in CHANNELS:
        out.append(Directive(disc.resource(ch), f"-STAGE_REPLICATION {cfg.chan}", f"{ch} : {cfg.chan} étage(s)",
                             essential=(cfg.chan != 1)))
    return out


# Directive refusée par Catapult (texte « what » du journal, en ASCII) -> réglage en cause
REFUSAL_KNOB = (("entree en", "xin"), ("double port", "dp"), ("MAC_", "par"), ("poids", "par"),
                ("MAC pipelinees", "pipe"), ("perceptron", "pipe"), ("ReLU", "pp"), ("max-pool", "pp"))


def refused_knobs(whats: list) -> set:
    """Réglages dont une directive a été refusée : inutile de les reproposer (le refus est structurel)."""
    return {knob for w in whats for key, knob in REFUSAL_KNOB if key in w}


def ascii(text: str) -> str:
    """Catapult affiche mal l'UTF-8 : tout ce qui part dans le Tcl est en ASCII (é -> e, × -> x)."""
    text = text.replace("×", "x").replace("→", "->")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def tcl_lines(dirs: list) -> list:
    """Directives en Tcl : explo_try essaie les chemins candidats (proc définie dans backend.CAND_TCL)."""
    lines = []
    for d in dirs:
        paths = " ".join("{" + p + "}" for p in d.paths)
        lines.append(f"explo_try {{{ascii(d.what)}}} {int(d.essential)} [list {paths}] {d.args}")
    return lines
