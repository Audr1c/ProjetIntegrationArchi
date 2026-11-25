#!/usr/bin/env python3
"""
Génère doc/carte/carte.html : carte interactive du projet (qui fait quoi, qui appelle qui, qui lit /
écrit quoi), à ouvrir dans un navigateur. Python standard uniquement.

Usage :  make carte          (ou python3 doc/carte/gen_carte.py [--quiet])
         regénérée aussi à chaque commit par le hook git installé par `make carte-hook`.

Trouvé AUTOMATIQUEMENT à chaque génération :
  - les fichiers du dépôt (git ls-files + nouveaux fichiers non ignorés) ;
  - leur description : docstring Python, commentaire d'en-tête C++ / Tcl / shell, titre Markdown ;
  - #include "…" (C++), imports Python entre fichiers du projet ;
  - cibles make (description « ## ») et ce que chaque recette lance ;
  - scripts / fichiers cités dans le code Tcl, shell, Python, C++ (chaînes, hors commentaires).
RÉDIGÉ À LA MAIN dans doc/carte/modele.py : rôles en une ligne, liens « écrit / lit » que l'analyse
ne voit pas, outils externes, parcours pas à pas. Les fichiers sans description sont signalés.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import modele  # noqa: E402

# Fichiers du dépôt montrés sur la carte (les dossiers volumineux sont des nœuds virtuels de modele.py)
EXCLUS = [r"^Exploration/runs/", r"^hls/Demo_FIR/", r"^hls/include/", r"^hls/rapports/", r"^doc/img/",
          r"^data/", r"^Results/", r"^hls/work", r"(^|/)\.", r"\.gitkeep$", r"__init__\.py$", r"\.pdf$",
          r"\.zip$", r"\.tgz$", r"^doc/carte/carte\.html$", r"^doc/carte/template\.html$", r"^Makefile$",
          r"^doc/hls/", r"^build/", r"^cpp/build/", r"\.png$"]
EXTENSIONS = {".py", ".cpp", ".hpp", ".h", ".tcl", ".sh", ".txt", ".md", ".bin", ""}

TYPES_LIENS = ["lance", "importe", "inclut", "lit", "ecrit", "depend", "synthetise", "pilote"]
# Un seul lien automatique par paire de nœuds : le plus « fort » de cette liste
PRIORITE = ["synthetise", "importe", "inclut", "lance", "ecrit", "pilote", "lit", "depend"]
# Fichiers dont le contenu n'est pas analysé (ils citent tout le dépôt)
NON_ANALYSES = [r"^doc/carte/"]


# ------------------------------------------------------------------ fichiers

def fichiers_depot() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    except (OSError, subprocess.CalledProcessError):
        out = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file()]
    res = []
    for f in sorted(set(x.strip() for x in out if x.strip())):
        p = ROOT / f
        if not p.exists() or p.is_char_device() or not p.is_file():   # périphériques : sandbox Claude
            continue
        if any(re.search(e, f) for e in EXCLUS):
            continue
        if p.suffix not in EXTENSIONS and p.name != "CMakeLists.txt":
            continue
        res.append(f)
    return res


def groupe_de(f: str) -> str:
    for prefixe, g in (("python/", "python"), ("ExplorationHLS/", "explohls"), ("Exploration/", "explo"), ("cpp/", "cpp"),
                       ("hls/ref/", "donnees"), ("hls/", "hls")):
        if f.startswith(prefixe):
            return g
    return "donnees"


def genre_de(f: str) -> str:
    suffixe = Path(f).suffix.lstrip(".")
    if f.endswith("CMakeLists.txt"):
        return "cmake"
    if suffixe in ("txt", "bin"):
        return "donnée"
    return suffixe or "shell"


# ------------------------------------------------------------------ descriptions

def nettoie(lignes: list[str], max_car: int = 900) -> str:
    texte = "\n".join(l.rstrip() for l in lignes).strip("\n")
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    return texte if len(texte) <= max_car else texte[:max_car].rsplit(" ", 1)[0] + " …"


def description(f: str) -> str:
    p = ROOT / f
    if p.suffix in (".bin",) or p.stat().st_size > 400_000:
        return ""
    try:
        txt = p.read_text(errors="replace")
    except OSError:
        return ""
    if p.suffix == ".py":
        try:
            doc = ast.get_docstring(ast.parse(txt)) or ""
        except SyntaxError:
            doc = ""
        return nettoie(doc.split("\n\n")[0].splitlines() if len(doc) > 900 else doc.splitlines())
    if p.suffix in (".cpp", ".hpp", ".h"):
        m = re.search(r"/\*(.*?)\*/", txt[:6000], flags=re.S)
        if m and txt[:m.start()].strip().replace("#ifndef", "").replace("#define", "").count("\n") < 6:
            lignes = [re.sub(r"^\s*\*\s?", "", l) for l in m.group(1).splitlines()]
            return nettoie(lignes)
        lignes = []
        for l in txt.splitlines():
            if l.startswith("//"):
                lignes.append(l[2:].strip())
            elif lignes:
                break
        return nettoie(lignes)
    if p.suffix == ".md":
        lignes = [l for l in txt.splitlines()[:12]]
        return nettoie(lignes, 500)
    if p.suffix in (".tcl", ".sh", ".txt", "") or p.name == "CMakeLists.txt":
        lignes = []
        for l in txt.splitlines():
            if l.startswith("#!"):
                continue
            if l.startswith("#"):
                c = l.lstrip("#").strip()
                if not re.fullmatch(r"[=\-_ ]*", c):
                    lignes.append(c)
            elif lignes or l.strip():
                break
        return nettoie(lignes)
    return ""


# ------------------------------------------------------------------ liens automatiques

def sans_commentaires_c(txt: str) -> str:
    txt = re.sub(r"/\*.*?\*/", " ", txt, flags=re.S)
    return re.sub(r"//[^\n]*", " ", txt)


def sans_commentaires_diese(txt: str) -> str:
    lignes = []
    for l in txt.splitlines():
        if l.lstrip().startswith("#"):
            continue
        lignes.append(re.sub(r";\s*#.*$", "", l))
    return "\n".join(lignes)


def chaines_python(txt: str) -> str:
    """Chaînes du code Python, sans les docstrings."""
    try:
        arbre = ast.parse(txt)
    except SyntaxError:
        return ""
    docs = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body:
            premier = n.body[0]
            if isinstance(premier, ast.Expr) and isinstance(getattr(premier, "value", None), ast.Constant):
                docs.add(id(premier.value))
    # seulement les chaînes sans espace (chemins, noms de fichiers) : pas les messages ni les textes d'aide
    morceaux = [n.value for n in ast.walk(arbre)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs
                and n.value.strip() and not re.search(r"\s", n.value.strip())]
    return "\n".join(morceaux)


def motifs_noeuds(noeuds: dict) -> dict[str, list[re.Pattern]]:
    """Expressions qui désignent un nœud dans un texte : chemin, nom de fichier s'il est unique, motifs du modèle."""
    noms = {}
    for nid, n in noeuds.items():
        if n["fichier"]:
            noms.setdefault(Path(nid).name, []).append(nid)
    borne = r"(?<![\w.])(?:[\w$().\-]*/)?{}(?![\w])"      # nom isolé, éventuellement précédé d'un chemin
    res = {}
    for nid, n in noeuds.items():
        pats = []
        if n["fichier"]:
            pats.append(borne.format(re.escape(nid)))
            if len(noms[Path(nid).name]) == 1:
                pats.append(borne.format(re.escape(Path(nid).name)))
        pats += n.get("motifs", [])
        res[nid] = [re.compile(p) for p in pats]
    return res


