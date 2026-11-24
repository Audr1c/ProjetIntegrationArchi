#!/usr/bin/env python3
"""Efficacité des pas de descente des runs déjà faits : bits gagnés × poids / précision perdue.

Pour chaque candidat évalué complètement (statut ok / ko) d'un run, on compare à la
configuration dont il est parti (même « version » de la config courante) :
    Δbits = bits moyens/valeur de la base − ceux du candidat
            (= bits retirés à la variable × poids de la variable dans la métrique)
    Δacc  = précision de la base − précision du candidat, en points (sur les mêmes images)
    E     = Δbits / Δacc  en bits/valeur par point de précision perdu ; E = ∞ si Δacc ≤ 0 (pas gratuit)

Le critère envisagé pour la suite : n'accepter un pas qui coûte de la précision que si E ≥ s.
Ce script ne rejoue pas les runs : il montre comment la marge a été dépensée et ce qu'un
tel critère aurait refusé.

Sorties (dans --out, par défaut runs/efficiency/) :
    steps.csv              tous les candidats complets : run, pas, variable, Δbits, Δacc, E, gardé ?
    efficiency_steps.png   nuage Δacc / Δbits de tous les candidats, droites d'iso-efficacité
    efficiency_paths.png   chemin suivi par chaque run : perte cumulée / bits, pas coûteux annotés
    efficiency_runs.png    marge dépensée par classe de poids, et bits finaux selon le rendement
                           de la marge (bits gagnés par les pas coûteux / précision perdue)
et deux tableaux dans le terminal (par variable, par run).

Usage : python3 efficiency.py [-s 1] [--metric mem|ops] [-k 5] [-n 1000] [--runs runs] [--out ...]
"""
import argparse, csv, json, math, sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explo.formats import NAMES, usage_counts

console = Console()

# classes de poids (part de la variable dans la métrique)
CLASSES = [("lourde", 0.05, "tab:red"), ("moyenne", 0.005, "tab:orange"), ("légère", 0.0, "tab:blue")]


def weight_class(w):
    return next(c for c in CLASSES if w >= c[1])


def weights(k, metric):
    idx = 0 if metric == "mem" else 1
    cnt = usage_counts(k)
    tot = sum(v[idx] for v in cnt.values())
    return {n: cnt[n][idx] / tot for n in NAMES}


def eff(d_bits, d_acc):
    return math.inf if d_acc <= 0 else d_bits / d_acc


# ============================================================
# Lecture des runs
# ============================================================

def load_run(d, k, n, metric, W):
    """Retourne None si le run ne convient pas, sinon {name, ref_acc, threshold, steps, path, final}."""
    try:
        params = json.loads((d / "params.json").read_text())
        summary = json.loads((d / "summary.json").read_text())
    except FileNotFoundError:
        return None
    if summary.get("status") != "terminé" or params.get("k") != k or params.get("images") != n:
        return None
    lines = [json.loads(l) for l in open(d / "history.jsonl") if l.strip()]
    ref = next((e for e in lines if e.get("status") == "ref"), None)
    if ref is None or any(v not in ref["config"] for v in NAMES):
        return None                      # ancien run (sans accumulateurs) : pas comparable
    key = f"bits_{metric}"
    kept = [e for e in lines if e.get("event") == "kept"]
    # base de la version v : référence (v = 0) ou état après le v-ième pas retenu
    bases = [(ref["acc"], ref[key])] + [(e["acc"], e[key]) for e in kept]
    kept_ids = {e["id"] for e in kept}

    steps = []
    for e in lines:
        if e.get("status") not in ("ok", "ko") or e.get("acc") is None or "version" not in e:
            continue
        v = e["version"]
        if v >= len(bases):
            continue
        b_acc, b_bits = bases[v]
        name, dim = e["var"].split(".")
        d_bits, d_acc = b_bits - e[key], b_acc - e["acc"]
        steps.append(dict(run=d.name, pass_no=e["pass"], var=e["var"], name=name, dim=dim,
                          value=e["value"], version=v, status=e["status"], kept=e["id"] in kept_ids,
                          acc=e["acc"], d_bits=d_bits, d_acc=d_acc, E=eff(d_bits, d_acc), weight=W[name]))

    # chemin réellement suivi : pas retenus successifs
    path, (p_acc, p_bits) = [], bases[0]
    for i, e in enumerate(kept):
        name = e["var"].split(".")[0]
        d_bits, d_acc = p_bits - e[key], p_acc - e["acc"]
        path.append(dict(i=i + 1, var=e["var"], name=name, frm=e["from"], value=e["value"], acc=e["acc"],
                         bits=e[key], d_bits=d_bits, d_acc=d_acc, E=eff(d_bits, d_acc), weight=W[name]))
        p_acc, p_bits = e["acc"], e[key]
    return dict(name=d.name, short=d.name.rsplit("_", 1)[-1], ref_acc=ref["acc"], ref_bits=ref[key],
                threshold=params["threshold"], steps=steps, path=path,
                final=path[-1]["bits"] if path else ref[key])


