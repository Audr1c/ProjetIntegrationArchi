#!/usr/bin/env python3
"""
Exploration des directives Catapult du CNN (pipeline, déroulage, mémoires) — machines de l'école.

But : la configuration la MOINS COÛTEUSE en ressources qui respecte tous les seuils (hlsexplo/limits.py) :
    latence <= 10 M cycles (10 images/s à 100 MHz), BRAM18 <= 60 %, DSP <= 50 %, LUT <= 50 % du XC7Z020,
    slack >= 0, directives toutes appliquées.
Le code C++ ne change pas : seules les directives varient. Chaque candidat repart du même projet Catapult
déjà analysé (pas de go analyze), branché à l'état assembly.

Méthode (détail : hlsexplo/search.py)
    1. Référence     : aucune directive.
    2. Montée        : tant que la latence dépasse la cible, on monte d'un barreau le bloc (layer1, layer2,
                       layer3, dense) où le modèle analytique prédit le meilleur gain de cycles par unité de
                       ressource : ReLU/pool pipelinés, MAC pipelinées (II 1 puis 2), 2 MAC/cycle + RAM double
                       port, 5 MAC/cycle. Les barreaux sans gain prévisible sont écartés sans synthèse.
    3. Repli         : cible atteinte, on retire ce qui coûte tant que tous les seuils tiennent.
    Le modèle (hlsexplo/model.py) est recalé sur chaque synthèse : il classe, Catapult tranche.

Machines de l'école (Python 3.8, sans sudo)
    source hls/bash_mentor_24                    # Catapult dans le PATH
    make venv-ecole                              # une fois : .venv + requirements-ecole.txt (ou pip --user)
    make explore-hls ARGS="run"                  # ou : .venv/bin/python ExplorationHLS/explore_hls.py run
Le dépôt doit être cloné dans un chemin SANS espace. Une licence Catapult par worker (--jobs, défaut 1).

Commandes
    run    [options]      lance une exploration (Ctrl-C : arrêt propre ; relancer reprend sur le cache)
    base   [--jobs N]     construit seulement le(s) projet(s) de base (go analyze ... assembly)
    list                  tous les runs
    show   [run]          chemin suivi et configuration retenue (dernier run par défaut)
    plot   [run]          regénère pareto.png et evolution.png
    tcl    [run]          affiche best_directives.tcl (à passer à hls/cnn.tcl par DIRECTIVES_FILE)
    --fake sur chaque commande : faux Catapult (quelques secondes par synthèse) pour tester sans licence ;
    ses runs vont dans ExplorationHLS/runs_fake/.

Options de run [défaut]
    --target M        latence maximale en millions de cycles [10]
    --bram P / --dsp P / --lut P   budget en % du XC7Z020 [60 / 50 / 50]
    --slack NS        slack minimal estimé par Catapult [0]
    --jobs N          synthèses en parallèle (une licence et un projet de base chacune) [1]
    --timeout MIN     délai maximal d'une synthèse [30] ; --base-timeout MIN pour le projet de base [120]
    --max-evals N     nombre maximal de synthèses [60]
    --chan 1|2        canaux entre couches : mémoire simple ou ping-pong [1]
    --keep            garder les dossiers de solution (~100 Mo chacun) au lieu de les effacer
    --plain           affichage texte (sans rich, ou pour un journal)
    --name NOM        nom du run [date-heure]

Fichiers : ExplorationHLS/runs/ (cache.jsonl + un dossier par run, voir hlsexplo/store.py),
           ExplorationHLS/work/w<N>/ (projets Catapult, ignorés par git).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hlsexplo import paths, plots, report                       # noqa: E402
from hlsexplo.backend import BackendError, CatapultBackend, FakeBackend  # noqa: E402
from hlsexplo.dashboard import HAVE_RICH, PlainView              # noqa: E402
from hlsexplo.limits import Limits                               # noqa: E402
from hlsexplo.search import Explorer                             # noqa: E402
from hlsexplo.store import Store, find_run, list_runs            # noqa: E402


def make_backends(args, limits) -> list:
    if args.fake:
        return [FakeBackend(i, limits, args.speed) for i in range(args.jobs)]
    CatapultBackend.check_tool()
    return [CatapultBackend(i, args.timeout * 60, args.base_timeout * 60, args.keep) for i in range(args.jobs)]


def make_view(args, info, limits):
    if HAVE_RICH and not args.plain:
        from hlsexplo.dashboard import Dashboard
        return Dashboard(info, limits, args.jobs)
    return PlainView(info, limits, args.jobs)


# ============================================================
# Commandes
# ============================================================

def cmd_run(args):
    limits = Limits.from_args(args.target, args.bram, args.dsp, args.lut, args.slack)
    backends = make_backends(args, limits)
    name = args.name or time.strftime("%Y%m%d-%H%M%S") + ("_fake" if args.fake else "")
    base, n = name, 1
    while (paths.runs_dir(args.fake) / name).exists():       # même --name relancé : nouveau dossier
        n += 1
        name = f"{base}-{n}"
    store = Store(args.fake, name)
    info = {"run": name, "backend": "faux Catapult (--fake)" if args.fake else "Catapult",
            "clock_ns": paths.CLOCK_NS, "code": paths.code_hash(), "goal": args.goal}
    store.write_json("params.json", {**info, "limits": limits.to_json(), "jobs": args.jobs,
                                     "max_evals": args.max_evals, "chan": args.chan, "argv": sys.argv[1:]})
    view = make_view(args, info, limits)
    explorer = Explorer(backends, limits, store, view, args.max_evals, args.goal)

    t0, best, interrupted, error = time.time(), None, False, None
    live = None
    if hasattr(view, "console"):
        from rich.live import Live
        live = Live(view, console=view.console, refresh_per_second=4, screen=False)
        live.start()
    try:
        best = explorer.run(args.chan)
    except KeyboardInterrupt:
        interrupted = True
        explorer.abort()
    except BackendError as e:
        error = str(e)
    finally:
        if live:
            live.stop()
    best = best or (explorer.path[-1] if explorer.path else None)
    report.write_summary(store, explorer, best, interrupted, t0)
    pngs = plots.plot_run(store.run)
    console = getattr(view, "console", None)
    report.print_run(store.run, console)
    if pngs:
        print("graphes : " + ", ".join(str(p) for p in pngs))
    if interrupted:
        print("Interrompu : relancer la même commande reprend (les synthèses faites sont en cache).")
    if error:
        print(f"ERREUR : {error}")
        return 1
    return 0


def cmd_base(args):
    limits = Limits.from_args(10, 60, 50, 50, 0)
    view = PlainView({"run": "base"}, limits, args.jobs)
    explorer = Explorer(make_backends(args, limits), limits, Store(args.fake), view)
    try:
        explorer.prepare()
    except BackendError as e:
        print(f"ERREUR : {e}")
        return 1
    print("Projet(s) de base prêt(s) :", ", ".join(str(paths.WORK / f"w{i}") for i in range(args.jobs)))
    return 0


def cmd_list(args):
    for run in list_runs(args.fake):
        s = json.loads((run / "summary.json").read_text()) if (run / "summary.json").exists() else {}
        b = s.get("best") or {}
        lat = (b.get("result") or {}).get("latency")
        thr = (b.get("result") or {}).get("throughput")
        print(f"{run.name:28s} {s.get('goal', 'cost'):4s} {'cible OK ' if s.get('target_met') else 'cible KO '} "
              f"{(lat or 0) / 1e6:7.2f} M  débit {(thr or 0) / 1e6:5.2f} M  coût {b.get('cost', 0):.3f}  {s.get('counts', {}).get('synth', 0):3d} synthèses"
              f"  {b.get('label', '')}")
    return 0


def cmd_show(args):
    report.print_run(find_run(args.run, args.fake))
    return 0


def cmd_plot(args):
    for p in plots.plot_run(find_run(args.run, args.fake)):
        print(p)
    return 0


def cmd_tcl(args):
    f = find_run(args.run, args.fake) / "best_directives.tcl"
    print(f.read_text() if f.exists() else f"pas de {f}")
    return 0


# ============================================================
# Ligne de commande
# ============================================================

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Détails : docstring de ExplorationHLS/explore_hls.py")
    sub = ap.add_subparsers(dest="cmd")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--fake", action="store_true", help="faux Catapult (test sans licence)")

    r = sub.add_parser("run", parents=[common], help="lance une exploration")
    r.add_argument("--goal", choices=("cost", "perf"), default="cost",
                   help="cost : la moins chère sous la cible ; perf : la plus rapide (latence + débit) sous les budgets")
    r.add_argument("--target", type=float, default=10.0, help="latence max, millions de cycles [10]")
    r.add_argument("--bram", type=float, default=60.0, help="budget BRAM18, %% du XC7Z020 [60]")
    r.add_argument("--dsp", type=float, default=50.0, help="budget DSP, %% [50]")
    r.add_argument("--lut", type=float, default=50.0, help="budget LUT, %% [50]")
    r.add_argument("--slack", type=float, default=0.0, help="slack minimal, ns [0]")
    r.add_argument("--jobs", type=int, default=1, help="synthèses en parallèle (licences) [1]")
    r.add_argument("--timeout", type=float, default=30.0, help="délai max d'une synthèse, min [30]")
    r.add_argument("--base-timeout", type=float, default=120.0, help="délai max du projet de base, min [120]")
    r.add_argument("--max-evals", type=int, default=60, help="synthèses au plus [60]")
    r.add_argument("--chan", type=int, choices=(1, 2), default=1, help="canaux : 1 simple, 2 ping-pong [1]")
    r.add_argument("--keep", action="store_true", help="garder les dossiers de solution")
    r.add_argument("--plain", action="store_true", help="affichage texte")
    r.add_argument("--name", help="nom du run")
    r.add_argument("--speed", type=float, default=1.0, help="(--fake) facteur de durée des fausses synthèses")
    r.set_defaults(func=cmd_run)

    b = sub.add_parser("base", parents=[common], help="construit le(s) projet(s) de base")
    b.add_argument("--jobs", type=int, default=1)
    b.add_argument("--timeout", type=float, default=30.0)
    b.add_argument("--base-timeout", type=float, default=120.0)
    b.add_argument("--keep", action="store_true")
    b.add_argument("--speed", type=float, default=1.0)
    b.set_defaults(func=cmd_base)

    for name, func, hlp in (("list", cmd_list, "tous les runs"), ("show", cmd_show, "chemin et config retenue"),
                            ("plot", cmd_plot, "regénère les graphes"), ("tcl", cmd_tcl, "directives retenues")):
        p = sub.add_parser(name, parents=[common], help=hlp)
        if name != "list":
            p.add_argument("run", nargs="?", help="nom (ou début) du run [dernier]")
        p.set_defaults(func=func)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
