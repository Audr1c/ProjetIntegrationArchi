"""Génère les ROM de coefficients du CNN pour la HLS : cpp/coeffs_k3.hpp et cpp/coeffs_k5.hpp.

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

import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "python"))
from extractCoeff import infer_shape  # noqa: E402

NUMBER = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"     # même expression que python/extractCoeff.py
PER_LINE = 8

# (tenseur du fichier, nom C++, type C++, taille C++)
LAYERS = [
    ("conv1/weights",  "ker1", "ker1_t",  "K1_SIZE"),
    ("conv1/biases",   "bia1", "bias1_t", "C1"),
    ("conv2/weights",  "ker2", "ker2_t",  "K2_SIZE"),
    ("conv2/biases",   "bia2", "bias2_t", "C2"),
    ("conv3/weights",  "ker3", "ker3_t",  "K3_SIZE"),
    ("conv3/biases",   "bia3", "bias3_t", "C3"),
    ("local3/weights", "fck",  "fck_t",   "FCK_SIZE"),
    ("local3/biases",  "fcb",  "fcb_t",   "N_CLASSES"),
]


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
    out = [
        "/*",
        f" * Coefficients du CNN, noyaux {k}x{k} : ROM de la fonction top cnn().",
        f" * FICHIER GÉNÉRÉ par hls/gen_coeffs.py depuis {src} : ne pas modifier à la main.",
        " *",
        " * À inclure DANS le corps de cnn() (cpp/cnn.cpp), pas d'include guard.",
        " * CNN_ROM_BEGIN / CNN_ROM_END : définies dans cnn.cpp (ROM ac_fixed en synthèse, double sur PC).",
        " * Valeurs recopiées du fichier texte, converties en ac_fixed dans les formats de config.hpp.",
        " * Noyaux rangés [C_out][C_in][K][K], perceptron [180][10].",
        " */",
        "",
    ]
    for tname, cname, ctype, csize in LAYERS:
        t = tensors[tname]
        if t.ndim == 4:
            if t.shape[0] != k or t.shape[1] != k:
                sys.exit(f"{src} : {tname} de forme {t.shape}, noyau {k}x{k} attendu")
            t = t.transpose(3, 2, 0, 1)          # (M, N, L, C) -> (C, L, M, N)
        out += [c_array(ctype, cname, csize, list(t.reshape(-1))), ""]
    dst = os.path.join(ROOT, "cpp", f"coeffs_k{k}.hpp")
    with open(dst, "w") as f:
        f.write("\n".join(out))
    n = sum(tensors[t].size for t, *_ in LAYERS)
    print(f"{os.path.relpath(dst, ROOT)} : {n} coefficients")


if __name__ == "__main__":
    for k in (3, 5):
        generate(k)
