"""Compilation d'une configuration (-D...) et exécution de cpp/main en mode --trace."""

import re
import subprocess
import sys
import threading
import time

from . import paths
from .formats import FMT, NAMES, width

# ============================================================
# Compilation et exécution du modèle C++
# ============================================================

RE_TRACE = re.compile(r"^T (\d+) (\d+) (\d+) (\d+) (\S+)")
RE_FINAL = re.compile(r"Got an accuracy of ([\d.]+)% \((\d+)/(\d+)\)")


class Runner:
    """Compile une configuration (-D...) et lance cpp/main dessus en mode --trace."""

    def __init__(self):
        (paths.BUILD / "obj").mkdir(parents=True, exist_ok=True)
        (paths.BUILD / "bin").mkdir(parents=True, exist_ok=True)
        self.procs = {}             # pid -> Popen
        self.cancelled = set()
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def prepare(self):
        """Objets communs (indépendants des formats), recompilés seulement si le code change."""
        newest = max(p.stat().st_mtime for p in paths.CPP.glob("*.[ch]pp"))
        for src in ("extract_coeff.cpp", "read_image.cpp"):
            obj = paths.BUILD / "obj" / src.replace(".cpp", ".o")
            if obj.exists() and obj.stat().st_mtime >= newest:
                continue
            r = subprocess.run([paths.CXX, *paths.CXXFLAGS, "-c", str(paths.CPP / src), "-o", str(obj)],
                               capture_output=True, text=True)
            if r.returncode:
                sys.exit(f"Échec de compilation de {src} :\n{r.stderr}")

    def defines(self, config):
        d = [f'-DPROJECT_ROOT="{paths.ROOT}"']
        for n in NAMES:
            macro = FMT[n][1]
            d += [f"-D{macro}_W={width(config, n)}", f"-D{macro}_I={config[n][0]}"]
        return d

    def cancel(self, pid):
        """Tue une évaluation devenue inutile."""
        with self.lock:
            self.cancelled.add(pid)
            p = self.procs.get(pid)
        if p:
            try:
                p.kill()
            except OSError:
                pass

    def uncancel(self, pid):
        with self.lock:
            self.cancelled.discard(pid)

    def kill_all(self):
        self.stop.set()
        with self.lock:
            procs = list(self.procs.values())
        for p in procs:
            try:
                p.kill()
            except OSError:
                pass

    def _is_cancelled(self, pid):
        with self.lock:
            return pid in self.cancelled or self.stop.is_set()

    def evaluate(self, config, k, n, batch, pid, order_file, on_stage, on_image):
        """
        on_image(rang, indice, succès, marge) -> True pour arrêter l'évaluation (arrêt anticipé).
        Retourne {"trace": [...], "acc", "correct", "n", ...} si complète,
                 {"trace": [...], "stopped": True} si arrêtée par on_image,
                 {"killed": True} si annulée, {"error": ...} en cas d'échec.
        """
        exe = paths.BUILD / "bin" / f"main_{pid}_{threading.get_ident()}"
        try:
            on_stage("compilation")
            t0 = time.time()
            cmd = [paths.CXX, *paths.CXXFLAGS, *self.defines(config), f"-DKS={k}", "-I", str(paths.CPP),
                   str(paths.CPP / "main.cpp"), str(paths.CPP / "cnn.cpp"),
                   str(paths.BUILD / "obj" / "extract_coeff.o"), str(paths.BUILD / "obj" / "read_image.o"),
                   "-o", str(exe)]
            # start_new_session : le Ctrl-C du terminal ne tue pas les enfants, c'est nous qui les arrêtons
            r = subprocess.run(cmd, capture_output=True, text=True, start_new_session=True)
            t_compile = time.time() - t0
            if r.returncode:
                return {"error": "compilation : " + r.stderr[-1500:]}
            if self._is_cancelled(pid):
                return {"killed": True, "n_done": 0}

            on_stage("inférence")
            t1 = time.time()
            args = [str(exe), str(n), str(k), batch, "--trace"]
            if order_file:
                args += ["--order", str(order_file)]
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, bufsize=1, start_new_session=True)
            with self.lock:
                self.procs[pid] = p
            trace, final, stopped = [], None, False
            for line in p.stdout:
                m = RE_TRACE.match(line)
                if m:
                    rank, idx, label, pred = (int(m.group(i)) for i in range(1, 5))
                    ok = int(label == pred)
                    trace.append((idx, ok, float(m.group(5))))
                    if on_image(rank, idx, ok, float(m.group(5))):
                        stopped = True
                        p.kill()
                        break
                    continue
                m = RE_FINAL.search(line)
                if m:
                    final = m
            err = "" if stopped else p.stderr.read()
            p.wait()
            with self.lock:
                self.procs.pop(pid, None)
            timing = {"t_compile": round(t_compile, 2), "t_run": round(time.time() - t1, 2)}
            if stopped:
                return {"trace": trace, "stopped": True, **timing}
            if self._is_cancelled(pid):
                return {"killed": True, "n_done": len(trace)}
            if p.returncode or not final:
                return {"error": f"exécution (code {p.returncode}) : {err[-1500:]}"}
            return {"trace": trace, "acc": float(final.group(1)), "correct": int(final.group(2)),
                    "n": int(final.group(3)), **timing}
        finally:
            exe.unlink(missing_ok=True)
