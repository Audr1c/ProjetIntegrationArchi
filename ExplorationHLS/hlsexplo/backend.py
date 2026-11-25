"""
Moteurs de synthèse : le vrai Catapult (machines de l'école) ou un faux, pour tester sans licence.

Catapult, pour chaque worker (dossier ExplorationHLS/work/w<N>/, un projet par worker) :
  1. Projet de base, une seule fois par version du code : hls/cnn.tcl sourcé avec CNN_STOP_AT = assembly
     (go analyze, compile, libraries, assembly, AUCUNE directive de boucle ni de mémoire), puis
     découverte des chemins exacts des boucles et des mémoires (directive get /.../* -match glob),
     puis project save. Refait automatiquement si un fichier de paths.CODE_FILES change.
  2. Chaque candidat : catapult -shell -file cand.tcl dans le même dossier :
         project load base ; solution new -state assembly ; directives ; go extract
     Le projet n'est PAS sauvé : la solution suivante reprend le même nom. Les rapports sont lus par
     hls/catapult_report.py, puis le dossier de la solution est effacé (~100 Mo chacun).
Délai maximal par synthèse (seuil S9) : le groupe de processus Catapult est tué.
"""

from __future__ import annotations

import gzip
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import paths
from .model import Model, ii_min
from .space import BLOCKS, CHANNELS, CONV, INSTANCE_BLOCK, OUT_MAP, ROM_OF, Config, Discovery, ascii, tcl_lines

sys.path.insert(0, str(paths.HLS))
import catapult_report  # noqa: E402  (hls/catapult_report.py : Python standard)

# Étapes d'une synthèse, dans l'ordre (lignes « Starting transformation '<étape>' » du journal de
# Catapult 2024.2, relevées dans hls/rapports/*/catapult.log) : barre de progression des workers
BASE_STAGES = ("analyze", "compile", "libraries", "assembly")
CAND_STAGES = ("loops", "memories", "cluster", "architect", "allocate", "schedule", "dpfsm", "instance", "extract")
STAGE_RE = re.compile(r"transformation '(\w+)'|^\s*(?:#\s*)?go (\w+)")


class BackendError(RuntimeError):
    pass


def _block_of_process(name: str) -> str | None:
    m = re.search(r"(layer[123]|dense)", name)
    return m.group(1) if m else None


def summarize(rep: dict) -> dict:
    """Rapport complet de catapult_report.parse_solution -> les quelques nombres utiles à l'exploration."""
    blocks = {}
    for p in rep.get("processes") or []:
        b = _block_of_process(p["name"])
        if b and p.get("latency_cycles") is not None:
            blocks[b] = blocks.get(b, 0) + p["latency_cycles"]
    area = rep.get("area") or {}
    # Une image traverse les couches l'une après l'autre : latence = somme des blocs
    latency = sum(blocks.values()) if blocks else rep.get("latency_cycles")
    prof = sorted(rep.get("profile") or [], key=lambda r: -(catapult_report.num(r.get("Total Cycles")) or 0))
    return {
        "status": "ok" if latency is not None else "fail",
        "latency": latency,
        "throughput": max(blocks.values()) if blocks else rep.get("throughput_cycles"),
        "blocks": blocks,
        "bram": rep.get("bram18_total"),
        "dsp": area.get("DSP"),
        "lut": area.get("LUTs"),
        "slack": rep.get("slack_ns"),
        "max_delay": rep.get("max_delay_ns"),
        "loops": [[(r.get("Loop") or "").strip()[-70:], catapult_report.num(r.get("Total Cycles"))] for r in prof[:6]],
    }


# ============================================================
# Vrai Catapult
# ============================================================

