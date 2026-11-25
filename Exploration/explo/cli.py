"""Commandes de explore.py : run, list, show, pareto, plot, select."""

import argparse
import json
import os
import shutil
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from rich import box
from rich.live import Live
from rich.table import Table

from . import paths
from .cache import Cache, find_run, load_runs
from .dashboard import Dashboard, console, fmt_time
from .formats import FMT, NAMES, bits, code_hash, make_config_hpp, width
from .plots import pareto, pass_stats, plot_all, plot_formats, plot_formats_pyramid, plot_progress, plot_progress_all, plot_run
from .runner import Runner
from .search import Exploration
from .sessions import ask_resume, find_session, new_session, save_session, show_session

def cmd_run(args):
    if args.k not in (3, 5):
        sys.exit("--k doit valoir 3 ou 5")
    cache, runner = Cache(), Runner()
    console.print("[dim]Compilation des objets communs…")
    runner.prepare()
    code = code_hash()

    sess = find_session(args, code)
    if sess is None or not ask_resume(sess, args):
        sess = new_session(args, code)
        console.print(f"Nouvelle session [bold]{sess['id']}[/] : {len(sess['runs'])} run(s), "
                      f"graine de départ {sess['seed0']}")

    dash = Dashboard(args.workers, len(sess["runs"]))
    if dash.t_runs is not None:
        dash.overall.update(dash.t_runs, completed=sum(r["status"] == "terminé" for r in sess["runs"]))
    touched, ex, t_runs, n_ran = [], None, 0.0, 0
    pool = ThreadPoolExecutor(max_workers=2 * args.workers + 2)

    # 1er Ctrl-C : arrêt propre (on tue les calculs, la run en cours se sauvegarde et s'arrête)
    # 2e Ctrl-C  : arrêt immédiat
    interrupts = [0]

    def on_sigint(sig, frame):
        interrupts[0] += 1
        if interrupts[0] > 1:
            raise KeyboardInterrupt
        runner.kill_all()
        with dash.lock:
            dash.info["phase"] = "⏹ Arrêt demandé : sauvegarde de la run en cours… (Ctrl-C encore = immédiat)"

    old_handler = signal.signal(signal.SIGINT, on_sigint)
    try:
        with Live(dash, console=console, refresh_per_second=4, vertical_overflow="visible"):
            for r, entry in enumerate(sess["runs"]):
                if entry["status"] == "terminé":
                    continue
                if runner.stop.is_set():
                    break
                t = time.time()
                ex = Exploration(args, entry["seed"], entry["threshold"], cache, runner, dash, code,
                                 run_id=entry["run_id"])
                entry["run_id"], entry["status"] = ex.run_id, "en cours"
                save_session(sess)
                touched.append(ex)
                ex.run(pool, n_ran, t_runs)
                n_ran += 1
                t_runs += time.time() - t
                entry["status"] = ex.status
                entry["variables"] = f"{len(ex.done_idx)}/{len(ex.plan)}"
                save_session(sess)
                if dash.t_runs is not None and ex.status == "terminé":
                    dash.overall.advance(dash.t_runs)
    except KeyboardInterrupt:
        console.print("[red]Arrêt immédiat : les variables terminées sont sauvegardées.")
        runner.kill_all()
        if ex is not None and ex.status == "en cours":
            ex.status = "interrompu"
            try:
                ex.save()
            except Exception as e:
                console.print(f"[red]sauvegarde incomplète : {e}")
    finally:
        signal.signal(signal.SIGINT, old_handler)
        pool.shutdown(wait=True, cancel_futures=True)
        for entry in sess["runs"]:
            if entry["status"] == "en cours":
                entry["status"] = "interrompu"
        if ex is not None:
            for entry in sess["runs"]:
                if entry["run_id"] == ex.run_id:
                    entry["variables"] = f"{len(ex.done_idx)}/{len(ex.plan)}"
        save_session(sess)

    for e in touched:
        f = e.dir / "summary.json"
        if f.exists():
            print_summary(json.loads(f.read_text()))
    show_session(sess)
    if any(r["status"] != "terminé" for r in sess["runs"]):
        console.print("[yellow]Session non terminée : relancer la même commande pour la continuer.")
    if touched:
        plot_all(args.k, args.images, "mem")
        plot_all(args.k, args.images, "mem", zoom=True)
        plot_progress_all(args.k, args.images)


