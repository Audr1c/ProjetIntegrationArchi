#!/usr/bin/env python3
"""Agrège les state.json de tous les runs. Par type de variable, un graphe :
abscisse = nb de bits de la variable (I rond plein, F carré creux), un point par
valeur prise ; ordonnée = bits moyens par valeur (métrique bits_mem du projet, pondérée par
le nb de valeurs stockées) en fin de run, moyennés sur les runs où la variable prend cette valeur ; taille du point = nb de runs.
Les points de séries différentes qui tombent sur la même abscisse sont décalés
horizontalement (autour de la valeur entière) pour rester tous visibles.

Usage : python3 bits_stats.py [--runs runs] [--out runs/bits_stats] [--max-bits 13]
  --max-bits B : ne garde que les runs finissant à moins de B bits moyens/valeur
                 (sortie par défaut : runs/bits_stats_lt<B>)
"""
import argparse, csv, json, re, sys
from collections import OrderedDict
from pathlib import Path

import matplotlib, matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explo.formats import bits  # même métrique que les graphes de progression


KS = {}


def load_runs(runs_dir):
    runs = OrderedDict()
    for st in sorted(Path(runs_dir).glob("*/state.json")):
        cfg = json.loads(st.read_text()).get("config")
        sm = st.parent / "summary.json"
        sj = json.loads(sm.read_text()) if sm.exists() else {}
        k = sj.get("k", 5)
        if sj.get("status", "terminé") != "terminé":
            continue  # run interrompu : config pas (ou peu) optimisée
        if cfg:
            runs[st.parent.name] = cfg
            KS[st.parent.name] = k
    return runs


def var_type(name):
    return re.sub(r"\d+$", "", name)  # ker1 -> ker, accfc -> accfc


def plot_type(ax, typ, names, pts):
    """pts[(var, part)] = {nb_bits: [total de bits du run, ...]}.
    Un point par valeur prise par la variable ; y = total de bits moyen des
    runs où la variable prend cette valeur ; taille = nb de runs concernés."""
    cols = plt.cm.tab10.colors
    series = [(n, p) for n in names for p in "IF"]
    # décalage horizontal des séries qui partagent une abscisse
    at_x = {}
    for key in series:
        for x in pts[key]:
            at_x.setdefault(x, []).append(key)
    off = {}
    for x, keys in at_x.items():
        m = len(keys); step = min(.15, .7 / m)
        for j, key in enumerate(keys):
            off[(key, x)] = (j - (m - 1) / 2) * step
    for g, n in enumerate(names):
        for part, mk, fill in (("I", "o", True), ("F", "s", False)):
            d = pts[(n, part)]
            xs0 = sorted(d)
            xs = [x + off[((n, part), x)] for x in xs0]
            ys = [np.mean(d[x]) for x in xs0]
            sz = [18 + 10 * len(d[x]) for x in xs0]
            ax.scatter(xs, ys, s=sz, marker=mk, color=cols[g], alpha=.8,
                       facecolors=cols[g] if fill else "none",
                       linewidths=1.5, label=f"{n}.{part}")
            ax.plot(xs, ys, color=cols[g], alpha=.25, lw=1,
                    ls="-" if fill else "--")
    ax.set_xlabel("nombre de bits de la variable")
    ax.set_ylabel("bits moyens par valeur (fin de run)")
    ax.set_title(typ); ax.grid(alpha=.3)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.legend(fontsize=7, ncol=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-bits", type=float, default=None,
                    help="ne garder que les runs finissant sous ce nb de bits moyens/valeur")
    a = ap.parse_args()
    runs = load_runs(a.runs)
    total = {r: bits(c, KS[r], "mem")[0] for r, c in runs.items()}  # bits moyens/valeur
    if a.max_bits is not None:
        runs = OrderedDict((r, c) for r, c in runs.items() if total[r] < a.max_bits)
    if not runs:
        raise SystemExit(f"aucun run retenu dans {a.runs}")
    out = Path(a.out or ("runs/bits_stats" if a.max_bits is None
                         else f"runs/bits_stats_lt{a.max_bits:g}"))
    out.mkdir(parents=True, exist_ok=True)
    names = list(OrderedDict.fromkeys(n for c in runs.values() for n in c))
    pts = {(n, p): {} for n in names for p in "IF"}
    data = {n: ([], []) for n in names}
    with open(out / "bits_final.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["run", "var", "I", "F", "total"])  # total = I+F de la variable
        for r, cfg in runs.items():
            for n in names:
                if n not in cfg:  # ancien run sans cette variable
                    continue
                i, fr = cfg[n]
                data[n][0].append(i); data[n][1].append(fr)
                pts[(n, "I")].setdefault(i, []).append(total[r])
                pts[(n, "F")].setdefault(fr, []).append(total[r])
                w.writerow([r, n, i, fr, i + fr])
    with open(out / "bits_mean.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["var", "I_mean", "I_std", "F_mean", "F_std", "n_runs"])
        for n in names:
            I, F = map(np.array, data[n])
            w.writerow([n, f"{I.mean():.3f}", f"{I.std():.3f}",
                        f"{F.mean():.3f}", f"{F.std():.3f}", len(I)])

    types = OrderedDict()
    for n in names:
        types.setdefault(var_type(n), []).append(n)

    for t, ns in types.items():
        fig, ax = plt.subplots(figsize=(7, 4.5))
        plot_type(ax, t, ns, pts)
        fig.tight_layout(); fig.savefig(out / f"bits_{t}.png", dpi=130)
        plt.close(fig)

    cols = 3; rows = -(-len(types) // cols)
    fig, axs = plt.subplots(rows, cols, figsize=(5 * cols, 3.8 * rows))
    axs = axs.ravel()
    for ax, (t, ns) in zip(axs, types.items()):
        plot_type(ax, t, ns, pts)
    for ax in axs[len(types):]:
        ax.axis("off")
    filt = "" if a.max_bits is None else f", runs < {a.max_bits:g} bits"
    fig.suptitle(f"Bits moyens par valeur (fin de run) selon le nb de bits de chaque variable ({len(runs)} runs{filt})")
    fig.tight_layout(); fig.savefig(out / "bits_all.png", dpi=130)
    print(f"{len(runs)} runs, {len(types)} types -> {out}/")


if __name__ == "__main__":
    main()
