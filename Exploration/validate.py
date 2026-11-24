#!/usr/bin/env python3
"""Teste une ou plusieurs configurations virgule fixe sur beaucoup d'images et sur d'autres batches.

L'exploration ne mesure la précision que sur les 1000 premières images de data_batch_1 : ce
script vérifie qu'une config trouvée tient sur d'autres images (test_batch, autres batches).

CONFIG peut être :
    <run>          config finale d'un run (préfixe du nom, ex. 20261119-223144)
    <run>:ref      config de référence (large) de ce run
    <id>           point du cache d'exploration (préfixe d'id, ex. 2a7ec1aa0f)
    chemin.hpp     un fichier config.hpp (ex. Exploration/runs/<run>/config.hpp)
    current        cpp/config.hpp
    float          modèle Python en float (python/cnn_fast.py), pour comparaison

Batches (-b) : test (test_batch.bin, défaut), 1 à 5 (data_batch_N.bin), all (les six), ou un nom de fichier.
Par défaut, toutes les images de chaque batch (10 000) ; -n et --start pour une tranche.

Chaque config est compilée une fois, puis les images sont réparties sur -j processus en parallèle
(cpp/main --order). Les résultats image par image sont gardés dans runs/validation.jsonl :
relancer avec les mêmes configs ne recalcule rien.

Affiche la précision par batch (intervalle de confiance à 95 %), et si plusieurs configs sont
données, la comparaison appariée avec la première (mêmes images : pertes, gains, écart ± IC95).

Exemples :
    python Exploration/validate.py 20261119-223144 20261119-223144:ref float
    python Exploration/validate.py Exploration/runs/20261119-223144_k5_t1_s5949/config.hpp -b test 2 3
    python Exploration/validate.py current -b 1 --start 1000 -n 9000 --md Results/validation.md
"""
import argparse, hashlib, json, math, os, re, subprocess, sys, tempfile, threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explo import paths
from explo.cache import Cache, find_run
from explo.formats import FMT, NAMES, bits, code_hash, pack, unpack
from explo.runner import RE_TRACE, Runner

console = Console()
DATA = paths.ROOT / "data" / "cifar-10-batches-bin"
VALID_FILE = paths.RUNS / "validation.jsonl"
BATCH_SIZE = 10000
EXPLO_BATCH, EXPLO_N = "data_batch_1.bin", 1000      # images utilisées par l'exploration
MACRO2NAME = {FMT[n][1]: n for n in NAMES}


# ============================================================
# Configurations
# ============================================================

def macros_of(config):
    """{nom: [I, F]} -> {MACRO_W: W, MACRO_I: I}"""
    m = {}
    for n, (i, f) in config.items():
        m[f"{FMT[n][1]}_W"], m[f"{FMT[n][1]}_I"] = i + f, i
    return m


def parse_hpp(path):
    """Lit les #define X_W / X_I d'un config.hpp. Un accumulateur à W = 0 (automatique) reste
    dans les macros (compilation) mais pas dans la config (calcul des bits)."""
    txt = Path(path).read_text()
    m = {f"{a}_{b}": int(v) for a, b, v in re.findall(r"#define\s+(\w+)_(W|I)\s+(-?\d+)", txt)
         if a in MACRO2NAME}
    config, auto = {}, []
    for macro, n in MACRO2NAME.items():
        w, i = m.get(f"{macro}_W"), m.get(f"{macro}_I")
        if w is None or i is None:
            continue
        if w == 0:
            auto.append(n)
        else:
            config[n] = [i, w - i]
    return m, config, auto