def print_summary(s):
    ref, f = s["reference"], s["final"]
    t = Table(title=f"{s['run']} — {s['status']}", box=box.ROUNDED)
    t.add_column("format")
    t.add_column("départ", justify="right")
    t.add_column("final", justify="right", style="bold")
    t.add_column("ac_fixed")
    for n in [n for n in NAMES if n in f["config"]]:
        I0, F0 = ref["config"][n]
        I, F = f["config"][n]
        t.add_row(n, str(I0 + F0), str(I + F), f"<{I + F}, {I}, {'true' if FMT[n][2] else 'false'}>")
    st = s.get("stats", {})
    saved, tot = st.get("img_saved", 0), st.get("img_total", 0)
    t.caption = (f"précision {ref['acc']:.2f} % → [bold]{f['acc']:.2f} %[/]   "
                 f"bits mem {ref['bits_mem']:.2f} → [bold]{f['bits_mem']:.2f}[/]   "
                 f"ops {ref['bits_ops']:.2f} → [bold]{f['bits_ops']:.2f}[/]\n"
                 f"{s['evaluations']} évaluations en {fmt_time(s['duration_s'])}, "
                 f"{st.get('stopped', 0)} coupées tôt, {st.get('killed', 0)} tuées, "
                 f"{st.get('rechecks', 0)} revérifiées, "
                 f"{100 * saved / max(1, saved + tot):.0f} % d'images économisées")
    console.print(t)
    try:
        stats = pass_stats(paths.RUNS / s["run"], ref["bits_mem"])
    except Exception:
        stats = []
    if len(stats) > 1:
        tp = Table(title="Gain par passe", box=box.SIMPLE_HEAD)
        for col in ("passe", "réductions", "bits moyens", "gain", "durée", "évaluations"):
            tp.add_column(col, justify="right")
        for st in stats:
            tp.add_row(str(st["pass"]), str(st["reductions"]), f"{st['bits_start']:.2f} → {st['bits_end']:.2f}",
                       f"[green]{st['gain']:+.2f}" if st["gain"] < 0 else f"{st['gain']:+.2f}",
                       fmt_time(st["t_end"] - st["t_start"]), str(st["evaluations"]))
        console.print(tp)
    console.print(f"  → [dim]{(paths.RUNS / s['run']).relative_to(paths.ROOT)}/[/]  "
                  "(config.hpp, plot.png, curves.png, history.jsonl)")


def cmd_list(args):
    runs = load_runs(k=args.k)
    sel = json.loads(paths.SELECTED_FILE.read_text()) if paths.SELECTED_FILE.exists() else []
    cur = sel[-1]["id"] if sel else None
    t = Table(title="Explorations", box=box.SIMPLE_HEAD)
    for c in ("run", "statut", "k", "images", "seuil", "graine", "P", "réf %", "final %", "bits mem",
              "bits ops", "évals", "coupées", "durée", "id final"):
        t.add_column(c, justify="left" if c in ("run", "statut") else "right")
    for s in runs:
        f = s["final"]
        mark = " [bold green]◀ sélectionnée" if f["id"] == cur else ""
        status = s["status"] + (f" ({s['variables_done']}/{s['variables_total']})"
                                if s["status"] != "terminé" and "variables_done" in s else "")
        t.add_row(s["run"], status, str(s["k"]), str(s["images"]), f"{s['threshold']:g}", str(s["seed"]),
                  str(s.get("parallel_vars", 1)), f"{s['reference']['acc']:.2f}", f"{f['acc']:.2f}",
                  f"{f['bits_mem']:.2f}", f"{f['bits_ops']:.2f}", str(s["evaluations"]),
                  str(s.get("stats", {}).get("stopped", "-")), fmt_time(s["duration_s"]), f["id"] + mark)
    console.print(t)


