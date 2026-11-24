"""Descentes (exponentielle puis dichotomie asynchrone) et déroulement d'une exploration."""

import json
import queue
import random
import time
from concurrent.futures import FIRST_COMPLETED, wait
from datetime import datetime

from . import paths
from .dashboard import console, fmt_time
from .formats import NAMES, bits, bounds, make_config_hpp, pack, point_id, start_config, unpack, with_value
from .monitor import PairedMonitor, make_order
from .plots import pass_stats, plot_curves, plot_formats, plot_progress, plot_run

# ============================================================
# Descente d'une variable : exponentielle puis dichotomie asynchrone
# ============================================================

class Descent:
    """
    Intervalle inconnu ]lo_fail, hi_pass[ :
        hi_pass : plus petite valeur qui passe (au départ : valeur actuelle)
        lo_fail : plus grande valeur qui casse (au départ : borne min - 1)
    hi_ver : version de la configuration sur laquelle hi_pass a été validée.
    Si une autre descente a validé une réduction depuis, hi_pass est revérifiée avant d'être retenue.
    """

    def __init__(self, name, dim, pass_no, config, version):
        self.name, self.dim, self.pass_no = name, dim, pass_no
        self.var = f"{name}.{dim}"
        self.cur = config[name][0 if dim == "I" else 1]
        self.min = bounds(config, name, dim)
        self.hi_pass, self.hi_ver = self.cur, version
        self.lo_fail = self.min - 1
        self.expo = [self.cur - 2 ** j for j in range(8)]
        self.running = {}               # future -> (valeur, pid, config, version, revérification ?)
        self.done = set()               # valeurs déjà conclues
        self.recheck = False            # une revérification de hi_pass est en cours
        self.note = ""
        self.t0 = time.time()

    def inside(self, v):
        return self.lo_fail < v < self.hi_pass

    def running_vals(self):
        return {r[0] for r in self.running.values()}

    def stale(self, version):
        return self.hi_pass != self.cur and self.hi_ver != version

    def next_value(self, version):
        """Prochaine valeur à lancer, ou None. ('recheck', v) pour revérifier hi_pass."""
        busy = self.running_vals() | self.done
        for v in self.expo:                     # v-1, v-2, v-4, v-8...
            if self.inside(v) and v not in busy:
                return v
        pts = sorted({self.lo_fail, self.hi_pass} | {v for v in self.running_vals() if self.inside(v)})
        best, gap = None, 1
        for a, b in zip(pts, pts[1:]):          # milieu du plus grand trou
            m = (a + b) // 2
            if b - a > gap and m not in busy:
                best, gap = m, b - a
        if best is not None:
            return best
        if (self.hi_pass - self.lo_fail <= 1 and self.stale(version) and not self.recheck
                and self.hi_pass not in self.running_vals()):
            return ("recheck", self.hi_pass)
        return None

    def finished(self, version):
        return self.hi_pass - self.lo_fail <= 1 and not self.running and not self.stale(version)

    def snapshot(self, version):
        return {"var": self.var, "name": self.name, "dim": self.dim, "cur": self.cur,
                "hi": self.hi_pass, "lo": self.lo_fail, "min": self.min,
                "stale": self.stale(version), "running": sorted(self.running_vals(), reverse=True),
                "note": self.note}


# ============================================================
# Une exploration
# ============================================================