def cites(texte: str, motifs: dict, sauf: str) -> set[str]:
    return {nid for nid, pats in motifs.items() if nid != sauf and any(p.search(texte) for p in pats)}


def resout_import(f: str, module: str | None, niveau: int, nom: str | None, fichiers: set[str]) -> str | None:
    base = Path(f).parent
    if niveau > 0:
        for _ in range(niveau - 1):
            base = base.parent
        racines = [base]
    else:
        racines = [Path(f).parent, Path("python"), Path("Exploration")]
    for r in racines:
        cands = []
        if module:
            cands.append(r / (module.replace(".", "/") + ".py"))
            if nom:
                cands.append(r / module.replace(".", "/") / (nom + ".py"))
        elif nom:
            cands.append(r / (nom + ".py"))
        for c in cands:
            if str(c) in fichiers:
                return str(c)
    return None


def liens_automatiques(noeuds: dict, fichiers: list[str]) -> list[tuple]:
    liens = []
    ensemble = set(fichiers)
    motifs = motifs_noeuds(noeuds)
    for f in fichiers:
        p = ROOT / f
        if p.suffix == ".bin" or p.stat().st_size > 3_000_000 or any(re.search(e, f) for e in NON_ANALYSES):
            continue
        txt = p.read_text(errors="replace")
        if p.suffix in (".cpp", ".hpp", ".h"):
            for inc in re.findall(r'#\s*include\s*"([^"]+)"', txt):
                cible = _normalise(str(Path(f).parent / inc).replace("\\", "/"))
                if cible in ensemble:
                    liens.append((f, "inclut", cible, ""))
            for inc in re.findall(r"#\s*include\s*<([^>]+)>", txt):
                if inc in ("ac_fixed.h", "ac_int.h"):
                    liens.append((f, "inclut", "dir:acinclude", ""))
                elif inc == "mc_scverify.h" and "hls/stub/mc_scverify.h" in ensemble:
                    liens.append((f, "inclut", "hls/stub/mc_scverify.h", "PC ; Catapult : le vrai"))
            code = re.sub(r"^\s*#\s*include[^\n]*", "", sans_commentaires_c(txt), flags=re.M)
            for cible in cites("\n".join(re.findall(r'"(?:\\.|[^"\\\n])*"', code)), motifs, f):
                liens.append((f, "lit", cible, ""))
        elif p.suffix == ".py":
            try:
                arbre = ast.parse(txt)
            except SyntaxError:
                continue
            for n in ast.walk(arbre):
                if isinstance(n, ast.ImportFrom):
                    for a in n.names:
                        c = resout_import(f, n.module, n.level, a.name, ensemble)
                        if c and c != f:
                            liens.append((f, "importe", c, ""))
                elif isinstance(n, ast.Import):
                    for a in n.names:
                        c = resout_import(f, a.name, 0, None, ensemble)
                        if c and c != f:
                            liens.append((f, "importe", c, ""))
            for cible in cites(chaines_python(txt), motifs, f):
                liens.append((f, "lit", cible, ""))      # lancement réel d'un script : à décrire dans modele.LIENS
        elif p.suffix in (".tcl", ".sh", "") or p.name == "CMakeLists.txt":
            code = sans_commentaires_diese(txt)
            for ligne in code.splitlines():
                for cible in cites(ligne, motifs, f):
                    g = noeuds[cible]["genre"]
                    if "solution file add" in ligne:
                        liens.append((f, "lit" if "-exclude true" in ligne else "synthetise", cible,
                                      "testbench" if "-exclude true" in ligne else "fichier du design"))
                    else:
                        liens.append((f, "lance" if g in ("py", "tcl", "sh", "ext", "bin") else "lit", cible, ""))
    return liens