def cmd_show(args):
    d = find_run(args.run)
    if not d:
        sys.exit(f"Run introuvable : {args.run}")
    print_summary(json.loads((d / "summary.json").read_text()))


def cmd_pareto(args):
    pts = Cache().points(args.k, args.images, code_hash())
    key = f"bits_{args.metric}"
    t = Table(title=f"Front de Pareto — noyau {args.k}x{args.k}, {args.images} images", box=box.SIMPLE_HEAD)
    for c in ("id", "précision %", "bits mem", "bits ops", *NAMES):
        t.add_column(c, justify="right")
    for p in pareto(pts, key):
        t.add_row(p["id"], f"{p['acc']:.2f}", f"{p['bits_mem']:.2f}", f"{p['bits_ops']:.2f}",
                  *[str(width(p["config"], n)) for n in NAMES])
    t.caption = "colonnes des formats : W (bits totaux). Sélection : explore.py select <id>"
    console.print(t)


def cmd_plot(args):
    outs = [plot_all(args.k, args.images, args.metric, args.all_codes),
            plot_all(args.k, args.images, args.metric, args.all_codes, zoom=True)]
    cache = Cache()
    for s in load_runs(k=args.k, n=args.images):
        plot_run(paths.RUNS / s["run"], cache, args.metric)
        plot_run(paths.RUNS / s["run"], cache, args.metric, zoom=True)
        plot_formats(paths.RUNS / s["run"])
        plot_formats_pyramid(paths.RUNS / s["run"])
        plot_progress(paths.RUNS / s["run"])
    outs.append(plot_progress_all(args.k, args.images))
    # affichage à l'écran : uniquement ici (fil principal, aucun worker en cours)
    outs = [o for o in outs if o]
    if outs and os.environ.get("DISPLAY") and not args.no_show:
        import matplotlib.pyplot as plt
        for o in outs:
            plt.figure(figsize=(13, 7.5))
            plt.imshow(plt.imread(o))
            plt.axis("off")
            plt.tight_layout()
        plt.show()


def cmd_select(args):
    d = find_run(args.target)
    if d:
        s = json.loads((d / "summary.json").read_text())
        config, acc, k, n = s["final"]["config"], s["final"]["acc"], s["k"], s["images"]
        origin, pid = f"exploration {s['run']}", s["final"]["id"]
    else:
        m = [e for pid, e in Cache().data.items() if pid.startswith(args.target) and "acc" in e]
        if len(m) != 1:
            sys.exit(f"Aucun run ni point complet unique ne correspond à « {args.target} »")
        e = m[0]
        config, acc, k, n, origin, pid = e["config"], e["acc"], e["k"], e["n"], f"point {e['id']}", e["id"]
    origin += f" : {acc:.2f} % sur {n} images, noyau {k}x{k}"
    out = paths.RUNS / "selected_config.hpp"
    out.write_text(make_config_hpp(config, origin))
    sel = json.loads(paths.SELECTED_FILE.read_text()) if paths.SELECTED_FILE.exists() else []
    sel.append({"date": datetime.now().isoformat(timespec="seconds"), "source": origin, "id": pid,
                "acc": acc, "k": k, "images": n, "bits_mem": bits(config, k, "mem")[0],
                "bits_ops": bits(config, k, "ops")[0], "config": config, "applied": args.apply})
    paths.SELECTED_FILE.write_text(json.dumps(sel, indent=1))
    console.print(f"Sélection : [bold]{origin}[/]   bits mem {bits(config, k)[0]:.2f}")
    console.print(f"  config écrite dans [bold]{out.relative_to(paths.ROOT)}")
    if args.apply:
        shutil.copy(out, paths.CPP / "config.hpp")
        console.print("  [green]cpp/config.hpp remplacé[/] (ancienne version récupérable avec git)")
        console.print("  [yellow]avant la synthèse Catapult : make coeffs[/] (ROM cpp/coeffs_k*_raw.hpp dans les nouveaux formats)")
    flags = " ".join(f"-D{FMT[n][1]}_W={width(config, n)} -D{FMT[n][1]}_I={config[n][0]}" for n in NAMES if n in config)
    console.print(f"  ou sans toucher au code : [dim]cmake -DCMAKE_CXX_FLAGS=\"{flags}\" ..")