def resolve(spec):
    """Retourne {label, kind ('fixed'|'float'), macros, config, note}."""
    if spec == "float":
        return dict(label="float", kind="float", macros=None, config=None, note="python/cnn_fast.py, float32")
    if spec == "current":
        spec = str(paths.CPP / "config.hpp")
    p = Path(spec)
    if p.suffix == ".hpp" and p.exists():
        macros, config, auto = parse_hpp(p)
        try:
            label = str(p.resolve().relative_to(paths.ROOT))
        except ValueError:
            label = str(p)
        note = f"accumulateurs automatiques : {', '.join(auto)}" if auto else ""
        return dict(label=label, kind="fixed", macros=macros, config=config, note=note)

    want_ref = spec.endswith(":ref")
    prefix = spec[:-4] if want_ref else spec
    d = find_run(prefix) if not re.fullmatch(r"[0-9a-f]{4,10}", prefix) else None
    if d:
        short = d.name.rsplit("_", 1)[-1]
        if want_ref:
            r = json.loads((d / "reference.json").read_text())
            return dict(label=f"{short}:ref", kind="fixed", macros=macros_of(r["config"]), config=r["config"],
                        note=f"référence du run {d.name} ({r['acc']:.1f} % sur {EXPLO_N} img d'exploration)")
        s = json.loads((d / "summary.json").read_text())
        f = s["final"]
        return dict(label=short, kind="fixed", macros=macros_of(f["config"]), config=f["config"],
                    note=f"final du run {d.name} ({f['acc']:.1f} % sur {s['images']} img d'exploration)")
    m = [e for pid, e in Cache().data.items() if pid.startswith(prefix) and "acc" in e]
    if len(m) == 1:
        e = m[0]
        return dict(label=e["id"], kind="fixed", macros=macros_of(e["config"]), config=e["config"],
                    note=f"point du cache ({e['acc']:.1f} % sur {e['n']} img d'exploration)")
    sys.exit(f"« {spec} » : ni run, ni point unique du cache, ni fichier .hpp, ni current/float")


def batch_name(b):
    if b in ("test", "t"):
        return "test_batch.bin"
    if b in "12345" and len(b) == 1:
        return f"data_batch_{b}.bin"
    return b


# ============================================================
# Résultats image par image (cache runs/validation.jsonl)
# ============================================================

class Store:
    def __init__(self):
        self.data = {}
        if VALID_FILE.exists():
            for line in open(VALID_FILE):
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self.data.setdefault(e["key"], []).append(e)

    @staticmethod
    def key(cfg, k, batch):
        if cfg["kind"] == "float":
            h = hashlib.sha1()
            for f in ("cnn_fast.py", "read_image.py", "extractCoeff.py", "utils.py"):
                h.update((paths.ROOT / "python" / f).read_bytes())
            code, ck = "py" + h.hexdigest()[:8], "float"
        else:
            code, ck = code_hash(), ",".join(f"{m}={v}" for m, v in sorted(cfg["macros"].items()))
        return hashlib.sha1(f"{code}|k{k}|{batch}|{ck}".encode()).hexdigest()[:12]

    def get(self, key, start, n):
        """Succès (liste de 0/1) des images [start, start + n) si déjà calculés."""
        for e in self.data.get(key, []):
            if e["start"] <= start and start + n <= e["start"] + e["n"]:
                ok = unpack(e["ok"], e["n"])
                return ok[start - e["start"]: start - e["start"] + n]
        return None

    def put(self, key, label, batch, start, ok):
        e = dict(key=key, label=label, batch=batch, start=start, n=len(ok), acc=round(100 * sum(ok) / len(ok), 3),
                 ok=pack(ok), date=datetime.now().isoformat(timespec="seconds"))
        self.data.setdefault(key, []).append(e)
        with open(VALID_FILE, "a") as f:
            f.write(json.dumps(e, separators=(",", ":")) + "\n")


# ============================================================
# Évaluation
# ============================================================

def compile_fixed(cfg, tag):
    exe = paths.BUILD / "bin" / f"validate_{tag}"
    d = [f'-DPROJECT_ROOT="{paths.ROOT}"'] + [f"-D{m}={v}" for m, v in cfg["macros"].items()]
    cmd = [paths.CXX, *paths.CXXFLAGS, *d, "-I", str(paths.CPP), str(paths.CPP / "main.cpp"),
           str(paths.CPP / "cnn.cpp"), str(paths.BUILD / "obj" / "extract_coeff.o"),
           str(paths.BUILD / "obj" / "read_image.o"), "-o", str(exe)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"Échec de compilation de {cfg['label']} :\n{r.stderr[-2000:]}")
    return exe


