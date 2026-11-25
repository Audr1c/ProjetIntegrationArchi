#!/usr/bin/env python3
"""
Résumé des résultats Catapult SANS interface graphique : lit les rapports texte d'une ou plusieurs
solutions et produit un tableau Markdown (et/ou JSON) : latence, débit, surface, DSP, LUT, slack,
mémoires (estimation BRAM), boucles les plus coûteuses, verdict SCVerify.

Python 3 standard seulement (aucune dépendance) : tourne sur les machines de l'école comme à la maison.

Fichiers lus dans un dossier de solution (ex. hls/work/Catapult_1/cnn.v1/) :
    rtl.rpt      (go extract)   surface (Bill Of Materials, Area Scores), timing (slack)
    cycle.rpt    (go schedule)  horloge, mémoires, boucles (itérations, c-steps, II), profil des cycles
    scverify/*/sim.log          verdict de la simulation RTL (PASSED / FAILED, nb de comparaisons)
    ../../catapult.log          transcript complet de la session (testbench C++ compris)

Usage :
    python3 hls/catapult_report.py hls/work/Catapult_1            # toutes les solutions du projet
    python3 hls/catapult_report.py hls/work/Catapult_1/cnn.v3      # une solution (détail)
    python3 hls/catapult_report.py hls/rapports/                   # rapports déjà sauvegardés
    python3 hls/catapult_report.py --save hls/rapports hls/work/Catapult_1/cnn.v1
        -> copie rtl.rpt, cycle.rpt, messages.txt, directives.tcl, sim.log, catapult.log dans
           hls/rapports/cnn.v1_<date>/ (versionné par git) et y écrit resume.md
Options : --json F (toutes les données), --top N (boucles listées, défaut 12), -o F (Markdown dans F),
          --detail (détail de chaque solution même s'il y en a plusieurs).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path

# Capacités des Zynq-7000 des cartes Zybo Z7 (DS190) : BRAM en blocs de 18 Kb
DEVICES = {
    "xc7z010": {"BRAM18": 120, "DSP": 80, "LUT": 17600},
    "xc7z020": {"BRAM18": 280, "DSP": 220, "LUT": 53200},
}
# Formes possibles d'un bloc RAMB18 de la série 7 (profondeur, largeur)
BRAM18_SHAPES = [(16384, 1), (8192, 2), (4096, 4), (2048, 9), (1024, 18), (512, 36)]

FILES_TO_SAVE = ["rtl.rpt", "cycle.rpt", "messages.txt", "directives.tcl"]

# Toute la sortie est en ASCII : Catapult et Questa affichent mal les accents (UTF-8 lu en Latin-1).
_ASCII = {"«": '"', "»": '"', "≈": "~", "→": "->", "—": "-", "–": "-", "…": "...", "×": "x", "µ": "u",
          "⚠": "!", "\u00a0": " ", "\u202f": " "}


def to_ascii(text: str) -> str:
    text = "".join(_ASCII.get(c, c) for c in text)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).encode("ascii", "replace").decode()


# ---------------------------------------------------------------- lecture des rapports

def split_sections(text: str) -> dict[str, list[str]]:
    """Découpe un rapport Catapult en sections : titre = ligne non indentée (hors en-tête « -- »)."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if line and not line[0].isspace() and not line.startswith("--"):
            current = line.strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line.rstrip("\n"))
    return sections


def find_section(sections: dict[str, list[str]], prefix: str) -> list[str]:
    for title, lines in sections.items():
        if title.startswith(prefix):
            return lines
    return []


