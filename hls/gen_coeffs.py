"""Génère les ROM de coefficients du CNN pour la HLS : cpp/coeffs_k3.hpp et cpp/coeffs_k5.hpp
(nombres du fichier, indépendants des formats), et cpp/coeffs_k3_raw.hpp, coeffs_k5_raw.hpp
(entiers déjà quantifiés dans les formats de cpp/config.hpp : utilisés en synthèse).

À RELANCER (make coeffs) après tout changement des formats K*, B*, FCK, FCB de config.hpp
(ex. explore.py select --apply) : sinon la synthèse s'arrête sur un #error explicite.

Encodage brut : r = floor(x * 2^F) replié sur W bits signés (F = W - I), c.-à-d. exactement
ac_fixed<W, I, true, AC_TRN, AC_WRAP>(x) : x * 2^F est exact en double, floor = troncature vers -inf,
le modulo 2^W = débordement AC_WRAP. Vérifié par make nonreg (cible main_raw) et par SCVerify.
Pourquoi : 74 000 objets ac_fixed initialisés dans le code font durer go analyze ~17 min ; un tableau
d'entiers natifs (RomWord, voir cpp/utils.hpp) se compile ~20x plus vite (mesure g++).

Usage (depuis la racine du dépôt) :
    .venv/bin/python hls/gen_coeffs.py

Chaque en-tête déclare des tableaux `static const` à inclure DANS le corps de cnn() (cpp/cnn.cpp) :
Catapult les implémente en ROM, et le manuel déconseille les variables globales (§6.1.2).
Les tableaux sont encadrés par les macros CNN_ROM_BEGIN / CNN_ROM_END définies dans cnn.cpp :
    synthèse (__SYNTHESIS__) : static const <type ac_fixed> nom[taille] = { ... };  -> ROM
    PC                       : static const double nom_d[taille] = { ... }; converti une fois au
                               premier appel (même conversion ; un tableau ac_fixed initialisé
                               statiquement coûte ~40 s et 1,3 Go de compilation à g++).

Les nombres sont recopiés tels qu'ils sont écrits dans data/coef/CNN_coeff_KxK.txt (pas de passage
par float32 comme python/extractCoeff.py) : le compilateur les lit en double exactement comme le
faisait strtod, puis la conversion double -> ac_fixed se fait dans les formats de config.hpp. Résultat bit-exact avec l'ancienne lecture du fichier, et pas besoin de regénérer quand
un format change.

Rangement (identique à l'ancien to_kernel de cpp/extract_coeff.hpp) :
    noyaux    : fichier (M, N, L, C)  ->  [C][L][M][N]
    perceptron: fichier (180, 10)     ->  ligne par ligne, value[k * 10 + j]
"""

import math
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))
from extractCoeff import infer_shape  # noqa: E402

NUMBER = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"     # même expression que python/extractCoeff.py
PER_LINE = 8

# (tenseur du fichier, nom C++, type C++, taille C++, préfixe des macros de format dans config.hpp)
LAYERS = [
    ("conv1/weights",  "ker1", "ker1_t",  "K1_SIZE",   "K1"),
    ("conv1/biases",   "bia1", "bias1_t", "C1",        "B1"),
    ("conv2/weights",  "ker2", "ker2_t",  "K2_SIZE",   "K2"),
    ("conv2/biases",   "bia2", "bias2_t", "C2",        "B2"),
    ("conv3/weights",  "ker3", "ker3_t",  "K3_SIZE",   "K3"),
    ("conv3/biases",   "bia3", "bias3_t", "C3",        "B3"),
    ("local3/weights", "fck",  "fck_t",   "FCK_SIZE",  "FCK"),
    ("local3/biases",  "fcb",  "fcb_t",   "N_CLASSES", "FCB"),
]


def read_formats(path):
    """{'K1': (W, I), ...} lus dans les #define de config.hpp (première définition)."""
    macros = {}
    with open(path) as f:
        for m in re.finditer(r"^\s*#define\s+(\w+)\s+(-?\d+)\s*$", f.read(), flags=re.MULTILINE):
            macros.setdefault(m.group(1), int(m.group(2)))
    return {p: (macros[p + "_W"], macros[p + "_I"]) for *_, p in LAYERS}


def raw_value(text, w, i):
    """Motif de ac_fixed<w, i, true, AC_TRN, AC_WRAP>(double(text)), en entier signé."""
    r = math.floor(math.ldexp(float(text), w - i))     # exact : multiplication par une puissance de 2
    r = (r + (1 << (w - 1))) % (1 << w) - (1 << (w - 1))
    return r


def parse_text_tensors(path):
    """{nom: tableau numpy de chaînes} : les nombres restent sous forme de texte."""
    with open(path) as f:
        content = f.read()
    tensors = {}
    for block in re.split(r"^tensor_name:\s*", content, flags=re.MULTILINE)[1:]:
        name, _, body = block.partition("\n")
        body = body.strip()
        ndim = len(re.match(r"\[+", body).group(0))
        values = np.array(re.findall(NUMBER, body), dtype=object)
        tensors[name.strip()] = values.reshape(infer_shape(body, ndim))
    return tensors