def run_fixed(exe, k, batch, idx, jobs, progress, task):
    """Lance jobs processus cpp/main sur les indices idx, retourne {indice: 0/1}."""
    chunks = [idx[i::jobs] for i in range(jobs) if idx[i::jobs]]
    res, lock = {}, threading.Lock()

    def one(chunk):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", dir=paths.BUILD, delete=False) as f:
            f.write(" ".join(map(str, chunk)))
            order = f.name
        try:
            p = subprocess.Popen([str(exe), str(len(chunk)), str(k), batch, "--trace", "--order", order],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            got = 0
            for line in p.stdout:
                m = RE_TRACE.match(line)
                if m:
                    with lock:
                        res[int(m.group(2))] = int(m.group(3) == m.group(4))
                    got += 1
                    progress.advance(task)
            err = p.stderr.read()
            p.wait()
            if p.returncode or got != len(chunk):
                raise RuntimeError(f"cpp/main (code {p.returncode}, {got}/{len(chunk)} images) : {err[-1000:]}")
        finally:
            os.unlink(order)

    with ThreadPoolExecutor(len(chunks)) as ex:
        for f in [ex.submit(one, c) for c in chunks]:
            f.result()
    return res


def run_float(k, batch, start, n, progress, task):
    sys.path.insert(0, str(paths.ROOT / "python"))
    from cnn_fast import cnn_fast
    from extractCoeff import parse_tensors
    from read_image import load_batch
    import numpy as np
    tensors = parse_tensors(str(paths.ROOT / "data" / "coef" / f"CNN_coeff_{k}x{k}.txt"))
    images, labels = load_batch(str(DATA / batch))
    ok = []
    for a in range(start, start + n, 250):
        b = min(a + 250, start + n)
        pred = np.argmax(cnn_fast(images[a:b], tensors), axis=1)
        ok += [int(x) for x in pred == labels[a:b]]
        progress.advance(task, b - a)
    return ok


# ============================================================
# Statistiques et affichage
# ============================================================

def wilson(c, n, z=1.96):
    """Intervalle de confiance à 95 % d'une proportion (en %)."""
    if n == 0:
        return 0.0, 0.0
    p = c / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (mid - h), 100 * (mid + h)


def paired(base, other):
    """Comparaison image par image : (pertes, gains, écart en points, demi-largeur IC95)."""
    n = len(base)
    lost = sum(1 for a, b in zip(base, other) if a and not b)
    won = sum(1 for a, b in zip(base, other) if b and not a)
    diff = (won - lost) / n
    var = (lost + won) / n - diff * diff
    return lost, won, 100 * diff, 100 * 1.96 * math.sqrt(max(var, 0) / n)


def report(cfgs, batches, results, k, md_path):
    bnames = [b for b, _, _ in batches]
    md = [f"# Validation des configurations (k={k})", "",
          f"Généré par `Exploration/validate.py` le {datetime.now():%Y-%m-%d %H:%M}.", ""]

    t = Table(title="Précision (IC 95 %)", title_justify="left")
    t.add_column("config"); t.add_column("bits mem", justify="right")
    for b, s, n in batches:
        t.add_column(f"{b}\n[{s}, {s + n})", justify="right")
    t.add_column("total", justify="right")
    md += ["| config | bits mem | " + " | ".join(f"{b} [{s}, {s + n})" for b, s, n in batches) + " | total |",
           "|---" * (len(batches) + 3) + "|"]
    for c in cfgs:
        cells, allok = [], []
        for b in bnames:
            ok = results[c["label"]][b]
            allok += ok
            lo, hi = wilson(sum(ok), len(ok))
            cells.append(f"{100 * sum(ok) / len(ok):.2f} % [{lo:.1f}, {hi:.1f}]")
        lo, hi = wilson(sum(allok), len(allok))
        cells.append(f"{100 * sum(allok) / len(allok):.2f} % [{lo:.1f}, {hi:.1f}]  ({len(allok)} img)")
        bm = (f"{bits(c['config'], k, 'mem')[0]:.2f}" if c["config"] and len(c["config"]) == len(NAMES)
              else ("32 (float)" if c["kind"] == "float" else "—"))
        t.add_row(c["label"], bm, *cells)
        md.append(f"| {c['label']} | {bm} | " + " | ".join(cells) + " |")
    console.print(t)

    if len(cfgs) > 1:
        base = cfgs[0]
        t2 = Table(title=f"Comparaison appariée avec {base['label']} (mêmes images) : écart ± IC95 — pertes / gains",
                   title_justify="left")
        t2.add_column("config")
        md += ["", f"Comparaison appariée avec **{base['label']}** (mêmes images) : écart ± IC95 (pertes / gains)", "",
               "| config | " + " | ".join(bnames) + " | total |", "|---" * (len(bnames) + 2) + "|"]
        for b in bnames + ["total"]:
            t2.add_column(b, justify="right")
        for c in cfgs[1:]:
            cells, A, B = [], [], []
            for b in bnames:
                x, y = results[base["label"]][b], results[c["label"]][b]
                A += x; B += y
                lost, won, d, h = paired(x, y)
                cells.append(f"{d:+.2f} ± {h:.2f} pt  ({lost}/{won})")
            lost, won, d, h = paired(A, B)
            cells.append(f"{d:+.2f} ± {h:.2f} pt  ({lost}/{won})")
            t2.add_row(c["label"], *cells)
            md.append(f"| {c['label']} | " + " | ".join(cells) + " |")
        console.print(t2)

    notes = [f"{c['label']} : {c['note']}" for c in cfgs if c["note"]]
    if any(b == EXPLO_BATCH and s < EXPLO_N for b, s, _ in batches):
        notes.append(f"attention : les images 0 à {EXPLO_N - 1} de {EXPLO_BATCH} sont celles de l'exploration "
                     f"(--start {EXPLO_N} pour les exclure)")
    for x in notes:
        console.print(f"[dim]{x}")
    if md_path:
        md += [""] + [f"- {x}" for x in notes] + [""]
        Path(md_path).write_text("\n".join(md))
        console.print(f"rapport écrit dans [bold]{md_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="\n".join(__doc__.split("\n")[2:]))
    ap.add_argument("configs", nargs="+", metavar="CONFIG")
    ap.add_argument("-b", "--batches", nargs="+", default=["test"], help="test, 1..5, all ou nom de fichier")
    ap.add_argument("-n", type=int, default=BATCH_SIZE, help="images par batch (défaut : toutes)")
    ap.add_argument("--start", type=int, default=0, help="première image de chaque batch (défaut 0)")
    ap.add_argument("-k", type=int, default=5, choices=(3, 5))
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4, help="processus en parallèle")
    ap.add_argument("--no-cache", action="store_true", help="recalcule même si déjà dans runs/validation.jsonl")
    ap.add_argument("--md", help="écrit aussi les tableaux dans ce fichier Markdown")
    a = ap.parse_args()

    names = ["test", "1", "2", "3", "4", "5"] if a.batches == ["all"] else a.batches
    batches = []
    for b in map(batch_name, names):
        if not (DATA / b).exists():
            sys.exit(f"batch introuvable : {DATA / b}")
        n = min(a.n, BATCH_SIZE - a.start)
        if n <= 0:
            sys.exit(f"--start {a.start} au-delà des {BATCH_SIZE} images")
        batches.append((b, a.start, n))
    cfgs = [resolve(s) for s in a.configs]
    seen = set()
    for c in cfgs:                       # deux fois la même étiquette : on numérote
        while c["label"] in seen:
            c["label"] += "'"
        seen.add(c["label"])

    store = Store()
    runner = Runner(); runner.prepare()
    results = {c["label"]: {} for c in cfgs}
    with Progress(TextColumn("{task.description}"), BarColumn(), MofNCompleteColumn(),
                  TimeRemainingColumn(), console=console) as progress:
        for c in cfgs:
            exe = None
            for b, s, n in batches:
                key = Store.key(c, a.k, b)
                ok = None if a.no_cache else store.get(key, s, n)
                task = progress.add_task(f"{c['label']:>16} {b:<18}", total=n)
                if ok is None:
                    if c["kind"] == "float":
                        ok = run_float(a.k, b, s, n, progress, task)
                    else:
                        if exe is None:
                            progress.update(task, description=f"{c['label']:>16} compilation…")
                            exe = compile_fixed(c, key)
                            progress.update(task, description=f"{c['label']:>16} {b:<18}")
                        res = run_fixed(exe, a.k, b, list(range(s, s + n)), a.jobs, progress, task)
                        ok = [res[i] for i in range(s, s + n)]
                    store.put(key, c["label"], b, s, ok)
                else:
                    progress.update(task, completed=n, description=f"{c['label']:>16} {b:<18} (cache)")
                results[c["label"]][b] = ok
            if exe is not None:
                exe.unlink(missing_ok=True)
    report(cfgs, batches, results, a.k, a.md)


if __name__ == "__main__":
    main()