def parse_table(lines: list[str]) -> list[dict[str, str]]:
    """Tableau à colonnes fixes : en-tête, ligne de tirets (donne la largeur des colonnes), lignes.
    S'arrête à la première ligne vide. Renvoie une liste de dictionnaires {colonne: texte}."""
    for i in range(1, len(lines)):
        if re.fullmatch(r"\s*-+( +-+)*\s*", lines[i]) and lines[i].strip():
            dashes, header = lines[i], lines[i - 1]
            spans = [(m.start(), m.end()) for m in re.finditer(r"-+", dashes)]
            names = [header[a:b + 1].strip() for a, b in spans]
            # dernière colonne : jusqu'au bout de la ligne
            rows = []
            for line in lines[i + 1:]:
                if not line.strip():
                    break
                cells = []
                for k, (a, b) in enumerate(spans):
                    end = spans[k + 1][0] if k + 1 < len(spans) else len(line)
                    cells.append(line[a:end].strip())
                rows.append(dict(zip(names, cells)))
            return rows
    return []


def num(s: str | None):
    """'46123242' -> 46123242, '4.24' -> 4.24, '(126)' -> 126, sinon None."""
    if s is None:
        return None
    s = s.strip().strip("()").replace(",", "")
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def bram18_estimate(depth: int, width: int) -> int:
    """Nombre minimal de RAMB18 pour une mémoire depth x width (sans tenir compte des ports)."""
    return min(math.ceil(width / w) * math.ceil(depth / d) for d, w in BRAM18_SHAPES)


def parse_memories(lines: list[str]) -> list[dict]:
    mems, cur = [], None
    for line in lines:
        m = re.match(r"\s*Resource Name:\s*(\S+)", line)
        if m:
            cur = {"name": m.group(1)}
            mems.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"\s*Memory Component:\s*(.+?)\s+Size:\s*(\d+)\s*x\s*(\d+)", line)
        if m:
            cur["component"] = m.group(1).strip()
            cur["depth"], cur["width"] = int(m.group(2)), int(m.group(3))
        m = re.match(r"\s*External:\s*(\w+)", line)
        if m:
            cur["external"] = m.group(1) == "true"
    for mem in mems:
        comp = mem.get("component", "").lower()
        is_block = ("block" in comp or "rom" in comp) and "register" not in comp
        mem["bram18"] = bram18_estimate(mem["depth"], mem["width"]) if is_block and "depth" in mem else 0
    return mems


def parse_sim_log(path: Path) -> dict:
    text = path.read_text(errors="replace")
    res = {"file": str(path)}
    m = re.findall(r"Simulation (PASSED|FAILED)", text)
    res["verdict"] = m[-1] if m else "INCONNU (simulation interrompue ?)"
    for key in ("comparison count", "error count", "capture count"):
        m = re.findall(key + r"\s*=\s*(\d+)", text)
        if m:
            res[key.replace(" ", "_")] = sum(int(x) for x in m)
    m = re.search(r"Throughput: (.+)", text)
    if m:
        res["throughput"] = m.group(1).strip()
    m = re.search(r"Latency: (.+)", text)
    if m:
        res["latency"] = m.group(1).strip()
    m = re.findall(r"Elapsed time: ([\d:]+)", text)
    if m:
        res["elapsed"] = m[-1]
    res["errors"] = [l.strip("# ").strip() for l in text.splitlines() if re.match(r"#?\s*Error:", l)][:5]
    return res


