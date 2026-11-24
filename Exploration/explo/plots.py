"""Graphes (matplotlib sans interface : objets Figure, utilisables depuis n'importe quel thread)."""

import json

import matplotlib
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from . import paths
from .cache import Cache, load_runs
from .dashboard import console
from .formats import NAMES, code_hash, usage_counts
from .monitor import PairedMonitor
from .formats import unpack

# Les figures sont des objets Figure (backend Agg) : pas de pyplot, pas de Tk,
# rien de global à fermer -> pas de crash depuis un thread ni de figure oubliée en mémoire.


def tab10():
    """Palette « tab10 ». matplotlib.colormaps n'existe qu'à partir de matplotlib 3.5 (Python 3.6
    plafonne à 3.3.4), et cm.get_cmap a été retiré en 3.9 : on essaie l'un puis l'autre."""
    try:
        return matplotlib.colormaps["tab10"]
    except AttributeError:
        from matplotlib import cm
        return cm.get_cmap("tab10")


# ============================================================
# Graphes
# ============================================================

def pareto(points, key):
    """Front de Pareto : précision max pour un nombre de bits donné."""
    front, best = [], -1
    for p in sorted(points, key=lambda p: (p[key], -p["acc"])):
        if p["acc"] > best:
            front.append(p)
            best = p["acc"]
    return front


def _axes(ax, k, metric):
    cnt = usage_counts(k)
    n_tot = sum(c[0 if metric == "mem" else 1] for c in cnt.values())
    ax.set_xlabel(f"bits moyens par valeur, pondérés par {'le stockage' if metric == 'mem' else 'les accès'}")
    ax.set_ylabel("précision (%)")
    ax.grid(alpha=0.3)
    unit, div = ("Kibit", 1024) if metric == "mem" else ("Gbit", 1e9)
    sec = ax.secondary_xaxis("top", functions=(lambda x: x * n_tot / div, lambda y: y * div / n_tot))
    sec.set_xlabel(f"total ({unit} {'stockés' if metric == 'mem' else 'lus par image'})")


def _read_history(run_dir):
    f = run_dir / "history.jsonl"
    if not f.exists():
        return []
    return [h for h in (json.loads(l) for l in f.read_text().splitlines() if l) if "event" not in h]


def _zoom(ax, pts, y_lo, y_hi):
    """Recadre sur la bande de précision [y_lo, y_hi] ; pts = [(x, y)] pour choisir l'axe x."""
    ax.set_ylim(y_lo, y_hi)
    xs = [x for x, y in pts if y_lo <= y <= y_hi]
    if xs:
        pad = max(0.05, 0.04 * (max(xs) - min(xs)))
        ax.set_xlim(min(xs) - pad, max(xs) + pad)


