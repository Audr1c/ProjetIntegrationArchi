"""Cache des évaluations (partagé par toutes les explorations) et lecture des runs stockés."""

import json
import sys
import threading

from . import paths

# ============================================================
# Cache des évaluations (partagé par toutes les explorations)
# ============================================================

class Cache:
    """
    Une ligne JSON par évaluation dans runs/cache.jsonl (on ajoute, on ne réécrit jamais tout le fichier).
    Si une configuration apparaît plusieurs fois, la dernière ligne gagne.
    L'ancien runs/cache.json est encore lu (compatibilité).
    """

    def __init__(self):
        paths.RUNS.mkdir(parents=True, exist_ok=True)
        self.data = {}
        old = paths.OLD_CACHE_FILE
        if old.exists():
            self.data.update(json.loads(old.read_text()))
        if paths.CACHE_FILE.exists():
            with open(paths.CACHE_FILE) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:   # dernière ligne tronquée par un arrêt brutal
                        continue
                    self.data[e["id"]] = e
        self.lock = threading.Lock()

    def get(self, pid):
        return self.data.get(pid)

    def put(self, pid, entry):
        line = json.dumps(entry, separators=(",", ":")) + "\n"
        with self.lock:
            self.data[pid] = entry
            with open(paths.CACHE_FILE, "a") as f:
                f.write(line)

    def points(self, k=None, n=None, code=None):
        """Évaluations complètes (les candidats coupés tôt n'ont pas de précision finale)."""
        return [e for e in self.data.values()
                if (k is None or e["k"] == k) and (n is None or e["n"] == n)
                and (code is None or e["code"] == code) and "acc" in e]


def load_runs(k=None, n=None):
    out = []
    for d in sorted(paths.RUNS.iterdir()) if paths.RUNS.exists() else []:
        f = d / "summary.json"
        if f.exists():
            s = json.loads(f.read_text())
            if (k is None or s["k"] == k) and (n is None or s["images"] == n):
                out.append(s)
    return out


def find_run(prefix):
    m = [d for d in paths.RUNS.iterdir() if d.is_dir() and d.name.startswith(prefix)] if paths.RUNS.exists() else []
    if len(m) > 1:
        sys.exit(f"Plusieurs runs commencent par {prefix}")
    return m[0] if m else None