def parse_solution(sol: Path) -> dict:
    """Toutes les données utiles d'un dossier de solution (ou d'un dossier de rapports sauvegardés)."""
    d: dict = {"dir": str(sol), "name": sol.name}
    rtl = (sol / "rtl.rpt").read_text(errors="replace") if (sol / "rtl.rpt").exists() else ""
    cyc = (sol / "cycle.rpt").read_text(errors="replace") if (sol / "cycle.rpt").exists() else ""
    s_rtl, s_cyc = split_sections(rtl), split_sections(cyc)

    for title in list(s_rtl) + list(s_cyc):
        if title.startswith("Solution Settings:"):
            d["name"] = title.split(":", 1)[1].strip()
    m = re.search(r"Current state:\s*(\S+)", rtl or cyc)
    d["state"] = m.group(1) if m else "?"

    # Processus : latence / débit en cycles (ligne « Design Total »)
    procs = parse_table(find_section(s_rtl, "Processes/Blocks") or find_section(s_cyc, "Processes/Blocks"))
    # Un processus par bloc hiérarchique (layer1, layer2, ...) : latence de chaque couche
    d["processes"] = [{"name": row.get("Process", "").strip(), "real_ops": num(row.get("Real Operation(s) count")),
                       "latency_cycles": num(row.get("Latency")), "throughput_cycles": num(row.get("Throughput"))}
                      for row in procs
                      if row.get("Process", "").strip() and not row.get("Process", "").startswith("Design Total")]
    for row in procs:
        if row.get("Process", "").startswith("Design Total"):
            d["real_ops"] = num(row.get("Real Operation(s) count"))
            d["latency_cycles"] = num(row.get("Latency"))
            d["throughput_cycles"] = num(row.get("Throughput"))
            d["II"] = num(row.get("II"))

    # Horloge
    clocks = parse_table(find_section(s_cyc, "Clock Information"))
    if clocks:
        d["clock_ns"] = num(clocks[0].get("Period"))
    else:
        m = re.search(r"Clock period or pin-to-reg delay constraint \(\w+\)\s*:\s*([\d.]+)", rtl)
        d["clock_ns"] = float(m.group(1)) if m else None
    if d.get("clock_ns") and d.get("latency_cycles") is not None:
        d["latency_ms"] = d["latency_cycles"] * d["clock_ns"] * 1e-6
    if d.get("clock_ns") and d.get("throughput_cycles"):
        d["per_second"] = 1e9 / (d["throughput_cycles"] * d["clock_ns"])

    # Surface : total du Bill Of Materials (colonnes Area(xxx) selon la bibliothèque)
    bom = find_section(s_rtl, "Bill Of Materials")
    header = next((l for l in bom if "Component Name" in l), "")
    cols = ["Area Score"] + re.findall(r"Area\(([^)]+)\)", header)
    for line in bom:
        if "TOTAL AREA" in line:
            values = re.findall(r"[-\d.]+", line.split(":", 1)[1])
            d["area"] = {c: num(v) for c, v in zip(cols, values)}
    for line in find_section(s_rtl, "Area Scores"):
        if "Total Area Score:" in line:
            d["area_score"] = num(line.split(":")[1].split()[-1])   # Post-Assignment
        if line.strip().startswith("Total Reg:"):
            d["area_reg"] = num(line.split(":")[1].split()[-1])

    # Timing
    m = re.search(r"Max Delay:\s*([-\d.]+)", rtl)
    d["max_delay_ns"] = float(m.group(1)) if m else None
    m = re.search(r"Slack:\s*([-\d.]+)", rtl)
    d["slack_ns"] = float(m.group(1)) if m else None

    # Mémoires
    d["memories"] = parse_memories(find_section(s_cyc, "Memory Resources"))
    d["bram18_total"] = sum(mem["bram18"] for mem in d["memories"])

    # Boucles et profil
    d["loops"] = parse_table(find_section(s_cyc, "Loops"))
    d["profile"] = parse_table(find_section(s_cyc, "Loop Execution Profile"))

    # Simulation SCVerify
    sims = sorted(sol.glob("scverify/*/sim.log")) + sorted(sol.glob("sim*.log"))
    d["sims"] = [parse_sim_log(p) for p in sims]
    return d


def find_solutions(paths: list[Path]) -> list[Path]:
    sols = []
    for p in paths:
        if (p / "rtl.rpt").exists() or (p / "cycle.rpt").exists():
            sols.append(p)
        else:
            found = {r.parent for pat in ("rtl.rpt", "cycle.rpt") for r in p.rglob(pat)
                     if "scverify" not in r.parts}
            sols.extend(sorted(found, key=natural_key))
    return sols


