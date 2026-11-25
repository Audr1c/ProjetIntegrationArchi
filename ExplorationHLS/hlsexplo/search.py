"""
Recherche : référence, montée, repli.

1. Référence : aucune directive (projet de base tel quel). Le modèle est recalé dessus.
2. Montée, tant que la latence dépasse la cible. À chaque pas, pour chaque bloc, le prochain barreau de
   son échelle (space.LADDER) est un candidat. Le modèle prédit son gain en cycles et son surcoût
   (fraction de budget) :
     - gain prédit < 2 % de la latence totale -> écarté sans synthèse (« inutile (modèle) ») ;
     - sinon classé par gain / surcoût. Le meilleur (les `jobs` meilleurs) part en synthèse.
   Un barreau a des variantes (II = 1 puis II = 2...) : la suivante n'est essayée que si Catapult échoue
   ou rate le timing sur la précédente. Retenu : un résultat valide (limits.verdict) qui baisse la
   latence mesurée d'au moins 2 % ; entre plusieurs (--jobs > 1), le meilleur gain mesuré par surcoût
   mesuré, les autres sont reproposés au pas suivant. Budget dépassé sur un bloc ->
   on ne monte plus ce bloc (les barreaux suivants coûtent plus).
3. Repli, une fois la cible atteinte : on essaie de retirer ce qui coûte (×5 -> ×2, double port -> simple,
   pipeline retiré, ping-pong -> simple...), le plus économe d'abord, en gardant latence <= cible et
   tous les seuils. Jusqu'à ce qu'aucun repli ne passe.
Le chemin suivi (configurations retenues) et chaque évaluation sont enregistrés (store.Store).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import paths, space
from .backend import BackendError
from .limits import Limits
from .model import Model
from .space import BLOCKS, Config, apply_rung, ladder, rung_done, trim_moves
from .store import Store, eval_id

MIN_GAIN = 0.02       # gain prédit minimal (fraction de la latence totale) pour lancer une synthèse
MIN_IMPROVE = 0.02    # gain mesuré minimal (même échelle) pour retenir un pas de montée


@dataclass
class Eval:
    """Une configuration évaluée (ou écartée par le modèle)."""
    id: str
    cfg: Config
    res: dict
    verdict: str                 # valid | timing | budget | refused | fail | timeout | interrupted | skipped
    phase: str = ""
    block: str = ""
    move: str = ""
    cached: bool = False
    duration: float = 0.0
    predicted: dict = field(default_factory=dict)
    decision: str = ""           # ref | kept | other | slow | target | nogain | skipped | <verdict>

    @property
    def latency(self):
        return self.res.get("latency")


class Explorer:
    def __init__(self, backends: list, limits: Limits, store: Store, view, max_evals: int = 60):
        self.backends = backends
        self.jobs = len(backends)
        self.free = list(range(self.jobs))
        self.free_lock = threading.Condition()
        self.limits = limits
        self.store = store
        self.view = view
        self.max_evals = max_evals
        self.model = Model(limits)
        self.model_lock = threading.Lock()
        self.code = paths.code_hash()
        self.disc = None
        self.stop = threading.Event()
        self.n_synth = 0
        self.evals = []              # toutes les évaluations du run (ordre chronologique)
        self.path = []               # configurations retenues : référence, puis chaque pas
        self.shown_skips = set()

    # ============================================================
    # Briques
    # ============================================================

    def prepare(self):
        """Projet de base de chaque worker (en parallèle), puis découverte des chemins."""
        def one(slot):
            self.view.worker_start(slot, "projet de base (go analyze ... assembly)")
            try:
                return self.backends[slot].prepare(lambda st, i, n: self.view.worker_stage(slot, st, i, n))
            finally:
                self.view.worker_end(slot)
        discs = self._parallel([lambda s=s: one(s) for s in range(self.jobs)])
        self.disc = discs[0]
        self.view.discovered(self.disc)

    def _take_slot(self) -> int:
        with self.free_lock:
            while not self.free:
                self.free_lock.wait()
            return self.free.pop(0)

    def _give_slot(self, slot: int):
        with self.free_lock:
            self.free.append(slot)
            self.free_lock.notify()

    def evaluate(self, cfg: Config, phase: str, block: str, move: str, predicted: dict | None = None) -> Eval:
        """Synthèse d'une configuration (ou lecture du cache)."""
        eid = eval_id(self.code, cfg)
        hit = self.store.cached(eid)
        cached = hit is not None
        if cached:
            res, dur = hit["result"], hit["duration"]
        elif self.stop.is_set():
            res, dur = {"status": "interrupted"}, 0.0
        elif self.n_synth >= self.max_evals:
            res, dur = {"status": "fail", "error": f"limite de {self.max_evals} synthèses atteinte"}, 0.0
        else:
            res, dur = self._synthesize(eid, cfg, f"{space.SHORT.get(block, block)} {move}")
        ev = Eval(eid, cfg, res, self.limits.verdict(res), phase, block, move, cached, dur, predicted or {})
        if res.get("status") == "ok":
            with self.model_lock:
                self.model.calibrate(cfg, res)
        return ev

    def _synthesize(self, eid: str, cfg: Config, label: str) -> tuple:
        slot = self._take_slot()
        t0 = time.time()
        try:
            self.view.worker_start(slot, label)
            dirs = space.directives(cfg, self.disc)
            try:
                res = self.backends[slot].evaluate(cfg, dirs, lambda st, i, n: self.view.worker_stage(slot, st, i, n),
                                                   self.store.eval_dir(eid))
            except BackendError as e:
                res = {"status": "interrupted" if self.stop.is_set() else "fail", "error": str(e)[:200]}
            except BaseException:
                self.backends[slot].kill()
                raise
            if self.stop.is_set() and res.get("status") != "ok":
                res = {"status": "interrupted"}
            dur = time.time() - t0
            with self.free_lock:
                self.n_synth += 1
            if res.get("status") != "interrupted":
                self.store.put(eid, self.code, cfg, res, dur)
            return res, dur
        finally:
            self.view.worker_end(slot)
            self._give_slot(slot)

    def record(self, ev: Eval, decision: str):
        ev.decision = decision
        self.evals.append(ev)
        self.store.history({
            "id": ev.id, "phase": ev.phase, "block": ev.block, "move": ev.move, "verdict": ev.verdict,
            "decision": decision, "cached": ev.cached, "duration": round(ev.duration, 1),
            "config": ev.cfg.to_json(), "label": ev.cfg.label(), "result": ev.res, "predicted": ev.predicted,
            "cost": round(self.limits.cost(ev.res), 4) if ev.res.get("status") == "ok" else None,
            "time": time.strftime("%H:%M:%S")})
        self.view.add_eval(ev)

    def skip(self, cfg: Config, phase: str, block: str, move: str, why: str, predicted: dict):
        """Candidat écarté par le modèle : enregistré sans synthèse, une fois par état du bloc concerné."""
        key = (block, move, cfg.blocks[block] if block in cfg.blocks else cfg.chan)
        if key in self.shown_skips:
            return
        self.shown_skips.add(key)
        ev = Eval(eval_id(self.code, cfg), cfg, {"status": "skipped", "error": why}, "skipped",
                  phase, block, move, predicted=predicted)
        self.record(ev, "skipped")

    def keep(self, ev: Eval):
        self.path.append(ev)
        self.view.current(ev, self.path)

    def _parallel(self, fns: list) -> list:
        if len(fns) == 1:
            return [fns[0]()]
        ex = ThreadPoolExecutor(max_workers=len(fns))
        futs = [ex.submit(f) for f in fns]
        try:
            return [f.result() for f in futs]
        except KeyboardInterrupt:
            self.abort()
            raise
        finally:
            ex.shutdown(wait=True)

    def abort(self):
        self.stop.set()
        for b in self.backends:
            b.kill()

    def _pred(self, cfg: Config) -> dict:
        with self.model_lock:
            r = self.model.resources(cfg)
            blocks = {b: round(self.model.block_latency(b, k)) for b, k in cfg.blocks.items()}
            return {"latency": sum(blocks.values()), "blocks": blocks, "cost": round(self.limits.cost(r), 4),
                    **{k: round(v) for k, v in r.items()}}

    def _block_latency(self, ev: Eval, block: str) -> float:
        measured = (ev.res.get("blocks") or {}).get(block)
        with self.model_lock:
            return measured if measured else self.model.block_latency(block, ev.cfg.blocks[block])

    # ============================================================
    # 1. Référence
    # ============================================================

    def reference(self, chan: int) -> Eval:
        self.view.phase("référence : aucune directive")
        ref = self.evaluate(Config(chan=chan), "référence", "", "aucune directive")
        self.record(ref, "ref")
        if ref.res.get("status") != "ok":
            raise BackendError(f"la référence a échoué ({ref.res.get('status')}) : {ref.res.get('error', '')}")
        with self.model_lock:
            self.model.calibrate(ref.cfg, ref.res, reference=True)
        self.keep(ref)
        return ref

    # ============================================================
    # 2. Montée
    # ============================================================

    def climb(self, cur: Eval) -> Eval:
        L = self.limits
        tried, blocked = set(), set()
        while cur.latency > L.target_cycles and not self.stop.is_set():
            options = self._climb_options(cur, tried, blocked)
            if not options:
                self.view.phase("montée : plus aucun changement prometteur")
                break
            batch = options[: self.jobs]
            self.view.phase("montée : " + ", ".join(f"{space.SHORT[o['block']]} {o['rung'].name}" for o in batch))
            evs = self._parallel([lambda o=o: self._try_rung(cur, o) for o in batch])

            def improves(ev):
                return ev.verdict == "valid" and ev.latency < cur.latency * (1 - MIN_IMPROVE)

            def score(ev):        # même critère que le classement, sur les valeurs MESURÉES
                extra = L.cost(ev.res) - L.cost(cur.res)
                return (cur.latency - ev.latency) / (max(extra, 0.0) + 0.02)

            good = [ev for ev in evs if improves(ev)]
            best = max(good, key=score) if good else None
            for o, ev in zip(batch, evs):
                if ev.verdict == "budget":
                    blocked.add(o["block"])
                if ev is best:
                    self.record(ev, "kept")
                elif improves(ev):
                    self.record(ev, "other")     # bon mais moins rentable : reproposé au pas suivant
                else:
                    tried.add(o["key"])
                    self.record(ev, "slow" if ev.verdict == "valid" else ev.verdict)
            if best is not None:
                cur = best
                self.keep(cur)
        return cur

    def _climb_options(self, cur: Eval, tried: set, blocked: set) -> list:
        options = []
        for b in BLOCKS:
            if b in blocked:
                continue
            k = cur.cfg.blocks[b]
            cur_b = self._block_latency(cur, b)
            for rung in ladder(b):
                if rung_done(k, rung) or (b, rung.name, k) in tried:
                    continue
                k2 = apply_rung(k, rung, rung.variants[0])
                cfg2 = cur.cfg.with_block(b, k2)
                with self.model_lock:
                    gain = cur_b - self.model.block_latency(b, k2)
                    extra = self.model.cost(cfg2) - self.model.cost(cur.cfg)
                pred = self._pred(cfg2)
                if gain < MIN_GAIN * cur.latency:
                    self.skip(cfg2, "montée", b, rung.name,
                              f"gain prédit {gain / 1e6:+.2f} M cycles (< {MIN_GAIN:.0%} de la latence)", pred)
                    continue
                options.append({"block": b, "rung": rung, "key": (b, rung.name, k), "gain": gain,
                                "score": gain / (max(extra, 0.0) + 0.02)})
        return sorted(options, key=lambda o: -o["score"])

    def _try_rung(self, cur: Eval, o: dict) -> Eval:
        """Variantes du barreau dans l'ordre ; la suivante seulement après un échec ou un timing raté."""
        b, rung = o["block"], o["rung"]
        ev = None
        for i, var in enumerate(rung.variants):
            if self.stop.is_set():
                break
            cfg2 = cur.cfg.with_block(b, apply_rung(cur.cfg.blocks[b], rung, var))
            move = rung.name + ("".join(f" {k}={v}" for k, v in var.items()) if len(rung.variants) > 1 else "")
            if ev is not None:                       # variante précédente ratée : on la note et on continue
                self.record(ev, ev.verdict)
            ev = self.evaluate(cfg2, "montée", b, move, self._pred(cfg2))
            if ev.verdict not in ("fail", "timing"):
                break
        return ev

    # ============================================================
    # 3. Repli
    # ============================================================

    def trim(self, cur: Eval) -> Eval:
        L = self.limits
        tried = set()
        while not self.stop.is_set():
            moves = []
            for b, desc, cfg2 in trim_moves(cur.cfg):
                if cfg2 in tried:
                    continue
                pred = self._pred(cfg2)
                if b in BLOCKS:
                    with self.model_lock:
                        delta = self.model.block_latency(b, cfg2.blocks[b]) - self.model.block_latency(b, cur.cfg.blocks[b])
                else:
                    delta = 0.0
                if cur.latency + delta > L.target_cycles * 1.05:
                    tried.add(cfg2)
                    self.skip(cfg2, "repli", b, desc, f"latence prédite {(cur.latency + delta) / 1e6:.2f} M > cible", pred)
                    continue
                with self.model_lock:
                    saving = self.model.cost(cur.cfg) - self.model.cost(cfg2)
                moves.append((saving, b, desc, cfg2, pred))
            if not moves:
                break
            moves.sort(key=lambda m: -m[0])
            accepted = None
            for i in range(0, len(moves), self.jobs):
                batch = moves[i: i + self.jobs]
                self.view.phase("repli : " + ", ".join(f"{space.SHORT.get(m[1], m[1])} {m[2]}" for m in batch))
                evs = self._parallel([lambda m=m: self.evaluate(m[3], "repli", m[1], m[2], m[4]) for m in batch])
                for m in batch:
                    tried.add(m[3])
                ok = [ev for ev in evs if ev.verdict == "valid" and ev.latency <= L.target_cycles
                      and L.cost(ev.res) < L.cost(cur.res) - 1e-6]
                accepted = min(ok, key=lambda ev: L.cost(ev.res)) if ok else None
                for ev in evs:
                    if ev is accepted:
                        d = "kept"
                    elif ev.verdict == "valid":
                        d = "target" if ev.latency > L.target_cycles else "nogain"
                    else:
                        d = ev.verdict
                    self.record(ev, d)
                if accepted or self.stop.is_set():
                    break
            if not accepted:
                break
            cur = accepted
            self.keep(cur)
        return cur

    # ============================================================
    # Tout
    # ============================================================

    def run(self, chan: int = 1) -> Eval:
        self.prepare()
        cur = self.reference(chan)
        if cur.latency > self.limits.target_cycles:
            cur = self.climb(cur)
        if cur.latency <= self.limits.target_cycles and not self.stop.is_set():
            cur = self.trim(cur)
        met = cur.latency <= self.limits.target_cycles
        self.view.phase("terminé : " + ("cible atteinte" if met else "cible NON atteinte"))
        return cur
