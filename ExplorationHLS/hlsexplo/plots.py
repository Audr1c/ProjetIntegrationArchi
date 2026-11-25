"""
Graphes PNG d'un run (matplotlib sans interface : Figure + Agg, utilisable depuis un thread).

    pareto.png     toutes les évaluations dans le plan latence / coût, chemin suivi fléché,
                   cible en pointillés, zone « trop lent » grisée ; ronds creux = prédictions du modèle
    evolution.png  pour chaque pas retenu : latence empilée par bloc (cible en pointillés) et
                   ressources en % du budget (BRAM, DSP, LUT), slack en légende
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from .space import BLOCKS, SHORT
from .store import read_history

COLORS = {"layer1": "#17becf", "layer2": "#9467bd", "layer3": "#e6b800", "dense": "#2ca02c"}
DECISION_STYLE = {   # décision -> (couleur, marqueur, légende)
    "kept": ("#2ca02c", "*", "retenu"), "ref": ("#1f77b4", "D", "référence"),
    "other": ("#98df8a", "o", "valide, autre choix"), "slow": ("#ff7f0e", "o", "valide, gain trop faible"), "nogain": ("#7f7f7f", "o", "valide, pas moins cher"),
    "target": ("#ff7f0e", "v", "latence > cible"), "slower": ("#ff7f0e", "v", "repli trop lent"), "timing": ("#d62728", "x", "timing raté"),
    "budget": ("#d62728", "s", "budget dépassé"), "refused": ("#e377c2", "P", "directive refusée"),
}


def _ok(h):
    return h["result"].get("status") == "ok" and h["result"].get("latency")


def _figure(*args, **kw):
    from matplotlib.figure import Figure
    return Figure(*args, **kw)


def plot_pareto(run: Path, hist: list, params: dict) -> Path:
    L = params["limits"]
    fig = _figure(figsize=(11, 6.5))
    ax = fig.subplots()
    target = L["target_cycles"] / 1e6
    lats = [h["result"]["latency"] / 1e6 for h in hist if _ok(h)]
    if not lats:
        return None
    x_hi = max(lats + [target]) * 1.4
    x_lo = min(lats + [target]) / 1.4
    ax.axvspan(target, x_hi, color="#f2dede", alpha=0.5, zorder=0, label="trop lent (> cible)")
    ax.axvline(target, ls="--", c="#d62728", lw=1.2)
    ax.text(target, 0.01, f" cible {target:g} M", transform=ax.get_xaxis_transform(), va="bottom", color="#d62728")

    # prédictions du modèle pour les candidats écartés sans synthèse
    sk = [h for h in hist if h["decision"] == "skipped" and h["predicted"].get("latency")]
    if sk:
        ax.scatter([h["predicted"]["latency"] / 1e6 for h in sk], [h["predicted"]["cost"] for h in sk],
                   facecolors="none", edgecolors="#aaaaaa", s=40, label="écarté par le modèle (prédit)", zorder=2)
    for dec, (c, m, lab) in DECISION_STYLE.items():
        pts = [h for h in hist if h["decision"] == dec and _ok(h)]
        if pts:
            ax.scatter([h["result"]["latency"] / 1e6 for h in pts], [h["cost"] for h in pts], c=c, marker=m,
                       s=150 if m == "*" else 45, label=lab, zorder=4, edgecolors="k" if m == "*" else None,
                       linewidths=0.5)
    path = [h for h in hist if h["decision"] in ("ref", "kept") and _ok(h)]
    for i, (a, b) in enumerate(zip(path, path[1:])):
        ax.annotate("", xy=(b["result"]["latency"] / 1e6, b["cost"]), xytext=(a["result"]["latency"] / 1e6, a["cost"]),
                    arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=1.5), zorder=3)
    for i, h in enumerate(path):
        txt = "réf" if h["decision"] == "ref" else f"{i}. {SHORT.get(h['block'], h['block'])} {h['move']}"
        ax.annotate(txt, (h["result"]["latency"] / 1e6, h["cost"]), xytext=(6, 6), textcoords="offset points",
                    fontsize=8, color="#225522")
    ax.set_xscale("log")
    ax.set_xlim(x_lo, x_hi)
    ax.set_xlabel("latence (millions de cycles par image, échelle log)")
    ax.set_ylabel("coût = BRAM/budget + DSP/budget + LUT/budget")
    ax.grid(alpha=0.3, which="both")
    clk = params.get("clock_ns", 10.0)
    import numpy as np
    inv = lambda v: 1e3 / (np.maximum(v, 1e-9) * clk)      # M cycles <-> images/s (involution)
    sec = ax.secondary_xaxis("top", functions=(inv, inv))
    sec.set_xlabel("images par seconde")
    from matplotlib.ticker import FuncFormatter
    plain = FuncFormatter(lambda v, _: f"{v:g}")
    for a in (ax.xaxis, sec.xaxis):
        a.set_major_formatter(plain)
        a.set_minor_formatter(plain)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"{run.name} — {params['backend']}", fontsize=10)
    fig.tight_layout()
    out = run / "pareto.png"
    fig.savefig(out, dpi=130)
    return out


def plot_evolution(run: Path, hist: list, params: dict) -> Path:
    L = params["limits"]
    path = [h for h in hist if h["decision"] in ("ref", "kept") and _ok(h)]
    if not path:
        return None
    fig = _figure(figsize=(max(8, 1.3 * len(path) + 4), 8))
    ax, ax2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    xs = range(len(path))
    bottom = [0.0] * len(path)
    for b in BLOCKS:
        v = [(h["result"].get("blocks") or {}).get(b, 0) / 1e6 for h in path]
        ax.bar(xs, v, bottom=bottom, color=COLORS[b], label=SHORT[b] + " (" + b + ")", edgecolor="white")
        bottom = [x + y for x, y in zip(bottom, v)]
    thr = [(h["result"].get("throughput") or 0) / 1e6 for h in path]
    ax.plot(list(xs), thr, "k_", markersize=40, markeredgewidth=2.5, label="débit (bloc le plus lent)")
    for x, h in zip(xs, path):
        ax.text(x, h["result"]["latency"] / 1e6, f"{h['result']['latency'] / 1e6:.1f} M", ha="center", va="bottom",
                fontsize=8)
    ax.axhline(L["target_cycles"] / 1e6, ls="--", c="#d62728", lw=1.2, label="cible")
    ax.set_ylabel("latence (M cycles)")
    ax.legend(fontsize=8, ncol=5, loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    for key, name, c in (("bram", "BRAM18", "#8c564b"), ("dsp", "DSP", "#1f77b4"), ("lut", "LUT", "#ff7f0e")):
        ax2.plot(xs, [100 * (h["result"].get(key) or 0) / L[key] for h in path], marker="o", c=c, label=name)
    ax2.axhline(100, ls="--", c="#d62728", lw=1.2, label="budget")
    ax2.set_ylabel("% du budget")
    ax2.grid(alpha=0.3)
    ax2.legend(fontsize=8, ncol=4)
    labels = ["réf"] + [f"{SHORT.get(h['block'], h['block'])}\n" + textwrap.fill(h["move"], 18) for h in path[1:]]
    slack = [h["result"].get("slack") for h in path]
    labels = [f"{l}\nslack {s:+.2f}" if s is not None else l for l, s in zip(labels, slack)]
    ax2.set_xticks(list(xs))
    ax2.set_xticklabels(labels, fontsize=7)
    fig.suptitle(f"{run.name} — chemin retenu", fontsize=10)
    fig.tight_layout()
    out = run / "evolution.png"
    fig.savefig(out, dpi=130)
    return out


def plot_run(run: Path) -> list:
    """Regénère les graphes d'un run ; [] si matplotlib manque (école sans matplotlib)."""
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return []
    params = json.loads((run / "params.json").read_text())
    hist = read_history(run)
    return [p for p in (plot_pareto(run, hist, params), plot_evolution(run, hist, params)) if p]