def natural_key(p: Path):
    """cnn.v2 avant cnn.v10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(p))]


# ---------------------------------------------------------------- sortie Markdown

def fmt(v, spec="", none="—"):
    if v is None:
        return none
    if isinstance(v, (int, float)) and spec:
        return format(v, spec)
    return str(v)


def fmt_time(ms):
    if ms is None:
        return "—"
    if ms >= 1000:
        return f"{ms / 1000:.2f} s"
    if ms >= 1:
        return f"{ms:.2f} ms"
    return f"{ms * 1000:.2f} µs"


def summary_table(sols: list[dict]) -> str:
    out = ["| Solution | État | Latence (cycles) | Latence | Débit (cycles) | appels/s | Surface | DSP | LUT | "
           "Slack (ns) | BRAM18 est. | SCVerify |",
           "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|"]
    for d in sols:
        area = d.get("area") or {}
        sim = ", ".join(f"{s['verdict']}" for s in d["sims"]) or "non lancée"
        out.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            d["name"], d["state"], fmt(d.get("latency_cycles"), ","),
            fmt_time(d.get("latency_ms")),
            fmt(d.get("throughput_cycles"), ","), fmt(d.get("per_second"), ",.2f"),
            fmt(d.get("area_score"), ",.0f"), fmt(area.get("DSP"), ".0f"), fmt(area.get("LUTs"), ",.0f"),
            fmt(d.get("slack_ns"), ".2f"), d["bram18_total"], sim))
    return "\n".join(out)


def detail(d: dict, top: int) -> str:
    out = [f"## {d['name']}  (état `{d['state']}`)", f"Dossier : `{d['dir']}`", ""]
    clk = d.get("clock_ns")
    out.append(f"- Horloge : {fmt(clk)} ns" + (f" ({1000 / clk:.0f} MHz)" if clk else ""))
    out.append(f"- Latence : {fmt(d.get('latency_cycles'), ',')} cycles"
               + (f" = {fmt_time(d['latency_ms'])}" if d.get("latency_ms") is not None else ""))
    out.append(f"- Débit : 1 appel / {fmt(d.get('throughput_cycles'), ',')} cycles"
               + (f" = {d['per_second']:.2f} appels/s" if d.get("per_second") else ""))
    if d.get("area"):
        out.append(f"- Surface : score total {fmt(d.get('area_score'), ',.0f')} (Area Scores) ; datapath (Bill Of Materials) : "
                   + ", ".join(f"{k} = {fmt(v, ',.0f')}" for k, v in d["area"].items()))
    out.append(f"- Timing : chemin critique {fmt(d.get('max_delay_ns'), '.2f')} ns, slack {fmt(d.get('slack_ns'), '.2f')} ns"
               + ("  ⚠ NÉGATIF" if (d.get("slack_ns") or 0) < 0 else ""))
    out.append("")

    procs = d.get("processes") or []
    if len(procs) > 1:
        out += ["### Blocs (processus)", "", "| Bloc | Operations | Latence (cycles) | Debit (cycles) |", "|---|--:|--:|--:|"]
        for pr in procs:
            out.append(f"| `{pr['name']}` | {fmt(pr['real_ops'], ',')} | {fmt(pr['latency_cycles'], ',')} | "
                       f"{fmt(pr['throughput_cycles'], ',')} |")
        out.append("")

    if d["memories"]:
        out += ["### Mémoires", "",
                "| Ressource | Composant | Taille (mots × bits) | Kbit | Externe | BRAM18 est. |",
                "|---|---|--:|--:|---|--:|"]
        for m in d["memories"]:
            if "depth" not in m:
                continue
            out.append(f"| `{m['name']}` | {m.get('component', '?')} | {m['depth']} × {m['width']} | "
                       f"{m['depth'] * m['width'] / 1024:.1f} | {'oui' if m.get('external') else 'non'} | {m['bram18'] or ''} |")
        tot = d["bram18_total"]
        use = ", ".join(f"{dev} : {tot}/{cap['BRAM18']} ({100 * tot / cap['BRAM18']:.0f} %)"
                        for dev, cap in DEVICES.items())
        out += ["", f"Total estimé : **{tot} RAMB18** — {use}. "
                "(Estimation par la forme des mémoires ; le chiffre réel vient de Precision/Vivado. "
                "Une ROM peut aussi partir en LUT.)", ""]
        if d.get("area"):
            a = d["area"]
            out.append("Datapath : " + ", ".join(
                f"{k} {fmt(a.get(k), ',.0f')}/{cap[k]} ({100 * (a.get(k) or 0) / cap[k]:.1f} %) sur {dev}"
                for dev, cap in DEVICES.items() for k in ("DSP",) if a.get(k) is not None))
            out.append("")

    if d["profile"]:
        prof = sorted(d["profile"], key=lambda r: -(num(r.get("Total Cycles")) or 0))[:top]
        loops = {(r.get("Loop") or "").strip(): r for r in d["loops"]}
        out += [f"### Boucles les plus coûteuses (top {top})", "",
                "| Boucle | Cycles | % | Itérations | C-steps | II | Unroll |", "|---|--:|--:|--:|--:|--:|--:|"]
        for r in prof:
            name = (r.get("Loop") or "").strip()
            lp = loops.get(name, {})
            out.append(f"| `{name}` | {fmt(num(r.get('Total Cycles')), ',')} | {r.get('% of Overall Design Cycles', '')} | "
                       f"{lp.get('Iterations', '')} | {lp.get('C-Steps', '')} | {lp.get('Init', '')} | {lp.get('Unroll', '')} |")
        out.append("")

    for s in d["sims"]:
        out += [f"### SCVerify : {s['verdict']}", f"`{s['file']}`", ""]
        for k in ("comparison_count", "error_count", "throughput", "latency", "elapsed"):
            if k in s:
                out.append(f"- {k} : {s[k]}")
        for e in s["errors"]:
            out.append(f"- ⚠ {e}")
        out.append("")
    if not d["sims"]:
        out += ["SCVerify : pas de `sim.log` (simulation RTL non lancée ou pas encore finie).", ""]
    return "\n".join(out)


def save(dest_root: Path, sol: Path) -> Path:
    """Copie les rapports d'une solution dans dest_root/<solution>_<date>/ (pour git)."""
    dest = dest_root / f"{sol.name}_{time.strftime('%Y%m%d-%H%M')}"
    dest.mkdir(parents=True, exist_ok=True)
    for f in FILES_TO_SAVE:
        if (sol / f).exists():
            shutil.copy2(sol / f, dest / f)
    for log in sol.glob("scverify/*/sim.log"):
        shutil.copy2(log, dest / f"sim_{log.parent.name}.log")
    transcript = sol.parent.parent / "catapult.log"           # hls/work/catapult.log
    if transcript.exists():
        shutil.copy2(transcript, dest / "catapult.log")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", type=Path, help="dossiers de solution, de projet Catapult ou de rapports")
    ap.add_argument("--save", type=Path, metavar="DOSSIER", help="copier d'abord les rapports dans DOSSIER/<solution>_<date>/")
    ap.add_argument("--json", type=Path, help="écrire toutes les données extraites en JSON")
    ap.add_argument("-o", "--output", type=Path, help="écrire le Markdown dans ce fichier")
    ap.add_argument("--top", type=int, default=12, help="nombre de boucles listées (défaut 12)")
    ap.add_argument("--detail", action="store_true", help="détail de chaque solution même s'il y en a plusieurs")
    args = ap.parse_args()

    sols = find_solutions(args.paths)
    if not sols:
        print(to_ascii("Aucun rtl.rpt / cycle.rpt trouvé dans : " + ", ".join(map(str, args.paths))), file=sys.stderr)
        return 1
    if args.save:
        sols = [save(args.save, s) for s in sols]
        for s in sols:
            print(to_ascii(f"Rapports copiés dans {s}"), file=sys.stderr)

    data = [parse_solution(s) for s in sols]
    md = ["# Résultats Catapult", "", summary_table(data), ""]
    if len(data) == 1 or args.detail:
        md += [detail(d, args.top) for d in data]
    text = to_ascii("\n".join(md))

    if args.save:
        for s, d in zip(sols, data):
            (s / "resume.md").write_text(to_ascii("\n".join(["# Résultats Catapult", "", summary_table([d]), "",
                                                              detail(d, args.top)])))
    if args.json:
        args.json.write_text(json.dumps(data, indent=1))
    if args.output:
        args.output.write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