def c_array(ctype, name, size, values):
    # CNN_ROM_BEGIN / CNN_ROM_END sont définies dans cpp/cnn.cpp (ROM ac_fixed en synthèse,
    # tableau double converti au premier appel sur PC)
    lines = [f"CNN_ROM_BEGIN({ctype}, {name}, {size})   // {len(values)} valeurs"]
    for i in range(0, len(values), PER_LINE):
        lines.append("    " + ", ".join(values[i:i + PER_LINE]) + ",")
    lines.append(f"CNN_ROM_END({ctype}, {name}, {size})")
    return "\n".join(lines)


def generate(k):
    src = f"data/coef/CNN_coeff_{k}x{k}.txt"
    tensors = parse_text_tensors(os.path.join(ROOT, src))
    flat = {}
    out = [
        "/*",
        f" * Coefficients du CNN, noyaux {k}x{k} : ROM de la fonction top cnn().",
        f" * FICHIER GÉNÉRÉ par hls/gen_coeffs.py depuis {src} : ne pas modifier à la main.",
        " *",
        " * À inclure DANS le corps de cnn() (cpp/cnn.cpp), pas d'include guard.",
        " * CNN_ROM_BEGIN / CNN_ROM_END : définies dans cnn.cpp (ROM ac_fixed en synthèse, double sur PC).",
        " * Valeurs recopiées du fichier texte, converties en ac_fixed dans les formats de config.hpp.",
        " * Noyaux rangés [C_out][C_in][K][K], perceptron [180][10].",
        " *",
        " * #ifdef CNN_ROM_BEGIN : compilé seul (Catapult compile chaque fichier du projet séparément),",
        " * l'en-tête est vide et valide.",
        " */",
        "",
        "#ifdef CNN_ROM_BEGIN",
        "",
    ]
    for tname, cname, ctype, csize, _ in LAYERS:
        t = tensors[tname]
        if t.ndim == 4:
            if t.shape[0] != k or t.shape[1] != k:
                sys.exit(f"{src} : {tname} de forme {t.shape}, noyau {k}x{k} attendu")
            t = t.transpose(3, 2, 0, 1)          # (M, N, L, C) -> (C, L, M, N)
        out += [c_array(ctype, cname, csize, list(t.reshape(-1))), ""]
        flat[cname] = list(t.reshape(-1))
    out += ["#endif // CNN_ROM_BEGIN", ""]
    dst = os.path.join(ROOT, "cpp", f"coeffs_k{k}.hpp")
    with open(dst, "w") as f:
        f.write("\n".join(out))
    n = sum(tensors[t].size for t, *_ in LAYERS)
    print(f"{os.path.relpath(dst, ROOT)} : {n} coefficients")
    generate_raw(k, src, flat)


def generate_raw(k, src, flat):
    formats = read_formats(os.path.join(ROOT, "cpp", "config.hpp"))
    fmt_txt = " ".join(f"{p}<{w},{i}>" for p, (w, i) in formats.items())
    cond = " || ".join(f"{p}_W != {w} || {p}_I != {i}" for p, (w, i) in formats.items())
    name = f"coeffs_k{k}_raw.hpp"
    out = [
        "/*",
        f" * Coefficients du CNN, noyaux {k}x{k}, DÉJÀ QUANTIFIÉS : ROM de cnn() en synthèse (CNN_ROM_RAW).",
        f" * FICHIER GÉNÉRÉ par hls/gen_coeffs.py depuis {src} et cpp/config.hpp : ne pas modifier à la main.",
        f" * Formats <W,I> : {fmt_txt}",
        " * Chaque entier = motif binaire de ac_fixed<W, I, true>(x) (AC_TRN, AC_WRAP), lu par rom_value().",
        " * Même rangement que coeffs_k*.hpp. À inclure DANS le corps de cnn() (cpp/cnn.cpp).",
        " */",
        "",
        "#ifdef CNN_ROM_RAW",
        "",
        f"#if {cond}",
        f'#error "{name} genere pour d autres formats que config.hpp : relancer make coeffs"',
        "#endif",
        "",
    ]
    for _, cname, ctype, csize, prefix in LAYERS:
        w, i = formats[prefix]
        vals = [raw_value(v, w, i) for v in flat[cname]]
        out.append(f"static const RomWord<{ctype}> {cname}[{csize}] = {{   // {len(vals)} valeurs, ac_fixed<{w},{i}>")
        for j in range(0, len(vals), 16):
            out.append("    " + " ".join(f"{{{v}}}," for v in vals[j:j + 16]))
        out += ["};", ""]
    out += ["#endif // CNN_ROM_RAW", ""]
    dst = os.path.join(ROOT, "cpp", name)
    with open(dst, "w") as f:
        f.write("\n".join(out))
    print(f"{os.path.relpath(dst, ROOT)} : formats {fmt_txt}")


if __name__ == "__main__":
    for k in (3, 5):
        generate(k)