# ============================================================
# Graphes
# ============================================================

def iso_lines(ax, s_list, s_crit, xmax):
    xs = np.linspace(0.01, xmax, 200)
    for s in s_list:
        crit = s == s_crit
        ax.plot(xs, s * xs, color="k", lw=1.2 if crit else .6, ls="-" if crit else ":", alpha=.6 if crit else .4)
        ax.annotate(f"E={s:g}" + (" (s)" if crit else ""), (xmax, s * xmax), fontsize=7, alpha=.7,
                    xytext=(2, 0), textcoords="offset points", va="center")


def plot_steps(runs, s, metric, out):
    steps = [st for r in runs for st in r["steps"]]
    fig, ax = plt.subplots(figsize=(10, 6.5))
    for cname, _, col in CLASSES:
        sel = [st for st in steps if weight_class(st["weight"])[0] == cname]
        for kind, mk, kw in (("ko", "x", dict(s=14, alpha=.35, linewidths=.8)),
                             ("ok", "o", dict(s=14, alpha=.35, facecolors="none", linewidths=.8)),
                             ("kept", "o", dict(s=40, alpha=.9, edgecolors="k", linewidths=.6))):
            pts = [st for st in sel if (st["kept"] if kind == "kept" else (st["status"] == kind and not st["kept"]))]
            if not pts:
                continue
            x = np.clip([p["d_acc"] for p in pts], -1, 3)
            y = np.clip([p["d_bits"] for p in pts], 1e-5, None)
            lab = {"kept": "retenu", "ok": "accepté puis dépassé", "ko": "refusé"}[kind]
            ax.scatter(x, y, marker=mk, color=col, label=f"{cname} — {lab}", **kw)
    iso_lines(ax, [0.5, 1, 2, 5, 10, 20], s, 3)
    ax.axvline(0, color="k", lw=.8)
    ax.set_yscale("log")
    ax.set_xlim(-1.05, 3.4)
    ax.set_xlabel("Δacc = précision perdue par rapport à la base (points, borné à [-1, 3])")
    ax.set_ylabel(f"Δbits = bits moyens/valeur gagnés ({metric})  [= bits retirés × poids]")
    ax.set_title(f"Efficacité des pas : {len(steps)} candidats complets, {len(runs)} runs\n"
                 "à gauche de 0 : pas gratuits ; au-dessus de la droite E=s : pas acceptés par le critère")
    ax.grid(alpha=.3, which="both")
    ax.legend(fontsize=7, loc="lower right", ncol=1)
    fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig)