def plot_run(run_dir, cache, metric="mem", zoom=False):
    s = json.loads((run_dir / "summary.json").read_text())
    hist = _read_history(run_dir)
    key = f"bits_{metric}"
    ref_acc, n = s["reference"]["acc"], s["images"]
    fig = Figure(figsize=(11, 6.5))
    ax = fig.subplots()

    others = cache.points(s["k"], n, s["code"])
    if others:
        ax.scatter([p[key] for p in others], [p["acc"] for p in others], s=10, c="lightgray",
                   label="autres explorations", zorder=1)
    for st, c, m, lab in (("ko", "tab:red", "x", "refusé (sous le seuil)"),
                          ("ok", "tab:blue", "o", "accepté")):
        pts = [h for h in hist if h["status"] == st and h["acc"] is not None]
        if pts:
            ax.scatter([h[key] for h in pts], [h["acc"] for h in pts], s=22, c=c, marker=m,
                       label=lab, zorder=3, alpha=0.8)
    # coupés tôt : on place la borne haute de leur précision finale
    cut = [h for h in hist if h["status"] == "stopped" and h.get("min_loss") is not None]
    if cut:
        ax.scatter([h[key] for h in cut], [max(0, ref_acc - 100 * h["min_loss"] / n) for h in cut], s=26,
                   c="tab:orange", marker="v", label="coupé tôt (précision finale ≤)", zorder=3, alpha=0.8)
    if s["path"]:
        ax.scatter([p[key] for p in s["path"]], [p["acc"] for p in s["path"]], s=36, c="tab:green",
                   label="retenu", zorder=4)
    path = [(s["reference"][key], ref_acc)] + [(p[key], p["acc"]) for p in s["path"]]
    ax.plot(*zip(*path), "-", c="tab:green", lw=1, alpha=0.6, zorder=2)
    ax.axhline(ref_acc, c="tab:cyan", ls="--", lw=1, label=f"référence {ref_acc:.2f} %")
    ax.axhline(ref_acc - s["threshold"], c="tab:orange", ls=":", lw=1, label=f"seuil −{s['threshold']} pt")
    f = s["final"]
    ax.scatter([f[key]], [f["acc"]], s=220, marker="*", c="gold", edgecolors="k", zorder=5,
               label=f"final {f['acc']:.2f} % / {f[key]:.2f} b")
    accs = [h["acc"] for h in hist if h["acc"] is not None] + [ref_acc]
    _axes(ax, s["k"], metric)
    st = s.get("stats", {})
    title = (f"{s['run']}  ({s['status']}, {s['evaluations']} évaluations, "
             f"{st.get('stopped', 0)} coupées tôt)")
    if zoom:
        # partie haute : autour de la référence et du seuil, avec le nom de chaque réduction retenue
        band = max(3 * s["threshold"], 2.0)
        pts = [(h[key], h["acc"]) for h in hist if h["acc"] is not None]
        _zoom(ax, pts + [(f[key], f["acc"])], ref_acc - band, max(accs) + 0.4)
        for p in s["path"]:
            ax.annotate(f"{p['var']}={p['value']}", (p[key], p["acc"]), fontsize=6, alpha=0.8,
                        xytext=(3, 4), textcoords="offset points", rotation=30)
        title += " — zoom sur la partie haute"
    else:
        ax.set_ylim(max(min(accs) - 2, 0), max(accs) + 1.5)
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    name = "plot" + ("" if metric == "mem" else f"_{metric}") + ("_zoom" if zoom else "")
    fig.savefig(run_dir / f"{name}.png", dpi=120)


def plot_formats(run_dir):
    """Barres des formats : départ (contour) et final (entiers + fraction), avec le gain en bits."""
    s = json.loads((run_dir / "summary.json").read_text())
    start, final = s["reference"]["config"], s["final"]["config"]
    fig = Figure(figsize=(10, 6.5))
    ax = fig.subplots()
    names = [n for n in NAMES if n in final]
    ys = range(len(names))[::-1]
    for y, n in zip(ys, names):
        I0, F0 = start[n]
        I, F = final[n]
        ax.barh(y, I0 + F0, color="none", edgecolor="gray", ls="--", lw=0.8)
        ax.barh(y, max(I, 0), color="tab:cyan", label="bits entiers (I)" if y == ys[0] else None)
        ax.barh(y, I + F - max(I, 0), left=max(I, 0), color="tab:green",
                label="bits fractionnaires" if y == ys[0] else None)
        ax.text(I0 + F0 + 0.3, y, f"{I0 + F0} → {I + F}  <{I + F},{I}>", va="center", fontsize=8)
    handles, _ = ax.get_legend_handles_labels()
    handles.append(Patch(facecolor="none", edgecolor="gray", ls="--", label="départ"))
    ax.set_yticks(list(ys), names)
    for lab in ax.get_yticklabels():
        if lab.get_text().startswith("acc"):
            lab.set_fontstyle("italic")
    ax.set_xlabel("bits")
    ax.set_xlim(0, max(sum(v) for v in start.values()) + 8)
    ax.grid(axis="x", alpha=0.3)
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    ax.set_title(f"{s['run']} — formats : {s['reference']['bits_mem']:.2f} → "
                 f"{s['final']['bits_mem']:.2f} bits moyens ({s['final']['acc']:.2f} %)")
    fig.tight_layout()
    fig.savefig(run_dir / "formats.png", dpi=120)


