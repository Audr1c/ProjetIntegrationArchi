"""Sessions : liste de runs prévue (graines, seuils), reprise après interruption."""

import json
import random
import sys
from datetime import datetime

from rich import box
from rich.table import Table

from . import paths
from .dashboard import console

# ---------- sessions : liste de runs prévue, reprise après interruption ----------

paths.SESSIONS = paths.RUNS / "sessions"
# paramètres qui doivent être identiques pour reprendre une session (workers peut changer)
SESSION_KEYS = ("k", "images", "batch", "threshold", "threshold_range", "parallel_vars", "order", "passes",
                "start_F", "early_stop", "z", "min_images", "reorder", "easy_frac", "easy_every", "runs")


def session_params(args):
    return json.loads(json.dumps({key: getattr(args, key) for key in SESSION_KEYS}))


def save_session(sess):
    paths.SESSIONS.mkdir(parents=True, exist_ok=True)
    tmp = paths.SESSIONS / f"{sess['id']}.tmp"
    tmp.write_text(json.dumps(sess, indent=1))
    tmp.replace(paths.SESSIONS / f"{sess['id']}.json")


def find_session(args, code):
    """Dernière session non terminée lancée avec les mêmes paramètres (et le même code C++)."""
    if not paths.SESSIONS.exists():
        return None
    params, found = session_params(args), None
    for f in sorted(paths.SESSIONS.glob("*.json")):
        sess = json.loads(f.read_text())
        if sess["params"] != params or sess["code"] != code:
            continue
        if args.seed is not None and sess["seed0"] != args.seed:
            continue
        if all(r["status"] == "terminé" for r in sess["runs"]):
            continue
        found = sess
    return found


def new_session(args, code):
    seed0 = args.seed if args.seed is not None else random.randrange(10000)
    rng = random.Random(seed0)
    runs = []
    for r in range(args.runs):
        thr = args.threshold
        if args.threshold_range:
            thr = round(rng.uniform(*args.threshold_range), 1)
        runs.append({"seed": seed0 + r, "threshold": thr, "run_id": None, "status": "à faire"})
    sess = {"id": datetime.now().strftime("%Y%m%d-%H%M%S"), "created": datetime.now().isoformat(timespec="seconds"),
            "params": session_params(args), "code": code, "seed0": seed0, "runs": runs}
    save_session(sess)
    return sess


def show_session(sess):
    t = Table(title=f"Session {sess['id']} (créée le {sess['created']})", box=box.SIMPLE_HEAD)
    for c in ("#", "graine", "seuil", "run", "statut", "variables"):
        t.add_column(c)
    for i, r in enumerate(sess["runs"], 1):
        col = {"terminé": "green", "interrompu": "yellow", "en cours": "yellow"}.get(r["status"], "dim")
        t.add_row(str(i), str(r["seed"]), f"{r['threshold']:g}", r["run_id"] or "-",
                  f"[{col}]{r['status']}", r.get("variables", ""))
    console.print(t)


def ask_resume(sess, args):
    show_session(sess)
    if args.resume:
        return True
    if args.new:
        return False
    if not sys.stdin.isatty():
        console.print("[yellow]Pas de terminal interactif : reprise automatique (--new pour repartir de zéro).")
        return True
    ans = console.input("Une session avec les mêmes paramètres n'est pas terminée. "
                        "[bold]Continuer cette session ? [O/n] [/]").strip().lower()
    return ans in ("", "o", "oui", "y", "yes")