def plot_paths(runs, s, metric, out):
    runs = sorted(runs, key=lambda r: r["final"])
    cols = 4; rows = -(-len(runs) // cols)
    fig, axs = plt.subplots(rows, cols, figsize=(4.2 * cols, 3.4 * rows), sharex=True, sharey=True)
    axs = np.atleast_1d(axs).ravel()
    for ax, r in zip(axs, runs):
        loss = [0.0] + [r["ref_acc"] - p["acc"] for p in r["path"]]
        bts = [r["ref_bits"]] + [p["bits"] for p in r["path"]]
        ax.plot(loss, bts, color="0.6", lw=1, drawstyle="default", zorder=1)
        for p, x, y in zip(r["path"], loss[1:], bts[1:]):
            col = weight_class(p["weight"])[2]
            ax.scatter(x, y, s=14, color=col, zorder=2)
            if p["d_acc"] >= 0.2:                 # pas qui ont coûté de la marge : annotés
                ax.annotate(f"{p['var']}{' ✗' if p['E'] < s else ''}", (x, y), fontsize=6.5,
                            xytext=(3, 2), textcoords="offset points", color=col)
        ax.axvline(r["threshold"], color="k", ls=":", lw=.8)
        ax.set_title(f"{r['short']} : {r['final']:.2f} bits", fontsize=9)
        ax.grid(alpha=.3)
    for ax in axs[len(runs):]:
        ax.axis("off")
    for ax in axs[::cols]:
        ax.set_ylabel(f"bits/valeur ({metric})")
    for ax in axs[-cols:]:
        ax.set_xlabel("perte cumulée / référence (pts)")
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=f"variable {n}") for n, _, c in CLASSES]
    fig.legend(handles=handles, loc="upper right", fontsize=8)
    fig.suptitle("Chemin suivi par chaque run (du meilleur au pire) : une chute verticale = bits gratuits, "
                 f"un pas vers la droite = marge dépensée\nannotés : pas coûtant ≥ 0,2 pt ; ✗ = refusé par le critère E ≥ {s:g}",
                 fontsize=10)
    fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig)


def run_stats(r, s):
    """Pas retenus coûteux (Δacc > 0) : marge par classe de poids, totale, sur E < s, et bits obtenus."""
    spent = {c[0]: 0.0 for c in CLASSES}
    bad = gained = 0.0
    n_bad = 0
    for p in r["path"]:
        if p["d_acc"] > 0:
            spent[weight_class(p["weight"])[0]] += p["d_acc"]
            gained += p["d_bits"]
            if p["E"] < s:
                bad += p["d_acc"]; n_bad += 1
    tot = sum(spent.values())
    return dict(spent=spent, tot=tot, bad=bad, n_bad=n_bad, gained=gained,
                yield_=gained / tot if tot > 0 else math.inf)


def plot_runs(runs, s, out):
    runs = sorted(runs, key=lambda r: r["final"])
    st = [run_stats(r, s) for r in runs]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.5), gridspec_kw=dict(width_ratios=[1.3, 1]))
    left = np.zeros(len(runs))
    ylab = [f"{r['short']}  ({r['final']:.2f})" for r in runs]
    for cname, _, col in CLASSES:
        v = np.array([x["spent"][cname] for x in st])
        a1.barh(ylab, v, left=left, color=col, label=f"variables {cname}s")
        left += v
    a1.invert_yaxis()
    a1.set_xlabel("pertes brutes des pas retenus coûteux (somme des Δacc > 0, pts)")
    a1.set_title("Où est partie la marge ? (runs du meilleur au pire, bits finaux entre parenthèses)", fontsize=10)
    a1.legend(fontsize=8); a1.grid(alpha=.3, axis="x")

    # rendement de la marge : bits gagnés par les pas coûteux / pertes de ces pas
    x = [x["yield_"] for x in st]
    y = [r["final"] for r in runs]
    a2.scatter(x, y, s=40)
    for xi, yi, r in zip(x, y, runs):
        a2.annotate(r["short"], (xi, yi), fontsize=7, xytext=(3, 2), textcoords="offset points")
    ok = [(xi, yi) for xi, yi in zip(x, y) if math.isfinite(xi)]
    title = "Bits finaux selon le rendement de la marge dépensée"
    if len(ok) > 2:
        title += f"  (corr = {np.corrcoef(*zip(*ok))[0, 1]:+.2f})"
    a2.set_title(title, fontsize=10)
    a2.set_xlabel("rendement = Σ Δbits / Σ Δacc des pas retenus coûteux (bits/valeur par point)")
    a2.set_ylabel("bits moyens/valeur en fin de run")
    a2.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(out, dpi=130); plt.close(fig)


# ============================================================
# Tableaux
# ============================================================

def fmt_e(e):
    return "∞" if e == math.inf else f"{e:.2f}"