def plot_curves(run_dir, ref_seq, threshold, z, min_images):
    """Écart cumulé à la référence, image par image : où chaque candidat décroche."""
    hist = [h for h in _read_history(run_dir) if h.get("seq") and h["status"] in ("ok", "ko", "stopped")]
    n = len(ref_seq)
    mon = PairedMonitor(ref_seq, threshold, z, min_images)
    fig = Figure(figsize=(11, 6))
    ax = fig.subplots()
    colors = {"ok": "tab:blue", "ko": "tab:red", "stopped": "tab:orange"}
    labels = {"ok": "accepté", "ko": "refusé (complet)", "stopped": "coupé tôt"}
    seen = set()
    top = mon.T * 3
    for h in hist:
        seq = unpack(h["seq"], h["n_done"])
        Dk, D = [0], 0
        for i, c in enumerate(seq):
            D += ref_seq[i] - c
            Dk.append(D)
        top = max(top, min(Dk[-1], 4 * mon.T + 40))
        st = h["status"]
        ax.plot(range(len(Dk)), Dk, c=colors[st], lw=0.8, alpha=0.5,
                label=labels[st] if st not in seen else None)
        seen.add(st)
        if st == "stopped":
            ax.scatter([len(Dk) - 1], [Dk[-1]], c="tab:orange", s=12, zorder=3)
    ax.axhline(mon.T, c="k", ls="--", lw=1, label=f"seuil final : {mon.T:.0f} images perdues")
    b = mon.boundary()
    ax.plot(range(min_images, n), b[min_images:n], c="tab:orange", ls=":", lw=1.5,
            label=f"limite d'arrêt anticipé (z = {z}, sans gain observé)")
    ax.set_ylim(-mon.T, top * 1.1)
    ax.set_xlim(0, n)
    ax.set_xlabel("images évaluées (difficiles d'abord)")
    ax.set_ylabel("images perdues par rapport à la référence (cumul)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"{run_dir.name} — écart à la référence image par image")
    fig.tight_layout()
    fig.savefig(run_dir / "curves.png", dpi=120)


def plot_all(k, n, metric, show_all_codes=False, zoom=False):
    cache = Cache()
    pts = cache.points(k, n, None if show_all_codes else code_hash())
    if not pts:
        console.print(f"[yellow]Aucun point complet pour k={k}, {n} images (code actuel).")
        return None
    key = f"bits_{metric}"
    fig = Figure(figsize=(12, 7))
    ax = fig.subplots()
    ax.scatter([p[key] for p in pts], [p["acc"] for p in pts], s=10, c="silver",
               label=f"{len(pts)} configurations complètes")
    front = pareto(pts, key)
    ax.step([p[key] for p in front], [p["acc"] for p in front], where="post", c="k", lw=1.2,
            label="front de Pareto")
    ax.scatter([p[key] for p in front], [p["acc"] for p in front], s=18, c="k", zorder=3)
    cmap = tab10()
    for i, s in enumerate(load_runs(k=k, n=n)):
        f = s["final"]
        ax.scatter([f[key]], [f["acc"]], s=160, marker="*", color=cmap(i % 10), edgecolors="k", zorder=5,
                   label=f"{s['run']} ({f['acc']:.1f} %, {f[key]:.2f} b)")
        path = [(s["reference"][key], s["reference"]["acc"])] + [(p[key], p["acc"]) for p in s["path"]]
        ax.plot(*zip(*path), "-", color=cmap(i % 10), lw=0.8, alpha=0.6)
    ys = [p["acc"] for p in front]
    _axes(ax, k, metric)
    title = f"Bits / précision — noyau {k}x{k}, {n} images"
    if zoom:
        # partie haute : les 4 derniers points de précision, avec l'id des points Pareto (pour select)
        top = max(ys)
        _zoom(ax, [(p[key], p["acc"]) for p in pts], top - 4, top + 0.5)
        for p in front:
            if p["acc"] >= top - 4:
                ax.annotate(f"{p['id'][:6]}\n{p['acc']:.1f}%", (p[key], p["acc"]), fontsize=6,
                            xytext=(3, -12), textcoords="offset points")
        title += " — zoom sur la partie haute"
    else:
        ax.set_ylim(max(min(ys) - 5, 0), max(ys) + 2)
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=7)
    fig.tight_layout()
    out = paths.RUNS / f"all_k{k}_n{n}_{metric}{'_zoom' if zoom else ''}.png"
    fig.savefig(out, dpi=130)
    console.print(f"Graphe : [bold]{out.relative_to(paths.ROOT)}")
    return out


