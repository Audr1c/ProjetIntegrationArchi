"""
Affichage en direct (rich) : seuils et jauges, latence par bloc, réglages de chaque bloc, workers Catapult,
dernières évaluations. Sans rich (ou --plain) : une ligne par événement.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from . import paths
from .space import BLOCKS, SHORT

try:
    from rich import box
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.text import Text
    HAVE_RICH = True
except ImportError:                     # école sans rich : affichage texte
    HAVE_RICH = False

BLOCK_COLOR = {"layer1": "cyan", "layer2": "magenta", "layer3": "yellow", "dense": "green"}

STATUS = {
    "ref": ("cyan", "référence"), "kept": ("bold green", "★ retenu"), "other": ("green", "✓ valide, autre choix"),
    "slow": ("yellow", "✓ gain trop faible"),
    "nogain": ("dim", "✓ pas moins cher"), "target": ("yellow", "✗ latence > cible"),
    "slower": ("yellow", "✗ plus lent"),
    "timing": ("red", "✗ timing"), "budget": ("red", "✗ budget"), "refused": ("magenta", "! directive refusée"),
    "fail": ("red", "✗ échec Catapult"), "timeout": ("red", "✗ délai dépassé"),
    "interrupted": ("dim", "⊘ interrompu"), "skipped": ("dim", "» inutile (modèle)"), "valid": ("green", "✓"),
}
SPARK = "▁▂▃▄▅▆▇█"


def mcyc(c) -> str:
    return "—" if c is None else f"{c / 1e6:.2f} M"


def ips(cycles, clock_ns) -> str:
    """Cycles par image -> images par seconde."""
    return "—" if not cycles else f"{1e9 / (cycles * clock_ns):.1f} img/s"


def fmt_int(v) -> str:
    return "—" if v is None else f"{v:,.0f}".replace(",", " ")


def fmt_dur(s) -> str:
    if s is None:
        return "--:--"
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


class BaseView:
    """État partagé (mis à jour par les threads de la recherche) ; le rendu est dans les sous-classes."""

    def __init__(self, info: dict, limits, jobs: int):
        self.lock = threading.Lock()
        self.info = info
        self.limits = limits
        self.jobs = jobs
        self.t0 = time.time()
        self.phase_txt = "préparation"
        self.cur = None                 # configuration retenue courante (search.Eval)
        self.ref = None
        self.path = []
        self.recent = deque(maxlen=12)
        self.counts = {"synth": 0, "cache": 0, "skipped": 0, "bad": 0, "time": 0.0}
        self.disc_txt = ""

    def phase(self, text):
        with self.lock:
            self.phase_txt = text

    def discovered(self, disc):
        with self.lock:
            n_l = len(disc.loops)
            n_b = len({b for b, _ in disc.loops})
            self.disc_txt = f"{n_l} boucles nommées dans {n_b} blocs, {len(disc.resources)} ressources"

    def add_eval(self, ev):
        with self.lock:
            self.recent.append(ev)
            # les candidats écartés par le modèle restent visibles, mais 3 au plus dans la liste
            skipped = [e for e in self.recent if e.decision == "skipped"]
            for e in skipped[:-3]:
                self.recent.remove(e)
            c = self.counts
            if ev.decision == "skipped":
                c["skipped"] += 1
            elif ev.cached:
                c["cache"] += 1
            else:
                c["synth"] += 1
                c["time"] += ev.duration
            if ev.verdict in ("fail", "timeout", "refused"):
                c["bad"] += 1

    def current(self, ev, path):
        with self.lock:
            self.cur = ev
            self.path = list(path)
            if self.ref is None:
                self.ref = ev

    # workers : surchargés par Dashboard
    def worker_start(self, slot, label):
        pass

    def worker_stage(self, slot, stage, i, n):
        pass

    def worker_end(self, slot):
        pass


# ============================================================
# Texte simple
# ============================================================

class PlainView(BaseView):
    def _p(self, msg):
        print(f"[{fmt_dur(time.time() - self.t0)}] {msg}", flush=True)

    def phase(self, text):
        super().phase(text)
        self._p(f"--- {text}")

    def discovered(self, disc):
        super().discovered(disc)
        self._p(f"découverte : {self.disc_txt}")

    def worker_start(self, slot, label):
        self._p(f"w{slot} : {label}")

    def add_eval(self, ev):
        super().add_eval(ev)
        r = ev.res
        st = STATUS.get(ev.decision, ("", ev.decision))[1]
        extra = (f"latence {mcyc(r.get('latency'))}  débit {mcyc(r.get('throughput'))}  BRAM {fmt_int(r.get('bram'))}  DSP {fmt_int(r.get('dsp'))}  "
                 f"LUT {fmt_int(r.get('lut'))}  slack {r.get('slack')}") if r.get("status") == "ok" else r.get("error", "")
        self._p(f"{SHORT.get(ev.block, ev.block or '-'):>3} {ev.move:<34} {st:<22} {extra}"
                + ("  (cache)" if ev.cached else ""))

    def current(self, ev, path):
        super().current(ev, path)
        self._p(f"*** configuration courante : {ev.cfg.label()}  ({mcyc(ev.latency)} cycles)")


# ============================================================
# rich
# ============================================================

if HAVE_RICH:
    class Dashboard(BaseView):
        def __init__(self, info, limits, jobs):
            super().__init__(info, limits, jobs)
            self.console = Console()
            self.workers = Progress(
                TextColumn("[dim]w{task.fields[slot]}"),
                TextColumn("{task.description}", justify="left"),
                BarColumn(bar_width=None), TextColumn("[cyan]{task.fields[stage]}"), TimeElapsedColumn(),
                expand=True)
            self.slots = [self.workers.add_task("[dim]libre", total=1, completed=0, slot=i, stage="")
                          for i in range(jobs)]

        # ---------------- workers ----------------
        def worker_start(self, slot, label):
            self.workers.reset(self.slots[slot], total=1, completed=0, description=f"[yellow]{label}",
                               stage="lancement", slot=slot)

        def worker_stage(self, slot, stage, i, n):
            self.workers.update(self.slots[slot], total=n, completed=i - 1, stage=stage)

        def worker_end(self, slot):
            self.workers.reset(self.slots[slot], total=1, completed=0, description="[dim]libre", stage="", slot=slot)

        # ---------------- briques graphiques ----------------
        @staticmethod
        def gauge(value, full, limit, width=40) -> Text:
            """Barre 0..full, trait vertical au seuil, verte sous le seuil, rouge au-dessus."""
            t = Text()
            if value is None or not full:
                return t.append("·" * width, "dim")
            n = max(0, min(width, round(value / full * width)))
            mark = max(0, min(width - 1, round(limit / full * width)))
            color = "green" if value <= limit else "red"
            for i in range(width):
                if i == mark:
                    t.append("│", "bold white")
                elif i < n:
                    t.append("█", color)
                else:
                    t.append("░", "grey30")
            return t

        def stacked(self, ev, full, width=40) -> Text:
            """Latence par bloc, segments colorés, trait à la cible."""
            t = Text()
            blocks = (ev.res.get("blocks") or {}) if ev else {}
            if not blocks or not full:
                return t.append("·" * width, "dim")
            mark = min(width - 1, round(self.limits.target_cycles / full * width))
            cells = []
            for b in BLOCKS:
                n = round(blocks.get(b, 0) / full * width)
                if blocks.get(b, 0) > 0 and n == 0:
                    n = 1
                cells += [b] * n
            cells = cells[:width]
            for i in range(width):
                if i == mark:
                    t.append("│", "bold white")
                elif i < len(cells):
                    t.append("█", BLOCK_COLOR[cells[i]])
                else:
                    t.append(" ")
            return t

        def sparkline(self) -> Text:
            lats = [e.latency for e in self.path if e.latency]
            t = Text()
            if not lats:
                return t
            hi, lo = max(lats), min(lats)
            for v in lats:
                k = 0 if hi == lo else round((v - lo) / (hi - lo) * (len(SPARK) - 1))
                t.append(SPARK[k], "green" if v <= self.limits.target_cycles else "yellow")
            t.append("  " + " → ".join(f"{v / 1e6:.1f}" for v in lats[-6:]) + " M", "dim")
            return t

        # ---------------- panneaux ----------------
        def header(self):
            i, L, c = self.info, self.limits, self.counts
            n = c["synth"]
            avg = c["time"] / n if n else None
            goal = ("[bold magenta]performance max[/] (latence + débit) sous les budgets" if i.get("goal") == "perf"
                    else "[bold magenta]coût min[/] sous la cible de latence")
            lines = [
                f"[bold]{i['run']}[/]   moteur [bold]{i['backend']}[/]   {self.jobs} worker(s)   "
                f"horloge {i['clock_ns']:.0f} ns   code {i['code']}   objectif : {goal}",
                f"seuils : latence ≤ [bold]{L.target_cycles / 1e6:.1f} M[/] cycles "
                f"(≥ {1e9 / (L.target_cycles * i['clock_ns']):.0f} img/s)   BRAM18 ≤ [bold]{L.bram:.0f}[/]   "
                f"DSP ≤ [bold]{L.dsp:.0f}[/]   LUT ≤ [bold]{fmt_int(L.lut)}[/]   slack ≥ [bold]{L.slack_min:g}[/] ns",
                f"synthèses : [bold]{n}[/]  ({c['cache']} en cache, [dim]{c['skipped']} écartées par le modèle[/], "
                f"[red]{c['bad']} échecs[/])   durée moy. {fmt_dur(avg)}   écoulé {fmt_dur(time.time() - self.t0)}",
                f"[dim]découverte : {self.disc_txt or 'en cours'}[/]",
                f"[bold yellow]{self.phase_txt}[/]",
                "[dim]Ctrl-C : arrêt propre (tout est sauvé ; relancer la même commande reprend sur le cache)[/]",
            ]
            return Panel("\n".join(lines), title="Exploration HLS — directives Catapult", border_style="blue")

        def gauges(self):
            ev, ref, L = self.cur, self.ref, self.limits
            g = Table.grid(padding=(0, 1))
            g.add_column(style="bold", width=8)
            g.add_column(no_wrap=True)
            g.add_column(justify="right")
            g.add_column()
            r = ev.res if ev else {}
            full_lat = max(ref.latency if ref else 0, L.target_cycles) * 1.02
            lat = r.get("latency")
            g.add_row("latence", self.gauge(lat, full_lat, L.target_cycles), mcyc(lat),
                      (f"[green]✓[/] ×{ref.latency / lat:.1f} vs réf"
                       if lat and lat <= L.target_cycles
                       else (f"[red]✗[/] ×{ref.latency / lat:.1f} vs réf" if lat and ref else "")))
            dev = paths.DEVICE
            thr = r.get("throughput")
            g.add_row("débit", self.gauge(thr, full_lat, L.target_cycles), mcyc(thr),
                      f"[cyan]{ips(thr, self.info['clock_ns'])}[/]" if thr else "")
            for key, name, lim, cap in (("bram", "BRAM18", L.bram, dev["BRAM18"]), ("dsp", "DSP", L.dsp, dev["DSP"]),
                                        ("lut", "LUT", L.lut, dev["LUT"])):
                v = r.get(key)
                g.add_row(name, self.gauge(v, cap, lim), f"{fmt_int(v)} / {fmt_int(lim)}",
                          "" if v is None else ("[green]✓[/]" if v <= lim else "[red]✗[/]"))
            s = r.get("slack")
            g.add_row("slack", Text(""), "—" if s is None else f"{s:+.2f} ns",
                      "" if s is None else ("[green]✓[/]" if s >= L.slack_min else "[red]✗[/]"))
            g.add_row("", "", "", "")
            g.add_row("blocs", self.stacked(ev, full_lat), "", "")
            legend = Text()
            blocks = r.get("blocks") or {}
            for b in BLOCKS:
                v = blocks.get(b)
                legend.append("█", BLOCK_COLOR[b]).append(f"{SHORT[b]} {'—' if v is None else f'{v / 1e6:.1f}'}  ")
            g.add_row("", legend, "[dim]M cycles", "")
            g.add_row("chemin", self.sparkline(), "", "")
            cost = f"coût {L.cost(r):.3f} (somme des fractions de budget)" if r.get("status") == "ok" else ""
            return Panel(g, title="Configuration retenue vs seuils", subtitle=cost, border_style="green")

        def architecture(self):
            t = Table(box=box.SIMPLE_HEAD, expand=True)
            for col, j in (("bloc", "left"), ("MAC", "left"), ("×", "right"), ("RAM", "left"), ("ReLU/pool", "left"),
                           ("latence", "right"), ("part", "right"), ("modèle", "right")):
                t.add_column(col, justify=j)
            ev = self.cur
            if ev is None:
                return Panel(t, title="Réglages par bloc", border_style="magenta")
            blocks = ev.res.get("blocks") or {}
            tot = sum(blocks.values()) or 1
            neck = max(blocks, key=blocks.get) if blocks else None      # bloc le plus lent = débit
            pred = ev.predicted.get("blocks") or {}
            for b in BLOCKS:
                k = ev.cfg.blocks[b]
                lat = blocks.get(b)
                share = (lat or 0) / tot
                ram = ("double port" if k.dp else "1R1W") + (f", entrée {k.in_banks()} bancs" if k.xin else "")
                t.add_row(f"[{BLOCK_COLOR[b]}]{b}" + (" [bold red]◆" if b == neck else ""),
                          f"pipeline II{k.ii}" if k.pipe else "[dim]séquentiel",
                          str(k.par) if k.par > 1 else "[dim]1", ram if (k.dp or k.xin) else "[dim]1R1W",
                          "pipelinés" if k.pp else "[dim]séquentiels", mcyc(lat),
                          f"[bold]{share:.0%}" if share > 0.4 else f"{share:.0%}", mcyc(pred.get(b)))
            t.caption = ("[bold red]◆[/] goulot (fixe le débit) · " +
                         ("canaux en ping-pong" if ev.cfg.chan == 2 else "canaux en mémoire simple"))
            return Panel(t, title="Réglages par bloc", border_style="magenta")

        def recent_table(self):
            t = Table(box=box.SIMPLE_HEAD, expand=True)
            for col, j in (("phase", "left"), ("bloc", "left"), ("changement", "left"), ("latence", "right"),
                           ("débit", "right"), ("BRAM", "right"), ("DSP", "right"), ("LUT", "right"), ("slack", "right"),
                           ("coût", "right"), ("durée", "right"), ("", "left")):
                t.add_column(col, justify=j)
            for ev in reversed(self.recent):
                r, p = ev.res, ev.predicted
                ok = r.get("status") == "ok" and r.get("latency") is not None
                color, txt = STATUS.get(ev.decision, ("white", ev.decision))
                note = (" [dim](cache)" if ev.cached else "")
                if not ok and r.get("error"):
                    note += f" [dim]{r['error'][:48]}"
                pre = "" if ok else "[dim]~"     # valeurs prédites par le modèle
                src = r if ok else p
                t.add_row(ev.phase, f"[{BLOCK_COLOR.get(ev.block, 'white')}]{SHORT.get(ev.block, ev.block)}",
                          ev.move, pre + mcyc(src.get("latency")), pre + mcyc(src.get("throughput")),
                          pre + fmt_int(src.get("bram")),
                          pre + fmt_int(src.get("dsp")), pre + fmt_int(src.get("lut")),
                          f"{r['slack']:+.2f}" if ok and r.get("slack") is not None else "",
                          f"{self.limits.cost(r):.3f}" if ok else (f"[dim]~{p['cost']:.3f}" if p.get("cost") else ""),
                          fmt_dur(ev.duration) if ev.duration else "", f"[{color}]{txt}[/]{note}")
            return Panel(t, title="Dernières évaluations   [dim](~ : prédiction du modèle)[/]", border_style="dim")

        def __rich__(self):
            with self.lock:
                top = Table.grid(expand=True)
                top.add_column(ratio=1)
                top.add_column(ratio=1)
                top.add_row(self.gauges(), self.architecture())
                return Group(self.header(), top, Panel(self.workers, title="Workers Catapult", border_style="dim"),
                             self.recent_table())