def table_vars(runs, W):
    agg = defaultdict(lambda: dict(n=0, n_cost=0, spent=0.0, gained=0.0, gained_cost=0.0))
    for r in runs:
        for p in r["path"]:
            a = agg[p["name"]]
            a["n"] += 1; a["gained"] += p["d_bits"]
            if p["d_acc"] > 0:
                a["n_cost"] += 1; a["spent"] += p["d_acc"]; a["gained_cost"] += p["d_bits"]
    t = Table(title="Pas retenus, par variable (tous runs)", title_justify="left")
    for c in ("variable", "poids", "pas", "dont coûteux", "marge dépensée", "bits gagnés",
              "dont par pas coûteux", "E des pas coûteux"):
        t.add_column(c, justify="left" if c == "variable" else "right")
    for n in sorted(agg, key=lambda n: -W[n]):
        a = agg[n]
        e = a["gained_cost"] / a["spent"] if a["spent"] > 0 else math.inf
        t.add_row(n, f"{100 * W[n]:.2f} %", str(a["n"]), str(a["n_cost"]), f"{a['spent']:.1f} pt",
                  f"{a['gained']:.3f}", f"{a['gained_cost']:.3f}", fmt_e(e))
    console.print(t)


def table_runs(runs, s):
    t = Table(title=f"Par run (pas retenus ; critère s = {s:g} bits/valeur par point)", title_justify="left")
    for c in ("run", "bits finaux", "pertes brutes", "lourdes", "moyennes", "légères", "rendement",
              f"pas E < {s:g}", f"pertes sur E < {s:g}", "plus gros pas refusés par le critère"):
        t.add_column(c, justify="left" if c in ("run", "plus gros pas refusés par le critère") else "right")
    for r in sorted(runs, key=lambda r: r["final"]):
        x = run_stats(r, s)
        bad = sorted((p for p in r["path"] if p["d_acc"] > 0 and p["E"] < s), key=lambda p: -p["d_acc"])
        refused = ", ".join(f"{p['var']} {p['frm']}→{p['value']} ({p['d_acc']:+.1f} pt)" for p in bad[:3])
        if len(bad) > 3:
            refused += f" +{len(bad) - 3}"
        t.add_row(r["short"], f"{r['final']:.2f}", f"{x['tot']:.1f}", *(f"{x['spent'][c[0]]:.1f}" for c in CLASSES),
                  fmt_e(x["yield_"]), str(x["n_bad"]), f"{x['bad']:.1f}", refused or "—")
    console.print(t)
    console.print("[dim]pertes brutes : somme des Δacc > 0 des pas retenus (> seuil car des pas suivants "
                  "regagnent des images) ; rendement : bits gagnés par ces pas / pertes brutes")


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-s", type=float, default=1.0, help="seuil d'efficacité E (bits/valeur par point), défaut 1")
    ap.add_argument("--metric", choices=("mem", "ops"), default="mem")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("-n", type=int, default=1000, help="nb d'images des runs à prendre (défaut 1000)")
    ap.add_argument("--runs", default=str(here / "runs"))
    ap.add_argument("--out", default=str(here / "runs" / "efficiency"))
    a = ap.parse_args()

    W = weights(a.k, a.metric)
    runs = [r for d in sorted(Path(a.runs).iterdir()) if d.is_dir()
            for r in [load_run(d, a.k, a.n, a.metric, W)] if r]
    if not runs:
        raise SystemExit("aucun run terminé compatible (k, n, avec accumulateurs)")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    with open(out / "steps.csv", "w", newline="") as f:
        cols = ["run", "pass_no", "version", "var", "value", "status", "kept", "weight", "acc", "d_bits", "d_acc", "E"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in runs:
            w.writerows(r["steps"])

    plot_steps(runs, a.s, a.metric, out / "efficiency_steps.png")
    plot_paths(runs, a.s, a.metric, out / "efficiency_paths.png")
    plot_runs(runs, a.s, out / "efficiency_runs.png")
    table_vars(runs, W)
    table_runs(runs, a.s)
    console.print(f"{len(runs)} runs, {sum(len(r['steps']) for r in runs)} candidats complets -> {out}/")


if __name__ == "__main__":
    main()