# ============================================================
# Progression au cours du temps : à quoi servent les passes ?
# ============================================================

def run_timeline(run_dir):
    """
    Relit history.jsonl : évaluations et réductions retenues avec leur temps écoulé total (en s)
    et leur passe. Gère les anciens historiques (temps remis à zéro à chaque reprise).
    """
    evs, kept = [], []
    off = last = 0.0
    for line in (run_dir / "history.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        ev = e.get("event")
        if ev == "resume":
            off += last
            last = 0.0
            continue
        if ev == "kept":
            k = dict(e)
            if "tg" not in k:
                k["tg"] = off + last
            if k.get("pass") is None:
                k["pass"] = next((x["pass"] for x in reversed(evs)
                                  if x["var"] == e["var"] and x["value"] == e["value"]), None)
            kept.append(k)
            continue
        if ev:
            continue
        last = e["t"]
        e["tg"] = e.get("tg", off + e["t"])
        evs.append(e)
    return evs, kept


def pass_stats(run_dir, ref_bits):
    """Par passe : gain en bits moyens (mem), nombre de réductions, durée, évaluations."""
    evs, kept = run_timeline(run_dir)
    out, prev = [], ref_bits
    for p in sorted({e["pass"] for e in evs if e.get("pass")}):
        ev = [e for e in evs if e.get("pass") == p]
        ks = [k for k in kept if k["pass"] == p]
        b = ks[-1]["bits_mem"] if ks else prev
        out.append({"pass": p, "reductions": len(ks), "bits_start": round(prev, 3), "bits_end": round(b, 3),
                    "gain": round(b - prev, 3), "evaluations": len(ev),
                    "t_start": round(min(e["tg"] for e in ev), 1), "t_end": round(max(e["tg"] for e in ev), 1)})
        prev = b
    return out


def plot_progress(run_dir):
    """Bits retenus (et précision) au cours du temps, passes colorées avec leur gain et leur durée."""
    s = json.loads((run_dir / "summary.json").read_text())
    evs, kept = run_timeline(run_dir)
    if not evs:
        return
    ref = s["reference"]
    stats = pass_stats(run_dir, ref["bits_mem"])
    t_end = max(e["tg"] for e in evs) / 60
    fig = Figure(figsize=(12, 7.5))
    ax, ax2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})

    for key, style, lab in (("bits_mem", "-", "bits moyens (stockage)"), ("bits_ops", "--", "bits moyens (accès)")):
        xs = [0] + [k["tg"] / 60 for k in kept] + [t_end]
        ys = [ref[key]] + [k[key] for k in kept]
        ys.append(ys[-1])
        ax.step(xs, ys, where="post", ls=style, c="tab:green" if key == "bits_mem" else "tab:purple", label=lab)
    for k in kept:
        ax.scatter([k["tg"] / 60], [k["bits_mem"]], s=12, c="tab:green", zorder=3)
    xs = [0] + [k["tg"] / 60 for k in kept] + [t_end]
    accs = [ref["acc"]] + [k["acc"] for k in kept]
    accs.append(accs[-1])
    ax2.step(xs, accs, where="post", c="tab:blue", label="précision de la config retenue")
    ax2.axhline(ref["acc"], c="tab:cyan", ls="--", lw=1, label=f"référence {ref['acc']:.2f} %")
    ax2.axhline(ref["acc"] - s["threshold"], c="tab:orange", ls=":", lw=1, label=f"seuil −{s['threshold']} pt")

    colors = ["#f2f2f2", "#e3ecf7"]
    lo = min(k["bits_mem"] for k in kept) if kept else ref["bits_mem"]
    for i, st in enumerate(stats):
        a, b = st["t_start"] / 60, st["t_end"] / 60
        for axe in (ax, ax2):
            axe.axvspan(a, b, color=colors[i % 2], zorder=0)
        ax.text((a + b) / 2, lo, f"passe {st['pass']}\n{st['gain']:+.2f} b\n{(b - a):.0f} min\n"
                f"{st['reductions']} réd.", ha="center", va="bottom", fontsize=8)
    prev = ref["bits_mem"]
    for k in kept:
        if prev - k["bits_mem"] >= 0.15:
            ax.annotate(f"{k['var']} {k.get('from', '?')}→{k['value']}", (k["tg"] / 60, k["bits_mem"]),
                        fontsize=6, xytext=(3, 3), textcoords="offset points", alpha=0.8)
        prev = k["bits_mem"]
    ax.set_ylabel("bits moyens par valeur")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)
    total = stats[-1]["bits_end"] - ref["bits_mem"] if stats else 0
    ax.set_title(f"{s['run']} — progression : {ref['bits_mem']:.2f} → {s['final']['bits_mem']:.2f} b "
                 f"({total:+.2f}) en {t_end:.0f} min")
    ax2.set_xlabel("temps écoulé (min, reprises comprises)")
    ax2.set_ylabel("précision (%)")
    ax2.grid(alpha=0.3)
    ax2.legend(loc="lower left", fontsize=7)
    fig.tight_layout()
    fig.savefig(run_dir / "progress.png", dpi=120)


