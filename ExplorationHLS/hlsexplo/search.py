"""
Recherche : référence, montée, repli.

Deux objectifs (--goal) :
    cost  la configuration la MOINS COÛTEUSE dont la latence tient la cible (critère J = latence)
    perf  la configuration la PLUS RAPIDE qui tient les budgets (critère J = latence + débit, débit = bloc
          le plus lent, les blocs travaillant en parallèle sur des images successives), puis sans le superflu

1. Référence : aucune directive (projet de base tel quel). Le modèle est recalé dessus.
2. Montée, tant que la latence dépasse la cible (cost) ou tant qu'un barreau rapporte (perf). À chaque pas,
   pour chaque bloc, le prochain barreau de son échelle (space.LADDER) est un candidat. Le modèle prédit
   son gain sur J et son surcoût (fraction de budget) :
     - gain prédit < 2 % de J -> écarté sans synthèse (« inutile (modèle) ») ; budget prédit dépassé de
       plus de 10 % -> écarté aussi ;
     - sinon classé par gain / surcoût. Le meilleur (les `jobs` meilleurs) part en synthèse.
   Un barreau a des variantes (II = 1 puis II = 2...) : la suivante n'est essayée que si Catapult échoue
   ou rate le timing sur la précédente. Retenu : un résultat valide (limits.verdict) qui baisse la
   latence mesurée d'au moins 2 % ; entre plusieurs (--jobs > 1), le meilleur gain mesuré par surcoût
   mesuré, les autres sont reproposés au pas suivant. Budget dépassé sur un bloc ->
   on ne monte plus ce bloc (les barreaux suivants coûtent plus).
3. Repli, une fois la cible atteinte : on essaie de retirer ce qui coûte (×10 -> ×5, double port -> simple,
   pipeline retiré, ping-pong -> simple...), le plus économe d'abord, en gardant latence <= cible, tous les
   seuils, et (perf) J à 1 % près. Jusqu'à ce qu'aucun repli ne passe.
4. Polissage (runs longs, désactivable par --no-polish) : tous les voisins à un réglage près de la config
   retenue (II ±1, ×2 <-> ×5 <-> ×10, double port, bancs, ReLU/pool, perceptron, ping-pong), sans filtre du
   modèle ; le premier meilleur est retenu et on recommence, jusqu'à ce qu'aucun voisin ne fasse mieux.
Arrêts : --max-evals synthèses, --hours, Ctrl-C ; une licence indisponible fait attendre (pas échouer).
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
from .model import Model, perf
from .space import BLOCKS, Config, apply_rung, ladder, refused_knobs, rung_done, trim_moves
from .store import Store, eval_id

MIN_GAIN = 0.02       # gain prédit minimal (fraction de la latence totale) pour lancer une synthèse
MIN_IMPROVE = 0.02    # gain mesuré minimal (même échelle) pour retenir un pas de montée
TRIM_TOL = 0.01       # objectif perf : un repli peut coûter au plus 1 % de latence + débit
POLISH_TOL = 0.005    # polissage : amélioration minimale de 0,5 % (ou J égal à 0,5 % près et moins cher)


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
    def __init__(self, backends: list, limits: Limits, store: Store, view, max_evals: int = 60, goal: str = "cost",
                 hours: float | None = None, polish: bool = True, license_wait_min: float = 30.0):
        self.goal = goal                 # cost : config la moins chère sous la cible ; perf : la plus rapide
        self.deadline = time.time() + hours * 3600 if hours else None
        self.do_polish = polish
        self.license_wait_s = license_wait_min * 60
        self.on_keep = None              # rappel après chaque pas retenu (sauvegarde : summary, Tcl, graphes)
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
        self.refused = {}            # bloc -> réglages dont Catapult a refusé une directive

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
        elif self.exhausted():
            res, dur = {"status": "interrupted", "error": self.exhausted()}, 0.0
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
            waited = 0.0
            while True:
                try:
                    res = self.backends[slot].evaluate(cfg, dirs,
                                                       lambda st, i, n: self.view.worker_stage(slot, st, i, n),
                                                       self.store.eval_dir(eid))
                except BackendError as e:
                    res = {"status": "interrupted" if self.stop.is_set() else "fail", "error": str(e)[:200]}
                except BaseException:
                    self.backends[slot].kill()
                    raise
                # pas de licence : ce n'est pas la config qui est en cause -> on attend et on réessaie
                if res.get("status") != "license" or self.stop.is_set():
                    break
                if waited >= self.license_wait_s:
                    res = {"status": "interrupted", "error": f"licence Catapult indisponible depuis {waited / 60:.0f} min"}
                    self.view.phase(f"ARRÊT : licence Catapult indisponible depuis {waited / 60:.0f} min")
                    self.stop.set()
                    break
                pause = 60 * getattr(self.backends[slot], "speed", 1.0)     # --fake : accéléré
                self.view.worker_stage(slot, f"licence indisponible, nouvel essai dans 60 s ({waited / 60:.0f} min)", 0, 1)
                self.stop.wait(pause)
                waited += 60
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
        if self.on_keep:
            try:
                self.on_keep()
            except Exception as e:         # une sauvegarde ratée ne doit pas tuer un run de plusieurs heures
                self.view.phase(f"(sauvegarde intermédiaire ratée : {e})")

    def exhausted(self) -> str:
        """Raison d'arrêter de lancer des synthèses ('' si on continue)."""
        if self.stop.is_set():
            return "arrêt demandé"
        if self.n_synth >= self.max_evals:
            return f"limite de {self.max_evals} synthèses atteinte"
        if self.deadline and time.time() > self.deadline:
            return "temps alloué écoulé (--hours)"
        return ""

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
            blocks = {b: round(v) for b, v in self.model.blocks(cfg).items()}
            return {"latency": sum(blocks.values()), "throughput": max(blocks.values()), "blocks": blocks,
                    "cost": round(self.limits.cost(r), 4), **{k: round(v) for k, v in r.items()}}

    def J(self, ev: Eval) -> float:
        """Critère de performance mesuré : latence (objectif cost) ou latence + débit (objectif perf)."""
        blocks = ev.res.get("blocks")
        return perf(blocks, self.goal) if blocks else ev.latency

    def _pred_J(self, cur: Eval, block: str, knobs) -> float:
        """J prédit si seul `block` change : blocs mesurés de cur, celui-là prédit par le modèle."""
        blocks = dict(cur.res.get("blocks") or {}) or {b: self._block_latency(cur, b) for b in BLOCKS}
        if block in BLOCKS:
            with self.model_lock:
                blocks[block] = self.model.block_latency(block, knobs)
        return perf(blocks, self.goal)

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

    def _climbing(self, cur: Eval) -> bool:
        """Objectif cost : monter jusqu'à la cible. Objectif perf : tant qu'un barreau rapporte (budgets)."""
        return self.goal == "perf" or cur.latency > self.limits.target_cycles

    def climb(self, cur: Eval) -> Eval:
        L = self.limits
        tried, blocked = set(), set()
        while self._climbing(cur) and not self.exhausted():
            options = self._climb_options(cur, tried, blocked)
            if not options:
                self.view.phase("montée : plus aucun changement prometteur")
                break
            batch = options[: self.jobs]
            self.view.phase("montée : " + ", ".join(f"{space.SHORT[o['block']]} {o['rung'].name}" for o in batch))
            evs = self._parallel([lambda o=o: self._try_rung(cur, o) for o in batch])
            j_cur = self.J(cur)

            def improves(ev):
                return ev.verdict == "valid" and self.J(ev) < j_cur * (1 - MIN_IMPROVE)

            def score(ev):        # même critère que le classement, sur les valeurs MESURÉES
                extra = L.cost(ev.res) - L.cost(cur.res)
                return (j_cur - self.J(ev)) / (max(extra, 0.0) + 0.02)

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
        j_cur = self.J(cur)
        what = "latence + débit" if self.goal == "perf" else "latence"
        for b in BLOCKS:
            if b in blocked:
                continue
            k = cur.cfg.blocks[b]
            for rung in ladder(b):
                if rung_done(k, rung) or (b, rung.name, k) in tried:
                    continue
                k2 = apply_rung(k, rung, rung.variants[0])
                cfg2 = cur.cfg.with_block(b, k2)
                bad = {f for f in self.refused.get(b, ()) if getattr(k2, f) != getattr(k, f)}
                if bad:
                    self.skip(cfg2, "montée", b, rung.name,
                              f"directive déjà refusée par Catapult ({', '.join(sorted(bad))})", self._pred(cfg2))
                    continue
                gain = j_cur - self._pred_J(cur, b, k2)
                with self.model_lock:
                    extra = self.model.cost(cfg2) - self.model.cost(cur.cfg)
                pred = self._pred(cfg2)
                if gain < MIN_GAIN * j_cur:
                    self.skip(cfg2, "montée", b, rung.name,
                              f"gain prédit {gain / 1e6:+.2f} M cycles (< {MIN_GAIN:.0%} de {what})", pred)
                    continue
                if pred["bram"] > self.limits.bram * 1.1 or pred["dsp"] > self.limits.dsp * 1.1:
                    self.skip(cfg2, "montée", b, rung.name, "budget dépassé (prédit)", pred)
                    continue
                options.append({"block": b, "rung": rung, "key": (b, rung.name, k), "gain": gain,
                                "score": gain / (max(extra, 0.0) + 0.02)})
        return sorted(options, key=lambda o: -o["score"])

    def _try_rung(self, cur: Eval, o: dict) -> Eval:
        """Variantes du barreau dans l'ordre ; la suivante seulement après un échec, un timing raté
        ou une directive refusée."""
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
            if ev.verdict == "refused":                 # structurel : les autres variantes le seraient aussi
                self.refused.setdefault(b, set()).update(refused_knobs(ev.res.get("refused") or []))
                break
            if ev.verdict not in ("fail", "timing"):
                break
        return ev

    # ============================================================
    # 3. Repli
    # ============================================================

    def trim(self, cur: Eval) -> Eval:
        """Retire ce qui coûte. Objectif cost : tant que latence <= cible. Objectif perf : tant que J ne se
        dégrade pas de plus de TRIM_TOL (on enlève ce qui ne sert pas à la performance)."""
        L = self.limits
        tried = set()
        while not self.exhausted():
            moves = []
            j_cur = self.J(cur)
            for b, desc, cfg2 in trim_moves(cur.cfg):
                if cfg2 in tried:
                    continue
                pred = self._pred(cfg2)
                j_pred = self._pred_J(cur, b, cfg2.blocks.get(b)) if b in BLOCKS else j_cur
                lat_pred = cur.latency + (pred["blocks"][b] - self._block_latency(cur, b) if b in BLOCKS else 0)
                if lat_pred > L.target_cycles * 1.05:
                    why = f"latence prédite {lat_pred / 1e6:.2f} M > cible"
                elif self.goal == "perf" and j_pred > j_cur * (1 + TRIM_TOL + 0.04):
                    why = f"perte prédite {100 * (j_pred / j_cur - 1):.0f} % de latence + débit"
                else:
                    why = None
                if why:
                    tried.add(cfg2)
                    self.skip(cfg2, "repli", b, desc, why, pred)
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

                def keeps_perf(ev):
                    return self.goal != "perf" or self.J(ev) <= j_cur * (1 + TRIM_TOL)

                ok = [ev for ev in evs if ev.verdict == "valid" and ev.latency <= L.target_cycles
                      and keeps_perf(ev) and L.cost(ev.res) < L.cost(cur.res) - 1e-6]
                accepted = min(ok, key=lambda ev: L.cost(ev.res)) if ok else None
                for ev in evs:
                    if ev is accepted:
                        d = "kept"
                    elif ev.verdict == "valid":
                        d = "target" if ev.latency > L.target_cycles else ("nogain" if keeps_perf(ev) else "slower")
                    else:
                        d = ev.verdict
                    self.record(ev, d)
                if accepted or self.exhausted():
                    break
            if not accepted:
                break
            cur = accepted
            self.keep(cur)
        return cur

    # ============================================================
    # 4. Polissage (runs longs)
    # ============================================================

    def better(self, ev: Eval, cur: Eval) -> bool:
        """ev meilleur que cur, au sens de l'objectif (tous seuils déjà vérifiés par verdict == valid)."""
        L = self.limits
        if ev.verdict != "valid" or not ev.latency:
            return False
        if cur.latency > L.target_cycles:                       # cible pas encore atteinte : la latence d'abord
            return ev.latency < cur.latency * (1 - POLISH_TOL)
        if ev.latency > L.target_cycles:
            return False
        if self.goal == "perf":
            jn, jc = self.J(ev), self.J(cur)
            return jn < jc * (1 - POLISH_TOL) or (jn <= jc * (1 + POLISH_TOL) and L.cost(ev.res) < L.cost(cur.res) - 0.005)
        return L.cost(ev.res) < L.cost(cur.res) - 1e-6

    def polish(self, cur: Eval) -> Eval:
        """Recherche locale exhaustive : TOUS les voisins à un réglage près (space.neighbors), sans filtre du
        modèle (il ne sert qu'à l'ordre), sauf budget prédit très dépassé et directives déjà refusées.
        Premier voisin meilleur (lot de `jobs`) -> retenu, et on recommence autour de lui."""
        seen = {e.cfg for e in self.evals if e.decision != "skipped"}
        while not self.exhausted():
            cands = []
            j_cur = self.J(cur)
            for b, desc, cfg2 in space.neighbors(cur.cfg):
                if cfg2 in seen:
                    continue
                pred = self._pred(cfg2)
                k_old, k_new = cur.cfg.blocks.get(b), cfg2.blocks.get(b)
                bad = {f for f in self.refused.get(b, ()) if k_new is not None and getattr(k_new, f) and
                       getattr(k_new, f) != getattr(k_old, f)}
                if bad or pred["bram"] > self.limits.bram * 1.15 or pred["dsp"] > self.limits.dsp * 1.15:
                    seen.add(cfg2)
                    self.skip(cfg2, "polissage", b, desc, "directive refusée" if bad else "budget dépassé (prédit)", pred)
                    continue
                j_pred = self._pred_J(cur, b, k_new) if b in BLOCKS else j_cur
                key = (j_pred, pred["cost"]) if self.goal == "perf" else (pred["cost"], j_pred)
                cands.append((key, b, desc, cfg2, pred))
            if not cands:
                break
            cands.sort(key=lambda c: c[0])
            accepted = None
            for i in range(0, len(cands), self.jobs):
                batch = cands[i: i + self.jobs]
                self.view.phase(f"polissage : voisins {i + 1}-{i + len(batch)} / {len(cands)} — "
                                + ", ".join(f"{space.SHORT.get(c[1], c[1])} {c[2]}" for c in batch))
                evs = self._parallel([lambda c=c: self.evaluate(c[3], "polissage", c[1], c[2], c[4]) for c in batch])
                for c in batch:
                    seen.add(c[3])
                good = [ev for ev in evs if self.better(ev, cur)]
                accepted = min(good, key=lambda ev: (self.J(ev), self.limits.cost(ev.res))) if good else None
                for ev in evs:
                    self.record(ev, "kept" if ev is accepted else ("nogain" if ev.verdict == "valid" else ev.verdict))
                if accepted or self.exhausted():
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
        if self._climbing(cur):
            cur = self.climb(cur)
        if cur.latency <= self.limits.target_cycles and not self.exhausted():
            cur = self.trim(cur)
        if self.do_polish and not self.exhausted():
            cur = self.polish(cur)
        met = cur.latency <= self.limits.target_cycles
        why = self.exhausted()
        self.view.phase("terminé : " + ("cible atteinte" if met else "cible NON atteinte")
                        + (f" ({why})" if why and why != "arrêt demandé" else ""))
        return cur

    def cheapest(self):
        """Configuration valide la moins coûteuse sous la cible, parmi toutes celles synthétisées."""
        ok = [e for e in self.evals if e.verdict == "valid" and e.latency and e.latency <= self.limits.target_cycles]
        return min(ok, key=lambda e: self.limits.cost(e.res)) if ok else None
