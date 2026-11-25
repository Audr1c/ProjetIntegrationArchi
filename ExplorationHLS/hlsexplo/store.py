"""
Stockage : cache des synthèses (partagé par tous les runs) et dossier de chaque run.

    runs/cache.jsonl              une ligne par synthèse : id, code, config, résultat (on ajoute, jamais réécrit)
    runs/<run>/params.json        paramètres (cible, budgets, moteur, jobs)
    runs/<run>/history.jsonl      chaque évaluation du run : phase, bloc, changement, statut, décision
    runs/<run>/summary.json       référence, configuration retenue, chemin suivi
    runs/<run>/best_directives.tcl  directives de la configuration retenue, à reporter dans hls/cnn.tcl
    runs/<run>/evals/<id>/        cand.tcl, directives_log.txt, fin du journal, rtl.rpt.gz, cycle.rpt.gz
    runs/<run>/*.png              graphes (ignorés par git, regénérés par « plot »)
Un id = empreinte du code (paths.code_hash) + configuration : relancer la même commande après une
interruption repasse instantanément sur tout ce qui est déjà synthétisé.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from . import paths
from .space import Config


def eval_id(code: str, cfg: Config) -> str:
    return hashlib.sha1(f"{code}|{cfg.key()}".encode()).hexdigest()[:10]


class Store:
    def __init__(self, fake: bool, run_name: str | None = None):
        self.root = paths.runs_dir(fake)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.root / "cache.jsonl"
        self.cache = {}
        if self.cache_file.exists():
            for line in self.cache_file.read_text().splitlines():
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:        # dernière ligne coupée par un arrêt brutal
                    continue
                self.cache[e["id"]] = e
        self.lock = threading.Lock()
        self.run = self.root / run_name if run_name else None
        if self.run:
            (self.run / "evals").mkdir(parents=True, exist_ok=True)

    # ---------------- cache ----------------
    def cached(self, eid: str) -> dict | None:
        e = self.cache.get(eid)
        # un échec dû à un arrêt de l'utilisateur ou à un délai dépassé se retente
        if e and e["result"].get("status") in ("interrupted", "timeout"):
            return None
        return e

    def put(self, eid: str, code: str, cfg: Config, result: dict, duration: float):
        e = {"id": eid, "code": code, "config": cfg.to_json(), "result": result,
             "duration": round(duration, 1), "date": time.strftime("%Y-%m-%d %H:%M:%S")}
        with self.lock:
            self.cache[eid] = e
            with open(self.cache_file, "a") as f:
                f.write(json.dumps(e) + "\n")

    # ---------------- run ----------------
    def eval_dir(self, eid: str) -> Path:
        return self.run / "evals" / eid

    def write_json(self, name: str, data):
        (self.run / name).write_text(json.dumps(data, indent=1, ensure_ascii=False))

    def history(self, entry: dict):
        with self.lock:
            with open(self.run / "history.jsonl", "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def list_runs(fake: bool = False) -> list:
    root = paths.runs_dir(fake)
    return sorted(p for p in root.iterdir() if (p / "params.json").exists()) if root.exists() else []


def find_run(name: str | None, fake: bool = False) -> Path:
    runs = list_runs(fake)
    if not runs:
        raise SystemExit(f"aucun run dans {paths.runs_dir(fake)}")
    if not name:
        return runs[-1]
    hits = [r for r in runs if r.name.startswith(name) or name in r.name]
    if len(hits) != 1:
        raise SystemExit(f"run « {name} » : {len(hits)} correspondance(s)")
    return hits[0]


def read_history(run: Path) -> list:
    f = run / "history.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []
