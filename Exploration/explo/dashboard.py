"""Tableau de bord rich : progression, descentes en cours, workers, formats, dernières évaluations."""

import threading
from collections import deque

from rich import box
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from .formats import FMT, NAMES, bits

console = Console()

# ============================================================
# Affichage
# ============================================================

def fmt_time(s):
    if s is None:
        return "--:--"
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


STATUS_TXT = {"kept": "[bold green]★ retenu", "ok": "[green]✓", "ko": "[red]✗ trop bas",
              "stopped": "[yellow]⚡ coupé", "killed": "[dim]⊘ inutile", "error": "[red]erreur",
              "ref": "[cyan]référence"}


class Dashboard:
    def __init__(self, n_workers, n_runs):
        self.lock = threading.Lock()
        self.n_runs = n_runs
        self.overall = Progress(
            SpinnerColumn(), TextColumn("[bold]{task.description}", justify="left"),
            BarColumn(bar_width=None), MofNCompleteColumn(),
            TextColumn("[cyan]{task.fields[info]}"),
            TextColumn("• écoulé"), TimeElapsedColumn(),
            TextColumn("• reste [bold magenta]{task.fields[eta]}"),
            expand=True)
        self.t_runs = (self.overall.add_task("Explorations", total=n_runs, info="", eta="--:--")
                       if n_runs > 1 else None)
        self.t_vars = self.overall.add_task("Variables", total=1, info="", eta="--:--")

        self.workers = Progress(
            TextColumn("[dim]w{task.fields[slot]}"),
            TextColumn("{task.description}", justify="left"),
            BarColumn(bar_width=None), MofNCompleteColumn(),
            TextColumn("{task.fields[acc]}"),
            TimeElapsedColumn(),
            expand=True)
        self.slots = [self.workers.add_task("[dim]libre", total=1, completed=0, slot=i, acc="")
                      for i in range(n_workers)]

        self.info = {}
        self.config = None
        self.start = None
        self.k = 5
        self.descents = []          # instantané des descentes en cours (pour le tableau)
        self.recent = deque(maxlen=14)

    # --- workers (appelé depuis les threads) ---
    def worker_begin(self, slot, label):
        self.workers.reset(self.slots[slot], total=1, completed=0, slot=slot,
                           description=f"[yellow]{label}[/] [dim]compilation", acc="")

    def worker_stage(self, slot, label, stage):
        self.workers.update(self.slots[slot], description=f"[yellow]{label}[/] [dim]{stage}")

    def worker_image(self, slot, done, total, D, T):
        col = "green" if D <= T else ("yellow" if D <= 2 * T else "red")
        self.workers.update(self.slots[slot], total=total, completed=done,
                            acc=f"[{col}]Δ réf {D:+4d} img[/] [dim](max {T:.0f})")

    def worker_end(self, slot):
        self.workers.reset(self.slots[slot], total=1, completed=0, description="[dim]libre",
                           acc="", slot=slot)

    # --- rendu ---
    def descents_table(self):
        t = Table(box=box.SIMPLE_HEAD, expand=True)
        for c, j in (("descente", "left"), ("départ", "right"), ("✓ passe à", "right"),
                     ("✗ casse à", "right"), ("en cours", "left"), ("cœurs", "right"), ("", "left")):
            t.add_column(c, justify=j)
        for d in self.descents:
            t.add_row(f"[bold yellow]{d['var']}", str(d["cur"]), f"[green]{d['hi']}" + (" [dim]?" if d["stale"] else ""),
                      f"[red]{d['lo']}" if d["lo"] >= d["min"] else f"[dim]< {d['min']}",
                      " ".join(map(str, d["running"])), str(len(d["running"])), d["note"])
        return t

    @staticmethod
    def bits_bar(I0, F0, I, F, testing=None):
        """Barre d'un format, 1 caractère par bit : partie entière | partie fractionnaire | bits retirés.
        testing : (dim, valeur la plus basse en cours de test) -> bits menacés en jaune."""
        W0, W = I0 + F0, I + F
        nI = min(max(I, 0), W)
        nF = W - nI
        risk = 0
        if testing:
            dim, v = testing
            risk = max(0, (I if dim == "I" else F) - v)
            risk = min(risk, nF if dim == "F" else nI)
        if testing and testing[0] == "I":
            bar = f"[cyan]{'█' * (nI - risk)}[/][yellow]{'█' * risk}[/][green]{'█' * nF}[/]"
        else:
            bar = f"[cyan]{'█' * nI}[/][green]{'█' * (nF - risk)}[/][yellow]{'█' * risk}[/]"
        return bar + f"[grey30]{'·' * max(0, W0 - W)}[/]"

    def config_table(self):
        t = Table(title="Configuration courante", box=box.SIMPLE_HEAD, title_style="bold")
        for c, j in (("format", "left"), ("S", "center"), ("I", "right"), ("F", "right"),
                     ("W", "right"), ("ΔW", "right"), ("bits  [cyan]█ entiers[/] [green]█ fraction[/] "
                                                       "[yellow]█ en test[/] [grey30]· retirés[/]", "left")):
            t.add_column(c, justify=j, style="bold" if c == "W" else None)
        if self.config is None:
            return t
        active = {(d["name"], d["dim"]): d for d in self.descents}
        for n in NAMES:
            I, F = self.config[n]
            d = I + F - sum(self.start[n])
            style = "bold yellow" if any(a[0] == n for a in active) else ""
            cI = "[reverse]" if (n, "I") in active else ""
            cF = "[reverse]" if (n, "F") in active else ""
            testing = None
            for dim in ("I", "F"):
                ds = active.get((n, dim))
                if ds and ds["running"]:
                    testing = (dim, min(ds["running"]))
            t.add_row(n, "s" if FMT[n][2] else "u", f"{cI}{I}", f"{cF}{F}", str(I + F),
                      f"[green]{d}" if d < 0 else f"{d}",
                      self.bits_bar(*self.start[n], I, F, testing), style=style)
        bm, tm = bits(self.config, self.k, "mem")
        bo, _ = bits(self.config, self.k, "ops")
        t.caption = f"mem {bm:.2f} b/val ({tm / 8192:.0f} Kio) • ops {bo:.2f} b/val"
        return t

    def recent_table(self):
        t = Table(title="Dernières évaluations", box=box.SIMPLE_HEAD, title_style="bold")
        for c, j in (("variable", "left"), ("précision", "right"), ("Δ réf", "right"),
                     ("images", "right"), ("bits", "right"), ("", "left")):
            t.add_column(c, justify=j)
        for r in reversed(self.recent):
            st = STATUS_TXT[r["status"]] + (" [dim](cache)" if r.get("cached") else "")
            acc = f"{r['acc']:.2f} %" if r.get("acc") is not None else "-"
            d = f"{r['D']:+d}" if r.get("D") is not None else ""
            t.add_row(r["label"], acc, d, str(r.get("n_done") or ""), f"{r['bits_mem']:.2f}", st)
        return t

    def info_panel(self):
        i = self.info
        nan = float("nan")
        saved = i.get("img_saved", 0)
        total = i.get("img_total", 0)
        lines = [
            f"[bold]{i.get('run', '')}[/]   noyau [bold]{i.get('k')}x{i.get('k')}[/]   "
            f"{i.get('n')} images   seuil [bold]{i.get('threshold')}[/] pt   graine {i.get('seed')}   "
            f"ordre {i.get('order')}   {i.get('workers')} workers, {i.get('parallel')} descente(s) en parallèle",
            f"référence [bold cyan]{i.get('ref', nan):.2f} %[/] ([dim]{i.get('ref_bits', 0):.2f} b/val[/])"
            f"   →   accepté si ≥ [bold]{i.get('limit', nan):.2f} %[/] (≤ {i.get('T', 0):.0f} images perdues)"
            f"     actuel [bold green]{i.get('cur_acc', nan):.2f} %[/] ([bold]{i.get('cur_bits', 0):.2f} b/val[/])",
            f"images : {i.get('img_order', '')}   •   arrêt anticipé : {i.get('early', '')}",
            f"évaluations : [bold]{i.get('evals', 0)}[/] ({i.get('cached', 0)} en cache, "
            f"[yellow]{i.get('stopped', 0)} coupées[/], [dim]{i.get('killed', 0)} inutiles tuées[/], "
            f"{i.get('rechecks', 0)} revérifiées)   images économisées : [bold]{saved}[/]/{saved + total} "
            f"({100 * saved / max(1, saved + total):.0f} %)   durée moy. complète {i.get('t_eval', 0):.1f} s",
        ]
        if i.get("resumed"):
            lines.append(f"[magenta]{i['resumed']}")
        if i.get("phase"):
            lines.append(f"[bold yellow]{i['phase']}")
        lines.append("[dim]Ctrl-C : arrêt propre de la run en cours (tout est sauvegardé, reprise possible) — "
                     "2e Ctrl-C : arrêt immédiat")
        return Panel("\n".join(lines), title="Exploration bits / précision", border_style="blue")

    def __rich__(self):
        with self.lock:
            return Group(
                self.info_panel(),
                self.overall,
                Panel(self.descents_table(), title="Descentes en cours", border_style="yellow"),
                Panel(self.workers, title="Workers", border_style="dim"),
                Columns([self.config_table(), self.recent_table()], padding=(0, 3)),
            )