class Exploration:
    def __init__(self, args, seed, threshold, cache, runner, dash, code, run_id=None):
        self.args = args
        self.k, self.n, self.batch = args.k, args.images, args.batch
        self.seed, self.threshold = seed, threshold
        self.cache, self.runner, self.dash, self.code = cache, runner, dash, code
        self.workers = args.workers
        self.rng = random.Random(seed)
        if run_id is None:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            run_id = f"{stamp}_k{self.k}_t{threshold:g}_s{seed}"
        self.run_id = run_id
        self.dir = paths.RUNS / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.plan, self.done_idx = [], set()
        self.elapsed0 = 0.0         # durée déjà passée avant une reprise
        self.resumed = False
        self.slots = queue.Queue()
        for i in range(self.workers):
            self.slots.put(i)
        self.history, self.path, self.eval_times = [], [], []
        self.stats = {"evals": 0, "cached": 0, "stopped": 0, "killed": 0, "rechecks": 0,
                      "img_saved": 0, "img_total": 0}
        self.t0 = time.time()
        self.status = "en cours"
        self.ref_acc = self.cur_acc = float("nan")
        self.ref_pid = None
        self.order_file = None
        self.ref_seq = None
        self.start = None
        self.config = None
        self.version = 0            # +1 à chaque réduction validée

    # ---------- évaluation d'une configuration (dans un thread) ----------
    def _eval(self, config, label, with_monitor=True):
        pid = point_id(self.code, self.k, self.n, self.batch, config)
        hit = self.cache.get(pid)
        if hit and "acc" in hit:
            return pid, hit, True
        T = self.threshold * self.n / 100
        if (hit and hit.get("stopped") and hit.get("ref") == self.ref_pid
                and hit.get("min_loss", -1) > T):
            return pid, hit, True       # déjà coupé avec une borne qui suffit pour ce seuil

        slot = self.slots.get()
        mon = (PairedMonitor(self.ref_seq, self.threshold, self.args.z, self.args.min_images)
               if (with_monitor and self.ref_seq) else None)
        try:
            if self.runner.stop.is_set():
                return pid, {"killed": True, "n_done": 0}, False
            self.dash.worker_begin(slot, label)

            def on_image(rank, idx, ok, margin):
                if mon is None:
                    self.dash.workers.update(self.dash.slots[slot], total=self.n, completed=rank)
                    return False
                mon.update(ok)
                self.dash.worker_image(slot, rank, self.n, mon.D, mon.T)
                return self.args.early_stop and mon.should_stop()

            res = self.runner.evaluate(config, self.k, self.n, self.batch, pid, self.order_file,
                                       on_stage=lambda s: self.dash.worker_stage(slot, label, s),
                                       on_image=on_image)
        finally:
            self.dash.worker_end(slot)
            self.slots.put(slot)

        if "error" in res or "killed" in res:
            return pid, res, False
        trace = res.pop("trace")
        seq = [ok for _, ok, _ in trace]                       # succès dans l'ordre d'évaluation
        entry = {"id": pid, "k": self.k, "n": self.n, "batch": self.batch, "code": self.code,
                 "config": config, "date": datetime.now().isoformat(timespec="seconds"),
                 "bits_mem": round(bits(config, self.k, "mem")[0], 4),
                 "bits_ops": round(bits(config, self.k, "ops")[0], 4),
                 "n_done": len(trace), "seq": pack(seq), "ref": self.ref_pid, **res}
        if mon is not None:
            lo_stat, lo_exact = mon.min_loss()
            entry.update(D=mon.D, min_loss=round(lo_stat, 2), min_loss_exact=lo_exact)
        if "acc" in entry:
            by_idx = [0] * self.n
            for idx, ok, _ in trace:
                by_idx[idx] = ok
            entry["by_index"] = pack(by_idx)
            if not with_monitor:                                 # référence : on garde les marges
                entry["margins"] = {str(i): round(m, 4) for i, _, m in trace}
        self.cache.put(pid, entry)
        return pid, entry, False

    def status_of(self, res):
        if "error" in res:
            return "error"
        if res.get("killed"):
            return "killed"
        if res.get("stopped"):
            return "stopped"
        return "ok" if res["acc"] >= self.ref_acc - self.threshold else "ko"

    def note(self, label, config, res, cached, status):
        """Met à jour compteurs et tableau « dernières évaluations »."""
        s = self.stats
        s["evals"] += 1
        s["cached"] += cached
        s["stopped"] += status == "stopped"
        s["killed"] += status == "killed"
        if not cached and status in ("ok", "ko", "stopped", "killed"):
            done = res.get("n_done", self.n) or 0
            s["img_total"] += done
            s["img_saved"] += self.n - done
        if not cached and "acc" in res:
            self.eval_times.append(res["t_run"] + res["t_compile"])
        with self.dash.lock:
            self.dash.info.update(s)
            if self.eval_times:
                self.dash.info["t_eval"] = sum(self.eval_times[-20:]) / len(self.eval_times[-20:])
            self.dash.recent.append({"label": label, "acc": res.get("acc"), "status": status,
                                     "D": res.get("D"), "n_done": res.get("n_done"),
                                     "bits_mem": bits(config, self.k)[0], "cached": cached})

    def record(self, config, res, pid, cached, var, value, status, pass_no, version):
        e = {"t": round(time.time() - self.t0, 1), "tg": round(self.duration(), 1), "pass": pass_no, "var": var, "value": value,
             "id": pid, "version": version, "config": config, "status": status, "cached": cached,
             "acc": res.get("acc"), "error": res.get("error"), "n_done": res.get("n_done"),
             "D": res.get("D"), "min_loss": res.get("min_loss"), "seq": res.get("seq"),
             "bits_mem": round(bits(config, self.k, "mem")[0], 4),
             "bits_ops": round(bits(config, self.k, "ops")[0], 4)}
        self.history.append(e)
        with open(self.dir / "history.jsonl", "a") as f:
            f.write(json.dumps(e) + "\n")

    # ---------- référence ----------
    def reference(self, pool):
        with self.dash.lock:
            self.dash.info["phase"] = "Référence : toutes les images dans l'ordre naturel, marge de chacune"
        pid, res, cached = pool.submit(self._eval, self.config, "référence", False).result()
        if self.runner.stop.is_set():
            return False
        if "acc" not in res:
            raise RuntimeError(f"La configuration de départ ne fonctionne pas : {res.get('error')}")
        self.ref_pid = pid
        self.ref_acc = self.cur_acc = res["acc"]
        by_idx = unpack(res["by_index"], self.n)
        margins = {int(i): m for i, m in res["margins"].items()}
        order = (make_order(margins, self.args.easy_frac, self.args.easy_every)
                 if self.args.reorder else list(range(self.n)))
        self.ref_seq = [by_idx[i] for i in order]
        self.order_file = self.dir / "order.txt"
        self.order_file.write_text(" ".join(map(str, order)) + "\n")
        (self.dir / "reference.json").write_text(json.dumps({
            "id": pid, "acc": self.ref_acc, "config": self.config, "order": order,
            "margins": {str(i): margins[i] for i in order},
            "correct": {str(i): by_idx[i] for i in order}}, indent=0))
        self.note("référence", self.config, res, cached, "ref")
        self.record(self.config, res, pid, cached, "ref", None, "ref", 0, 0)
        with self.dash.lock:
            self.dash.info.update(ref=self.ref_acc, ref_bits=bits(self.config, self.k)[0],
                                  limit=self.ref_acc - self.threshold, T=self.threshold * self.n / 100,
                                  phase="")
        self.update_dash()
        return True

    # ---------- toutes les descentes, P en parallèle ----------
    def descend(self, pool):
        P = max(1, self.args.parallel_vars)
        d = self.dash
        todo = [(i, *self.plan[i]) for i in range(len(self.plan)) if i not in self.done_idx]
        active = []
        n_done, n_new, t_start = len(self.done_idx), 0, time.time()
        d.overall.reset(d.t_vars, total=len(self.plan), completed=n_done, info="", eta="--:--")
        futures = {}                    # future -> descente

        def submit(ds, v, recheck=False):
            c = with_value(self.config, ds.name, ds.dim, v)
            pid = point_id(self.code, self.k, self.n, self.batch, c)
            self.runner.uncancel(pid)
            label = f"{ds.var}={v}" + (" ↻" if recheck else "")
            f = pool.submit(self._eval, c, label)
            ds.running[f] = (v, pid, c, self.version, recheck)
            futures[f] = ds
            if recheck:
                ds.recheck = True
                self.stats["rechecks"] += 1

        while not self.runner.stop.is_set():
            # 1. démarre de nouvelles descentes (jamais deux sur le même format)
            busy_fmt = {ds.name for ds in active}
            i = 0
            while len(active) < P and i < len(todo):
                idx, pass_no, name, dim = todo[i]
                if name in busy_fmt:
                    i += 1
                    continue
                todo.pop(i)
                ds = Descent(name, dim, pass_no, self.config, self.version)
                ds.plan_idx = idx
                if ds.hi_pass - ds.lo_fail <= 1:            # déjà au minimum
                    n_done += 1
                    self.done_idx.add(idx)
                    d.overall.update(d.t_vars, completed=n_done)
                    continue
                active.append(ds)
                busy_fmt.add(name)
            if not active:
                break

            # 2. répartit les workers : part égale, puis le reste à qui en a besoin
            quota = max(1, self.workers // len(active))
            for share in (quota, self.workers):
                for ds in active:
                    while len(futures) < self.workers and len(ds.running) < share:
                        v = ds.next_value(self.version)
                        if v is None:
                            break
                        if isinstance(v, tuple):
                            submit(ds, v[1], recheck=True)
                        else:
                            submit(ds, v)
            self.show_descents(active)

            # 3. attend un résultat
            finished, _ = wait(list(futures), timeout=0.5, return_when=FIRST_COMPLETED)
            for f in finished:
                ds = futures.pop(f)
                v, pid, c, ver, recheck = ds.running.pop(f)
                pid, res, cached = f.result()
                st = self.status_of(res)
                if recheck:
                    ds.recheck = False
                    recheck = v == ds.hi_pass
                if st == "ok" and ds.inside(v):
                    ds.hi_pass, ds.hi_ver = v, ver
                elif st == "ok" and recheck:
                    ds.hi_ver = ver     # revérifiée (si une autre réduction est passée entre-temps : on recommence)
                elif st in ("ko", "stopped", "error") and (ds.inside(v) or recheck):
                    if recheck:                             # le succès ne tient plus : on reprend
                        ds.note = f"[red]{v} ne passe plus"
                        ds.lo_fail, ds.hi_pass, ds.hi_ver = v, ds.cur, self.version
                        ds.done = {x for x in ds.done if x < v}
                    else:
                        ds.lo_fail = v
                if st != "killed":
                    ds.done.add(v)
                self.note(f"{ds.var}={v}", c, res, cached, st)
                self.record(c, res, pid, cached, ds.var, v, st, ds.pass_no, ver)

            # 4. tue les calculs devenus inutiles
            for ds in active:
                for v, pid, _, _, rc in ds.running.values():
                    if not ds.inside(v) and not (rc and v == ds.hi_pass):
                        self.runner.cancel(pid)

            # 5. descentes terminées : on retient la valeur
            for ds in [x for x in active if x.finished(self.version)]:
                active.remove(ds)
                self.commit(ds)
                self.done_idx.add(ds.plan_idx)
                n_done += 1
                n_new += 1
                el = time.time() - t_start
                left = len(todo) + len(active)
                eta = el / n_new * left
                d.overall.update(d.t_vars, completed=n_done, eta=fmt_time(eta),
                                 info=f"{bits(self.config, self.k)[0]:.2f} b/val")
                self.save()
            self.show_descents(active)

        with d.lock:
            d.descents = []

    def show_descents(self, active):
        with self.dash.lock:
            self.dash.descents = [ds.snapshot(self.version) for ds in active]

    def commit(self, ds):
        if ds.hi_pass >= ds.cur:
            return
        self.config = with_value(self.config, ds.name, ds.dim, ds.hi_pass)
        self.version += 1
        kept = next(e for e in reversed(self.history)
                    if e["var"] == ds.var and e["value"] == ds.hi_pass and e["status"] == "ok")
        self.cur_acc = kept["acc"]
        kept_e = {"var": ds.var, "value": ds.hi_pass, "from": ds.cur, "id": kept["id"], "acc": kept["acc"],
                  "pass": ds.pass_no, "tg": round(self.duration(), 1),
                  "bits_mem": kept["bits_mem"], "bits_ops": kept["bits_ops"],
                  "duration_s": round(time.time() - ds.t0, 1)}
        self.path.append(kept_e)
        with open(self.dir / "history.jsonl", "a") as fh:
            fh.write(json.dumps({"event": "kept", **kept_e}) + "\n")
        with self.dash.lock:
            for r in self.dash.recent:
                if r["label"].startswith(f"{ds.var}={ds.hi_pass}") and r["status"] == "ok":
                    r["status"] = "kept"
        self.update_dash()

    def update_dash(self):
        with self.dash.lock:
            self.dash.config = self.config
            self.dash.info["cur_acc"] = self.cur_acc
            self.dash.info["cur_bits"] = bits(self.config, self.k)[0]

    # ---------- exploration complète ----------
    def run(self, pool, run_index, runs_done_time):
        a = self.args
        state_f = self.dir / "state.json"
        if state_f.exists():
            self.load_state(json.loads(state_f.read_text()))
        else:
            self.config = start_config(a.start_F)
            self.start = {n: list(v) for n, v in self.config.items()}
            for f in ("history.jsonl", "summary.json"):         # run interrompu avant la référence
                if (self.dir / f).exists():                     # pas de missing_ok en Python < 3.8
                    (self.dir / f).unlink()
        params = {"run": self.run_id, "k": self.k, "images": self.n, "batch": self.batch,
                  "threshold": self.threshold, "seed": self.seed, "order": a.order,
                  "passes": a.passes, "workers": self.workers, "parallel_vars": a.parallel_vars,
                  "start_F": a.start_F, "early_stop": a.early_stop, "z": a.z, "min_images": a.min_images,
                  "reorder": a.reorder, "easy_frac": a.easy_frac, "easy_every": a.easy_every,
                  "code": self.code, "start": self.start,
                  "date": datetime.now().isoformat(timespec="seconds")}
        if not self.resumed:
            (self.dir / "params.json").write_text(json.dumps(params, indent=1))

        d = self.dash
        with d.lock:
            d.k = self.k
            d.start, d.config, d.descents = self.start, self.config, []
            d.run_index, d.n_runs_total = run_index, d.n_runs
            d.recent.clear()
            d.info.clear()
            d.info.update(run=self.run_id, k=self.k, n=self.n, threshold=self.threshold, seed=self.seed,
                          order=a.order, workers=self.workers, parallel=a.parallel_vars,
                          img_order=(f"difficiles d'abord (+{a.easy_frac:.0%} sûres, 1 sur {a.easy_every})"
                                     if a.reorder else "ordre naturel"),
                          early=(f"z = {a.z}, après {a.min_images} images" if a.early_stop else "désactivé"),
                          resumed=(f"reprise : {len(self.done_idx)}/{len(self.plan)} variables déjà faites"
                                   if self.resumed else ""))
            d.info.update(self.stats)

        if self.resumed:
            with d.lock:
                d.info.update(ref=self.ref_acc, ref_bits=bits(self.start, self.k)[0],
                              limit=self.ref_acc - self.threshold, T=self.threshold * self.n / 100)
            self.update_dash()
            ok = True
        else:
            ok = self.reference(pool)
            variables = [(n, dim) for n in NAMES for dim in ("F", "I")]
            self.plan = []
            for p in range(a.passes):
                vs = list(variables)
                if a.order == "random":
                    self.rng.shuffle(vs)
                self.plan += [(p + 1, n, dim) for n, dim in vs]
        if ok:
            self.save()
            self.descend(pool)

        if d.t_runs is not None:
            el = time.time() - self.t0
            per_run = (runs_done_time + el) / (run_index + 1)
            d.overall.update(d.t_runs, eta=fmt_time(per_run * (d.n_runs - run_index - 1)),
                             info=f"run {run_index + 1}")
        self.status = "interrompu" if self.runner.stop.is_set() else "terminé"
        self.save()
        return self

    def duration(self):
        return self.elapsed0 + time.time() - self.t0

    def load_state(self, st):
        """Reprise d'un run interrompu : on repart de la dernière variable terminée.
        Les descentes en cours au moment de l'arrêt sont refaites (leurs évaluations sont dans le cache)."""
        self.config, self.start = st["config"], st["start"]
        self.version, self.path, self.stats = st["version"], st["path"], st["stats"]
        self.cur_acc, self.ref_acc, self.ref_pid = st["cur_acc"], st["ref_acc"], st["ref_pid"]
        self.plan = [tuple(x) for x in st["plan"]]
        self.done_idx = set(st["done"])
        self.elapsed0 = st["elapsed"]
        ref = json.loads((self.dir / "reference.json").read_text())
        self.ref_seq = [ref["correct"][str(i)] for i in ref["order"]]
        self.order_file = self.dir / "order.txt"
        self.resumed = True
        with open(self.dir / "history.jsonl", "a") as fh:
            fh.write(json.dumps({"event": "resume", "date": datetime.now().isoformat(timespec="seconds"),
                                 "done": len(self.done_idx)}) + "\n")

    def save_state(self):
        if not self.plan:
            return
        st = {"config": self.config, "start": self.start, "version": self.version, "path": self.path,
              "stats": self.stats, "cur_acc": self.cur_acc, "ref_acc": self.ref_acc, "ref_pid": self.ref_pid,
              "plan": self.plan, "done": sorted(self.done_idx), "elapsed": round(self.duration(), 1)}
        tmp = self.dir / "state.tmp"
        tmp.write_text(json.dumps(st, indent=1))
        tmp.replace(self.dir / "state.json")

    def save(self):
        if self.config is None or self.ref_pid is None:
            return
        self.save_state()
        summary = {
            "run": self.run_id, "status": self.status, "k": self.k, "images": self.n,
            "batch": self.batch, "threshold": self.threshold, "seed": self.seed, "order": self.args.order,
            "parallel_vars": self.args.parallel_vars, "workers": self.workers,
            "code": self.code, "duration_s": round(self.duration(), 1),
            "variables_done": len(self.done_idx), "variables_total": len(self.plan),
            "evaluations": self.stats["evals"], "cached": self.stats["cached"], "stats": self.stats,
            "reference": {"acc": self.ref_acc, "id": self.ref_pid, "config": self.start,
                          "bits_mem": bits(self.start, self.k, "mem")[0],
                          "bits_ops": bits(self.start, self.k, "ops")[0]},
            "final": {"acc": self.cur_acc, "config": self.config,
                      "id": point_id(self.code, self.k, self.n, self.batch, self.config),
                      "bits_mem": bits(self.config, self.k, "mem")[0],
                      "bits_ops": bits(self.config, self.k, "ops")[0],
                      "kbits_mem": bits(self.config, self.k, "mem")[1] / 1000},
            "path": self.path,
        }
        try:
            summary["passes"] = pass_stats(self.dir, summary["reference"]["bits_mem"])
        except Exception:
            pass
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=1))
        (self.dir / "config.hpp").write_text(make_config_hpp(
            self.config, f"exploration {self.run_id} : {self.cur_acc:.2f} % sur {self.n} images "
                         f"(référence {self.ref_acc:.2f} %, seuil {self.threshold} pt), noyau {self.k}x{self.k}"))
        try:
            plot_run(self.dir, self.cache)
            plot_run(self.dir, self.cache, zoom=True)
            plot_formats(self.dir)
            plot_progress(self.dir)
            if self.ref_seq:
                plot_curves(self.dir, self.ref_seq, self.threshold, self.args.z, self.args.min_images)
        except Exception as e:      # un graphe raté ne doit jamais arrêter l'exploration
            console.log(f"[red]graphe non généré : {e}")