def plot_progress_all(k, n):
    """Toutes les explorations : bits retenus en fonction du temps, fin de chaque passe marquée."""
    runs = [s for s in load_runs(k=k, n=n) if (paths.RUNS / s["run"] / "history.jsonl").exists()]
    if not runs:
        return None
    fig = Figure(figsize=(12, 6.5))
    ax = fig.subplots()
    cmap = tab10()
    for i, s in enumerate(runs):
        evs, kept = run_timeline(paths.RUNS / s["run"])
        if not evs:
            continue
        c = cmap(i % 10)
        t_end = max(e["tg"] for e in evs) / 60
        xs = [0] + [kk["tg"] / 60 for kk in kept] + [t_end]
        ys = [s["reference"]["bits_mem"]] + [kk["bits_mem"] for kk in kept]
        ys.append(ys[-1])
        ax.step(xs, ys, where="post", color=c, lw=1, label=f"{s['run']} ({s['final']['bits_mem']:.2f} b)")
        for st in pass_stats(paths.RUNS / s["run"], s["reference"]["bits_mem"]):
            ax.scatter([st["t_end"] / 60], [st["bits_end"]], color=c, marker="|", s=120)
            ax.annotate(str(st["pass"]), (st["t_end"] / 60, st["bits_end"]), fontsize=6, color=c,
                        xytext=(2, 4), textcoords="offset points")
    ax.set_xlabel("temps écoulé (min)")
    ax.set_ylabel("bits moyens par valeur (stockage)")
    ax.set_title(f"Progression de toutes les explorations — noyau {k}x{k}, {n} images (| = fin de passe)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    out = paths.RUNS / f"progress_k{k}_n{n}.png"
    fig.savefig(out, dpi=120)
    console.print(f"Graphe : [bold]{out.relative_to(paths.ROOT)}")
    return out