def _normalise(chemin: str) -> str:
    parts = []
    for x in chemin.split("/"):
        if x == "..":
            if parts:
                parts.pop()
        elif x not in (".", ""):
            parts.append(x)
    return "/".join(parts)


def cibles_make(noeuds: dict) -> tuple[dict, list[tuple]]:
    """Nœuds « make:<cible> » (cibles avec ## description) et leurs liens."""
    txt = (ROOT / "Makefile").read_text(errors="replace")
    cibles, recettes, courant = {}, {}, None
    for l in txt.splitlines():
        m = re.match(r"^([a-zA-Z_-]+):([^=]*?)(?:##\s*(.*))?$", l)
        if m and not l.startswith("\t"):
            courant = m.group(1)
            deps = [d for d in m.group(2).split() if re.fullmatch(r"[a-zA-Z_-]+", d)]
            if m.group(3):
                cibles[courant] = (m.group(3).strip(), deps)
            recettes[courant] = []
        elif l.startswith("\t") and courant:
            recettes[courant].append(l.strip())
        elif l.strip() and not l.startswith("\t"):
            courant = None
    nouveaux, liens = {}, []
    for c, (desc, deps) in cibles.items():
        if c == "help":
            continue
        nid = f"make:{c}"
        nouveaux[nid] = dict(id=nid, titre=f"make {c}", groupe="make", role=desc, desc="Recette :\n" +
                             "\n".join(recettes.get(c, [])[:12]), genre="make", fichier=False, motifs=[])
        for d in deps:
            if d in cibles and d != "help":
                liens.append((nid, "depend", f"make:{d}", ""))
    tous = {**noeuds, **nouveaux}
    motifs = motifs_noeuds(tous)
    for c in cibles:
        if c == "help":
            continue
        texte = "\n".join(recettes.get(c, []))
        for cible in cites(texte, motifs, f"make:{c}"):
            if cible.startswith("make:"):
                continue
            liens.append((f"make:{c}", "lance" if tous[cible]["genre"] in ("py", "tcl", "sh", "bin", "cmake", "ext") else "lit",
                          cible, ""))
    return nouveaux, liens