def main(doc=None):
    ap = argparse.ArgumentParser(description=doc or __doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="lance une ou plusieurs explorations")
    r.add_argument("--k", type=int, default=5, help="noyau des convolutions : 3 ou 5 (défaut 5)")
    r.add_argument("--images", type=int, default=1000, help="images par évaluation (défaut 1000)")
    r.add_argument("--batch", default="data_batch_1.bin", help="fichier CIFAR-10")
    r.add_argument("--threshold", type=float, default=1.0,
                   help="perte de précision tolérée en points de %% (défaut 1.0)")
    r.add_argument("--threshold-range", type=float, nargs=2, metavar=("MIN", "MAX"),
                   help="seuil tiré au hasard dans [MIN, MAX] pour chaque exploration")
    r.add_argument("--workers", type=int, default=os.cpu_count() or 4, help="évaluations en parallèle")
    r.add_argument("--parallel-vars", type=int, default=1,
                   help="descentes menées en même temps (cœurs partagés entre elles, défaut 1)")
    r.add_argument("--seed", type=int, help="graine de l'ordre aléatoire (défaut : au hasard)")
    r.add_argument("--runs", type=int, default=1, help="nombre d'explorations successives (graines différentes)")
    r.add_argument("--order", choices=("random", "fixed"), default="random", help="ordre des variables")
    r.add_argument("--passes", type=int, default=1, help="nombre de passes sur toutes les variables")
    r.add_argument("--start-F", type=int, default=12, help="bits fractionnaires de départ (défaut 12)")
    r.add_argument("--resume", action="store_true", help="reprend sans demander la session non terminée")
    r.add_argument("--new", action="store_true", help="nouvelle session même si une session identique existe")
    g = r.add_argument_group("arrêt anticipé et ordre des images")
    g.add_argument("--no-early-stop", dest="early_stop", action="store_false",
                   help="évalue toujours toutes les images")
    g.add_argument("--z", type=float, default=2.0,
                   help="prudence de l'arrêt anticipé (écarts-types, défaut 2 ; plus grand = coupe moins)")
    g.add_argument("--min-images", type=int, default=20, help="images minimum avant de pouvoir couper")
    g.add_argument("--no-reorder", dest="reorder", action="store_false",
                   help="garde l'ordre naturel des images")
    g.add_argument("--easy-frac", type=float, default=0.1,
                   help="part d'images très sûres intercalées au début (défaut 0.1)")
    g.add_argument("--easy-every", type=int, default=4, help="une image sûre toutes les N (défaut 4)")
    r.set_defaults(func=cmd_run)

    l = sub.add_parser("list", help="liste les explorations")
    l.add_argument("--k", type=int)
    l.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="détail d'une exploration")
    s.add_argument("run", help="nom (ou début du nom) du run")
    s.set_defaults(func=cmd_show)

    p = sub.add_parser("pareto", help="points Pareto-optimaux, tous runs confondus")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--images", type=int, default=1000)
    p.add_argument("--metric", choices=("mem", "ops"), default="mem")
    p.set_defaults(func=cmd_pareto)

    gp = sub.add_parser("plot", help="nuage de points de toutes les explorations")
    gp.add_argument("--k", type=int, default=5)
    gp.add_argument("--images", type=int, default=1000)
    gp.add_argument("--metric", choices=("mem", "ops"), default="mem")
    gp.add_argument("--all-codes", action="store_true", help="inclure les points d'anciennes versions du code C++")
    gp.add_argument("--no-show", action="store_true", help="n'ouvre pas de fenêtre, écrit seulement les PNG")
    gp.set_defaults(func=cmd_plot)

    c = sub.add_parser("select", help="sélectionne une configuration (run ou point du cache)")
    c.add_argument("target", help="nom de run ou id de point (début suffit)")
    c.add_argument("--apply", action="store_true", help="remplace cpp/config.hpp")
    c.set_defaults(func=cmd_select)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
