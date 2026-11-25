"""Fin de run : summary.json, best_directives.tcl, tableau du chemin suivi (aussi pour « show »)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import space
from .space import Config, Discovery
from .store import read_history


def write_summary(store, explorer, best, interrupted: bool, t0: float):
    L = explorer.limits
    hist_path = [{"id": e.id, "block": e.block, "move": e.move, "label": e.cfg.label(), "result": e.res,
                  "cost": round(L.cost(e.res), 4)} for e in explorer.path]
    store.write_json("summary.json", {
        "date": time.strftime("%Y-%m-%d %H:%M:%S"), "duration_s": round(time.time() - t0),
        "interrupted": interrupted, "code": explorer.code,
        "target_met": bool(best and best.latency and best.latency <= L.target_cycles),
        "reference": hist_path[0] if hist_path else None,
        "best": {"id": best.id, "config": best.cfg.to_json(), "label": best.cfg.label(), "result": best.res,
                 "cost": round(L.cost(best.res), 4)} if best else None,
        "path": hist_path,
        "goal": explorer.goal,
        "cheapest": ({"id": c.id, "config": c.cfg.to_json(), "label": c.cfg.label(), "result": c.res,
                      "cost": round(L.cost(c.res), 4)} if (c := explorer.cheapest()) else None),
        "counts": {"synth": explorer.n_synth, "evals": len(explorer.evals),
                   "skipped": sum(e.decision == "skipped" for e in explorer.evals)},
    })
    if explorer.disc is not None:
        store.write_json("discovery.json", explorer.disc.to_json())
    if best is not None and explorer.disc is not None:
        (store.run / "best_directives.tcl").write_text(best_tcl(best.cfg, explorer.disc, store.run.name, best.res))
        c = explorer.cheapest()
        if c is not None and c.cfg != best.cfg:      # objectif perf : on garde aussi la moins chère sous la cible
            (store.run / "cheapest_directives.tcl").write_text(best_tcl(c.cfg, explorer.disc, store.run.name, c.res))


def best_tcl(cfg: Config, disc: Discovery, run_name: str, res: dict) -> str:
    """Directives au format de cnn_try (hls/cnn.tcl) : set DIRECTIVES_FILE sur ce fichier."""
    lat = res.get("latency")
    lines = [
        f"# Directives retenues par l'exploration HLS, run {run_name}",
        f"# {space.ascii(cfg.label())}",
        f"# latence {lat / 1e6:.2f} M cycles, BRAM18 {res.get('bram')}, DSP {res.get('dsp')}, LUT {res.get('lut')}, "
        f"slack {res.get('slack')} ns" if lat else "#",
        "# Usage : dans hls/cnn.tcl, set DIRECTIVES_FILE " + f"ExplorationHLS/runs/{run_name}/best_directives.tcl",
        "# (source apres go assembly ; cnn_try essaie les chemins dans l'ordre et previent s'il n'en trouve aucun)",
        "",
    ]
    for d in space.directives(cfg, disc):
        paths = " ".join("{" + p + "}" for p in d.paths)
        lines.append(f"cnn_try [list {paths}] {d.args}   ;# {space.ascii(d.what)}")
    return "\n".join(lines) + "\n"


def path_rows(run: Path) -> list:
    """[(pas, bloc, changement, résultat, coût)] du chemin retenu, lu dans history.jsonl."""
    return [h for h in read_history(run) if h["decision"] in ("ref", "kept")]


def print_run(run: Path, console=None):
    params = json.loads((run / "params.json").read_text())
    summ = json.loads((run / "summary.json").read_text()) if (run / "summary.json").exists() else {}
    rows = path_rows(run)
    L = params["limits"]
    if console is None:
        try:
            from rich.console import Console
            console = Console(width=max(Console().width, 150))     # journal / nohup : pas de colonnes écrasées
        except ImportError:
            pass
    out = console.print if console else print
    head = (f"{run.name}  ({params['backend']}, cible {L['target_cycles'] / 1e6:g} M cycles, "
            f"budgets BRAM {L['bram']:.0f} DSP {L['dsp']:.0f} LUT {L['lut']:.0f})")
    try:
        from rich.table import Table
        t = Table(title=head, title_justify="left")
        for c, j in (("pas", "right"), ("bloc", "left"), ("changement", "left"), ("latence", "right"), ("débit", "right"),
                     ("BRAM18", "right"), ("DSP", "right"), ("LUT", "right"), ("slack", "right"), ("coût", "right")):
            t.add_column(c, justify=j)
        for i, h in enumerate(rows):
            r = h["result"]
            t.add_row(str(i), space.SHORT.get(h["block"], h["block"] or "—"), h["move"],
                      f"{r['latency'] / 1e6:.2f} M", f"{(r.get('throughput') or 0) / 1e6:.2f} M", str(r.get("bram")), str(r.get("dsp")), str(r.get("lut")),
                      f"{r['slack']:+.2f}" if r.get("slack") is not None else "—", f"{h['cost']:.3f}")
        out(t)
    except ImportError:
        print(head)
        for i, h in enumerate(rows):
            r = h["result"]
            print(f"  {i:2d} {h['block'] or '-':7s} {h['move']:36s} {r['latency'] / 1e6:7.2f} M"
                  f"  débit {(r.get('throughput') or 0) / 1e6:5.2f} M  BRAM {r.get('bram')}"
                  f"  DSP {r.get('dsp')}  LUT {r.get('lut')}  slack {r.get('slack')}")
    if summ.get("best"):
        b = summ["best"]
        out(f"retenu : {b['label']}  ->  " + ("cible atteinte" if summ.get("target_met") else "cible NON atteinte")
            + ("  (run interrompu)" if summ.get("interrupted") else ""))
    if summ.get("cheapest") and summ["cheapest"]["id"] != (summ.get("best") or {}).get("id"):
        c = summ["cheapest"]
        out(f"la moins chère sous la cible : {c['label']}  ({c['result']['latency'] / 1e6:.2f} M cycles, "
            f"coût {c['cost']:.3f}) -> cheapest_directives.tcl")
    if (run / "best_directives.tcl").exists():
        out(f"directives : {run / 'best_directives.tcl'}")