class CatapultBackend:
    kind = "catapult"

    def __init__(self, slot: int, timeout_s: float, base_timeout_s: float, keep: bool = False):
        self.slot = slot
        self.dir = paths.WORK / f"w{slot}"
        self.timeout_s = timeout_s
        self.base_timeout_s = base_timeout_s
        self.keep = keep
        self.proc = None
        self.base = None            # {"code", "ccs", "solution", "discovery"}

    @staticmethod
    def check_tool():
        if shutil.which("catapult") is None:
            raise BackendError("commande catapult introuvable : source hls/bash_mentor_24 avant de lancer "
                               "(ou --fake pour tester sans Catapult)")
        if " " in str(paths.ROOT):
            raise BackendError(f"chemin du dépôt avec un espace ({paths.ROOT}) : Catapult/SCVerify le gèrent mal, "
                               "cloner ailleurs")

    # ---------------- lancement d'un script ----------------
    def _run(self, script: str, timeout: float, stages, on_stage) -> tuple:
        """Lance catapult sur un script du dossier du worker. Renvoie (code retour, délai dépassé, log)."""
        log_path = self.dir / (Path(script).stem + ".log")
        cmd = ["catapult", "-shell", "-file", script]
        with open(log_path, "w", errors="replace") as log:
            self.proc = subprocess.Popen(cmd, cwd=str(self.dir), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, universal_newlines=True, errors="replace",
                                         start_new_session=True)

            def reader():
                for line in self.proc.stdout:
                    log.write(line)
                    m = STAGE_RE.search(line)
                    st = m and (m.group(1) or m.group(2))
                    if st in stages:
                        on_stage(st, stages.index(st) + 1, len(stages))

            t = threading.Thread(target=reader, daemon=True)
            t.start()
            timed_out = False
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                self.kill()
            t.join(timeout=10)
            rc = self.proc.returncode
            self.proc = None
        return rc, timed_out, log_path

    def kill(self):
        p = self.proc
        if p is None or p.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            p.wait(timeout=15)
        except Exception:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except Exception:
                pass

    # ---------------- projet de base ----------------
    def prepare(self, on_stage) -> Discovery:
        """Projet de base (construit, ou repris s'il est à jour), puis chemins des boucles et des mémoires."""
        code = paths.code_hash()
        ok = self.dir / "base_ok.json"
        base = json.loads(ok.read_text()) if ok.exists() else None
        if not (base and base.get("code") == code and Path(base["ccs"]).exists()):
            base = self._adopt_base(code) or self._build_base(code, on_stage)
        self.base = base
        disc = self._parse_discovery()
        if not disc.loops:                      # découverte seule, sans refaire le projet de base
            (self.dir / "discover.tcl").write_text(DISCOVER_TCL.format(ccs=base["ccs"], dump=DUMP_PROC))
            on_stage("discover", 1, 1)
            self._run("discover.tcl", self.timeout_s, ("discover",), on_stage)
            disc = self._parse_discovery()
        if not disc.loops:
            lines = [l for l in _read(self.dir / "loops.txt").splitlines() if l.strip()][:6]
            raise BackendError("aucune boucle reconnue dans le projet de base (le projet est gardé : corriger puis "
                               f"relancer ne refait pas go analyze). Début de {self.dir / 'loops.txt'} :\n    "
                               + ("\n    ".join(l[:160] for l in lines) if lines else "(vide)")
                               + f"\nJournal : {self.dir / 'discover.log'}")
        return disc

    def _parse_discovery(self) -> Discovery:
        return Discovery.parse(_read(self.dir / "loops.txt"), _read(self.dir / "resources.txt"))

    def _build_base(self, code: str, on_stage) -> dict:
        if self.dir.exists():
            shutil.rmtree(str(self.dir))
        self.dir.mkdir(parents=True)
        (self.dir / "base.tcl").write_text(BASE_TCL.format(cnn_tcl=paths.CNN_TCL, dump=DUMP_PROC))
        rc, timed_out, log = self._run("base.tcl", self.base_timeout_s, BASE_STAGES, on_stage)
        ccs = sorted(self.dir.glob("*.ccs"))
        if timed_out or not ccs or "EXPLO_BASE_OK" not in log.read_text(errors="replace"):
            raise BackendError(f"projet de base non construit ({'délai dépassé' if timed_out else f'code {rc}'}) : "
                               f"voir {log}")
        return self._save_base(code, ccs[0])

    def _adopt_base(self, code: str) -> dict | None:
        """Projet de base déjà construit mais jamais validé (ex. découverte ratée avec une ancienne version de
        l'outil) : repris s'il a abouti et s'il est plus récent que tous les fichiers du code."""
        log = self.dir / "base.log"
        ccs = sorted(self.dir.glob("*.ccs"))
        if not ccs or "EXPLO_BASE_OK" not in _read(log):
            return None
        if ccs[0].stat().st_mtime < max(f.stat().st_mtime for f in paths.CODE_FILES):
            return None
        return self._save_base(code, ccs[0])

    def _save_base(self, code: str, ccs: Path) -> dict:
        sols = [p.name for p in self._solutions()]
        base = {"code": code, "ccs": str(ccs), "solution": sorted(sols)[0] if sols else "cnn.v1"}
        (self.dir / "base_ok.json").write_text(json.dumps(base, indent=1))
        return base

    # ---------------- un candidat ----------------
    def _solutions(self):
        """Dossiers de solution du projet (<projet>/cnn.vN), quel que soit le nom du projet."""
        return [p for p in self.dir.glob("*/cnn.v*") if p.is_dir()]

    def evaluate(self, cfg: Config, dirs: list, on_stage, out_dir: Path) -> dict:
        for old in self._solutions():                    # restes d'un candidat précédent ou interrompu
            if old.name != self.base["solution"]:
                shutil.rmtree(str(old), ignore_errors=True)
        (self.dir / "cand.tcl").write_text(CAND_TCL.format(
            label=ascii(cfg.label()), ccs=self.base["ccs"], directives="\n".join(tcl_lines(dirs))))
        dlog = self.dir / "directives_log.txt"
        if dlog.exists():
            dlog.unlink()
        start = time.time()
        rc, timed_out, log = self._run("cand.tcl", self.timeout_s, CAND_STAGES, on_stage)
        refused = [l.split("\t")[2] for l in _read(dlog).splitlines() if l.startswith("KO\t1\t")]
        _save_small(out_dir, [self.dir / "cand.tcl", dlog], log)
        if timed_out:
            return {"status": "timeout", "refused": refused}
        sols = sorted((p for p in self.dir.glob("*/cnn.v*/rtl.rpt") if p.stat().st_mtime >= start - 1),
                      key=lambda p: p.stat().st_mtime)
        if not sols:
            errs = [l.strip() for l in log.read_text(errors="replace").splitlines() if "Error" in l]
            return {"status": "fail", "refused": refused, "error": (errs[-1] if errs else f"code {rc}")[:200]}
        sol = sols[-1].parent
        res = summarize(catapult_report.parse_solution(sol))
        res["refused"] = refused
        for f in ("rtl.rpt", "cycle.rpt"):
            if (sol / f).exists():
                with open(sol / f, "rb") as src, gzip.open(out_dir / (f + ".gz"), "wb") as dst:
                    shutil.copyfileobj(src, dst)
        if not self.keep:
            shutil.rmtree(str(sol), ignore_errors=True)
        return res