# ------------------------------------------------------------------ assemblage

def construit(quiet: bool) -> dict:
    fichiers = fichiers_depot()
    noeuds = {}
    for f in fichiers:
        noeuds[f] = dict(id=f, titre=Path(f).name, groupe=groupe_de(f), role=modele.ROLES.get(f, ""),
                         desc=description(f), genre=genre_de(f), fichier=True,
                         motifs=list(getattr(modele, "MOTIFS", {}).get(f, [])))
    for nid, (g, titre, role, desc, motifs) in modele.VIRTUELS.items():
        genre = nid.split(":")[0]
        noeuds[nid] = dict(id=nid, titre=titre, groupe=g, role=role, desc=desc,
                           genre={"data": "données", "dir": "dossier", "bin": "bin", "ext": "ext"}.get(genre, genre),
                           fichier=False, motifs=motifs)
    make_noeuds, liens_make = cibles_make(noeuds)
    noeuds.update(make_noeuds)

    avert = []
    redige = []
    for (s, t, c, lab) in modele.LIENS:
        if s not in noeuds or c not in noeuds:
            avert.append(f"modele.LIENS : nœud inconnu dans ({s} -{t}-> {c})")
            continue
        redige.append((s, t, c, lab))
    for f in modele.ROLES:
        if f not in noeuds:
            avert.append(f"modele.ROLES : fichier absent ou exclu : {f}")

    ignores = set(getattr(modele, "IGNORES", []))
    paires_redigees = {(s, c) for s, _, c, _ in redige}
    vus, liens = set(), [dict(source=s, type=t, cible=c, label=lab, auto=False) for (s, t, c, lab) in redige]
    meilleur = {}                       # liens automatiques : le plus fort par paire
    for (s, t, c, lab) in liens_make + liens_automatiques(noeuds, fichiers):
        if s == c or (s, c) in paires_redigees or (s, c) in ignores:
            continue
        if (s, c) not in meilleur or PRIORITE.index(t) < PRIORITE.index(meilleur[(s, c)][0]):
            meilleur[(s, c)] = (t, lab)
    for (s, c), (t, lab) in meilleur.items():
        liens.append(dict(source=s, type=t, cible=c, label=lab, auto=True))
    for (s, c) in ignores:
        if s not in noeuds or c not in noeuds:
            avert.append(f"modele.IGNORES : noeud inconnu dans ({s}, {c})")

    parcours = []
    for titre, expl, etapes in modele.PARCOURS:
        ok = []
        for nid, texte in etapes:
            if nid not in noeuds:
                avert.append(f"modele.PARCOURS « {titre} » : nœud inconnu {nid}")
            else:
                ok.append(dict(noeud=nid, texte=texte))
        parcours.append(dict(titre=titre, explication=expl, etapes=ok))

    a_documenter = sorted(n["id"] for n in noeuds.values() if n["fichier"] and not n["role"] and not n["desc"])
    for n in noeuds.values():
        n["documente"] = bool(n["role"] or n["desc"])
        n["lien"] = ("vscode://file" + urllib.parse.quote(str(ROOT / n["id"]))) if n["fichier"] else ""
        n.pop("motifs", None)

    try:
        tete = subprocess.run(["git", "log", "-1", "--format=%h %s"], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip()
    except OSError:
        tete = ""
    return dict(
        meta=dict(date=time.strftime("%Y-%m-%d %H:%M"), commit=tete, avertissements=avert,
                  a_documenter=a_documenter, nb_fichiers=len(fichiers)),
        groupes=[dict(id=g, titre=t) for g, t in modele.GROUPES],
        types=TYPES_LIENS,
        noeuds=list(noeuds.values()),
        liens=liens,
        parcours=parcours,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Génère doc/carte/carte.html")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("-o", "--output", type=Path, default=HERE / "carte.html")
    args = ap.parse_args()
    data = construit(args.quiet)
    gabarit = (HERE / "template.html").read_text()
    html = gabarit.replace("/*__DONNEES__*/null", json.dumps(data, ensure_ascii=False))
    args.output.write_text(html)
    if not args.quiet:
        m = data["meta"]
        print(f"carte : {len(data['noeuds'])} noeuds, {len(data['liens'])} liens, {len(data['parcours'])} parcours"
              f" -> {args.output}")
        for a in m["avertissements"]:
            print("  attention :", a.encode("ascii", "replace").decode())
        if m["a_documenter"]:
            print("  sans description :", ", ".join(m["a_documenter"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