def _read(p: Path) -> str:
    return p.read_text(errors="replace") if p.exists() else ""


def _save_small(out_dir: Path, files, log: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        if f.exists():
            shutil.copy(str(f), str(out_dir / f.name))
    lines = log.read_text(errors="replace").splitlines() if log.exists() else []
    (out_dir / "catapult_fin.txt").write_text("\n".join(lines[-200:]) + "\n")


# Écrit tous les chemins portant une directive : un élément de la liste renvoyée par ligne (forme plate
# « chemin valeur chemin valeur » ou paires) ; Discovery.parse ne garde que les mots qui commencent par /.
# Plusieurs motifs, essayés dans l'ordre ; une ligne de commentaire par motif pour le diagnostic.
DUMP_PROC = """\
proc explo_dump {file directive} {
    set f [open $file w]
    foreach pattern {/.../* /* /cnn/* /cnn/.../* /cnn/*/*/*/*/*/*/*/*/*/*/*/*} {
        if {[catch {directive get $pattern -match glob -return pathvalue $directive} res]} {
            puts $f "# ERREUR ($pattern) $res"
            continue
        }
        puts $f "# motif $pattern : [llength $res] elements"
        if {[llength $res] > 0} {
            foreach e $res { puts $f $e }
            break
        }
    }
    close $f
}"""

BASE_TCL = """\
# Projet de base de l'exploration HLS (genere par ExplorationHLS, ne pas modifier)
# hls/cnn.tcl jusqu'a go assembly, decouverte des chemins des boucles et des memoires, sauvegarde.
set ::CNN_STOP_AT assembly
source {{{cnn_tcl}}}
{dump}
catch {{explo_dump loops.txt -MERGEABLE}}
catch {{explo_dump resources.txt -MAP_TO_MODULE}}
project save
puts "EXPLO_BASE_OK"
exit
"""

DISCOVER_TCL = """\
# Decouverte seule des chemins des boucles et des memoires, sur le projet de base deja sauve
project load {{{ccs}}}
{dump}
explo_dump loops.txt -MERGEABLE
explo_dump resources.txt -MAP_TO_MODULE
puts "EXPLO_DISCOVER_OK"
exit
"""

CAND_TCL = """\
# Candidat de l'exploration HLS (genere par ExplorationHLS) : {label}
project load {{{ccs}}}
solution new -state assembly
set ::explo_log [open directives_log.txt w]
# explo_try : essaie les chemins dans l'ordre ; journal OK/KO (KO + essentielle = resultat ecarte)
proc explo_try {{what essential paths args}} {{
    foreach p $paths {{
        if {{![catch {{directive set $p {{*}}$args}}]}} {{
            puts $::explo_log "OK\\t$essential\\t$what\\t$p $args"
            return 1
        }}
    }}
    puts $::explo_log "KO\\t$essential\\t$what\\t$paths $args"
    return 0
}}
{directives}
close $::explo_log
go extract
puts "EXPLO_EXTRACT_OK"
exit
"""


# ============================================================
# Faux Catapult (--fake) : même interface, résultats tirés du modèle + bruit + défauts réalistes
# ============================================================

class FakeBackend:
    """Pour tester l'outil (tableau de bord, recherche, reprise, graphes) sans licence.
    Durée d'une synthèse : quelques secondes. Les nombres ne valent RIEN pour le vrai matériel."""
    kind = "fake"

    def __init__(self, slot: int, limits, speed: float = 1.0):
        self.slot = slot
        self.speed = speed
        self.truth = Model(limits)
        self.stop = threading.Event()

    @staticmethod
    def check_tool():
        pass

    def kill(self):
        self.stop.set()

    def _sleep(self, s):
        if self.stop.wait(s * self.speed):
            raise BackendError("interrompu")

    def prepare(self, on_stage) -> Discovery:
        for i, st in enumerate(BASE_STAGES):
            on_stage(st, i + 1, len(BASE_STAGES))
            self._sleep(0.6)
        loops = {}
        labels = {"convolution_feature": ("CONV_CO", "MAC_N"), "relu": ("RELU",), "max_pool": ("POOL_CO",),
                  "m_acc_hwc": ("FC_ROW",)}
        for prefix, block in INSTANCE_BLOCK:
            for lab in labels[prefix.split("<")[0]]:
                loops[(block, lab)] = f"/cnn/{block}/core/core:rlp/main/{prefix}...>:{lab}"
        res = {n: f"/cnn/{b}/core/{n}:rsc" for b, n in list(OUT_MAP.items()) + list(ROM_OF.items())}
        res.update({c: f"/cnn/{c}:cns" for c in CHANNELS})
        return Discovery(loops, res)

    def evaluate(self, cfg: Config, dirs: list, on_stage, out_dir: Path) -> dict:
        rng = random.Random(cfg.key())
        dur = rng.uniform(2.0, 5.0) * (1 + 0.3 * sum(cfg.blocks[b].par > 1 for b in CONV))
        for i, st in enumerate(CAND_STAGES):
            on_stage(st, i + 1, len(CAND_STAGES))
            self._sleep(dur / len(CAND_STAGES))
        # défauts « réalistes » : II impossible, timing, erreurs rares
        for b in CONV:
            k = cfg.blocks[b]
            if k.pipe and ii_min(k) > k.ii:
                return {"status": "fail", "refused": [], "error": f"{b} : II={k.ii} impossible (ports mémoire)"}
        if cfg.blocks["layer1"].xin:          # simulé : l'interface du top ne se découpe pas en bancs
            return {"status": "ok", "refused": ["layer1 entree en 5 bancs"], "latency": None}
        if rng.random() < 0.04:
            return {"status": "fail", "refused": [], "error": "Error: erreur interne simulée"}
        blocks = {}
        for b in BLOCKS:
            k = cfg.blocks[b]
            f = (1.10 if k.pipe else 1.0) * (1.25 if (b == "layer1" and k.dp) else 1.0)   # entrée layer1 en 1R1W
            blocks[b] = int(self.truth.raw_block_latency(b, k) * f * rng.uniform(0.97, 1.03))
        r = self.truth.raw_resources(cfg)
        slack = 0.45 - 0.35 * sum(cfg.blocks[b].par == 5 for b in CONV) - 0.1 * sum(cfg.blocks[b].pp for b in CONV)
        return {"status": "ok", "refused": [], "latency": sum(blocks.values()), "blocks": blocks,
                "throughput": max(blocks.values()), "bram": int(r["bram"] + 4),
                "dsp": int(r["dsp"] * 1.5 + 2), "lut": int((r["lut"] + 1500) * rng.uniform(0.9, 1.1)),
                "slack": round(slack + rng.uniform(-0.15, 0.15), 3), "max_delay": None, "loops": []}
