"""Formats ac_fixed explorés, poids d'utilisation, identifiants de configuration, export config.hpp."""

import hashlib
from datetime import datetime

from . import paths

# ============================================================
# Formats et poids
# ============================================================

# (nom, préfixe de macro, signé, typedef, I de départ, F en plus au départ, description)
#
# Point de départ "large" (la référence doit être quasiment sans perte) :
#   I de départ  >= valeur finale de la run 20261119-185419 (4 passes) + 3 bits de marge
#   F de départ  = --start-F (12) + supplément ; supplément donné aux formats qui ont peu ou pas
#                  baissé leur partie fractionnaire (ker1 : 12 -> 10, ker2 : resté à 12) et aux
#                  accumulateurs (somme de jusqu'à 64x5x5 = 1600 produits)
# Toutes les valeurs à virgule fixe du modèle C++ sont là : données, coefficients, sorties de couche
# et accumulateurs (somme des produits avant quantification de la sortie de couche).
FORMATS = [
    ("input", "IN",    True,  "input_t", 6,  0, "image normalisée"),
    ("ker1",  "K1",    True,  "ker1_t",  6,  4, "poids conv1"),
    ("bias1", "B1",    True,  "bias1_t", 6,  0, "biais conv1"),
    ("acc1",  "ACC1",  True,  None,      8,  6, "accumulateur conv1 (somme des produits + biais)"),
    ("conv1", "CONV1", True,  "conv1_t", 8,  0, "sortie conv1 + relu"),
    ("pool1", "POOL1", False, "pool1_t", 7,  0, "sortie max-pool 1"),
    ("ker2",  "K2",    True,  "ker2_t",  4,  6, "poids conv2"),
    ("bias2", "B2",    True,  "bias2_t", 6,  0, "biais conv2"),
    ("acc2",  "ACC2",  True,  None,      11, 6, "accumulateur conv2"),
    ("conv2", "CONV2", True,  "conv2_t", 11, 0, "sortie conv2 + relu"),
    ("pool2", "POOL2", False, "pool2_t", 9,  0, "sortie max-pool 2"),
    ("ker3",  "K3",    True,  "ker3_t",  5,  2, "poids conv3"),
    ("bias3", "B3",    True,  "bias3_t", 6,  0, "biais conv3"),
    ("acc3",  "ACC3",  True,  None,      11, 6, "accumulateur conv3"),
    ("conv3", "CONV3", True,  "conv3_t", 11, 0, "sortie conv3 + relu"),
    ("pool3", "POOL3", False, "pool3_t", 9,  0, "sortie max-pool 3"),
    ("fck",   "FCK",   True,  "fck_t",   2,  0, "poids perceptron"),
    ("fcb",   "FCB",   True,  "fcb_t",   6,  0, "biais perceptron"),
    ("accfc", "ACCFC", True,  None,      10, 6, "accumulateur perceptron"),
    ("out",   "OUT",   True,  "out_t",   10, 0, "scores des 10 classes"),
]
FMT = {f[0]: f for f in FORMATS}
NAMES = [f[0] for f in FORMATS]
ACCS = {n for n in NAMES if n.startswith("acc")}

I_MIN = -6      # I peut être négatif (poids < 0.25 par ex.)
F_MIN = 0
W_MIN = 2


def usage_counts(k):
    """Nombre d'utilisations de chaque type pour une image : {nom: (mem, ops)}."""
    layers = [(24, 3, 64), (12, 64, 32), (6, 32, 20)]   # (H, L entrée, C sortie)
    mem, ops = {}, {}
    mem["input"] = 24 * 24 * 3
    for i, (H, L, C) in enumerate(layers, start=1):
        mac = H * H * C * L * k * k
        n_conv = H * H * C
        n_pool = (H // 2) ** 2 * C
        mem[f"ker{i}"], ops[f"ker{i}"] = k * k * L * C, mac
        mem[f"bias{i}"], ops[f"bias{i}"] = C, n_conv
        # accumulateur : une valeur par sortie de couche, lue + écrite à chaque MAC (+ ajout du biais)
        mem[f"acc{i}"], ops[f"acc{i}"] = n_conv, mac + n_conv
        mem[f"conv{i}"], ops[f"conv{i}"] = n_conv, n_conv + 9 * n_pool   # relu + lectures du pool 3x3
        mem[f"pool{i}"] = n_pool
        ops["input" if i == 1 else f"pool{i - 1}"] = mac                 # entrée lue une fois par MAC
    ops["pool3"] = 180 * 10
    mem["fck"], ops["fck"] = 180 * 10, 180 * 10
    mem["fcb"], ops["fcb"] = 10, 10
    mem["accfc"], ops["accfc"] = 10, 180 * 10 + 10
    mem["out"], ops["out"] = 10, 10
    return {n: (mem[n], ops[n]) for n in NAMES}


def bits(config, k, metric="mem"):
    """(bits moyens pondérés, bits totaux) de la configuration."""
    idx = 0 if metric == "mem" else 1
    cnt = usage_counts(k)
    names = [n for n in NAMES if n in config]       # anciens runs : sans accumulateurs
    tot = sum(sum(config[n]) * cnt[n][idx] for n in names)
    n = sum(cnt[n][idx] for n in names)
    return tot / n, tot


def width(config, name):
    return config[name][0] + config[name][1]


def config_key(config):
    return ",".join(f"{n}={config[n][0]}.{config[n][1]}" for n in NAMES)


def start_config(start_F):
    return {n: [FMT[n][4], start_F + FMT[n][5]] for n in NAMES}


def bounds(config, name, dim):
    """Valeur minimale autorisée pour la variable (name, dim)."""
    I, F = config[name]
    if dim == "I":
        return max(I_MIN, W_MIN - F)
    return max(F_MIN, W_MIN - I)


def with_value(config, name, dim, value):
    c = {n: list(v) for n, v in config.items()}
    c[name][0 if dim == "I" else 1] = value
    return c


def code_hash():
    """Empreinte du code C++ (hors config.hpp) : invalide le cache si le code change."""
    h = hashlib.sha1(" ".join(paths.CXXFLAGS).encode())
    for p in sorted(paths.CPP.glob("*.[ch]pp")):
        # coeffs_k*_raw.hpp : ROM de synthèse, regénérées à chaque changement de formats, jamais
        # compilées par l'exploration (chemin PC) -> hors empreinte
        if p.name != "config.hpp" and not p.name.endswith("_raw.hpp"):
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:10]


def point_id(code, k, n, batch, config):
    s = f"{code}|k{k}|n{n}|{batch}|{config_key(config)}"
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def pack(bits_list):
    """Liste de 0/1 -> chaîne hexadécimale compacte (stockage des succès image par image)."""
    s = "".join("1" if b else "0" for b in bits_list)
    s += "0" * (-len(s) % 4)
    return "".join(f"{int(s[i:i + 4], 2):x}" for i in range(0, len(s), 4))


def unpack(hexstr, n):
    s = "".join(f"{int(c, 16):04b}" for c in hexstr)
    return [int(c) for c in s[:n]]



# ============================================================
# Fichier config.hpp
# ============================================================

def make_config_hpp(config, origin):
    out = ["#ifndef CONFIG_HPP", "#define CONFIG_HPP", "",
           "/*",
           " * Formats virgule fixe du CNN : ac_fixed<W, I, S>",
           " *     W : nombre total de bits",
           " *     I : bits de partie entière (signe compris si signé)",
           " *",
           f" * Généré par Exploration/explore.py le {datetime.now():%Y-%m-%d %H:%M}",
           f" * {origin}",
           " *",
           " * Toutes les valeurs se modifient ici, ou à la compilation sans toucher au code :",
           ' *     cmake -DCMAKE_CXX_FLAGS="-DCONV1_W=12 -DCONV1_I=6" ..',
           " */", "", "#include <ac_fixed.h>", ""]
    for n in [n for n in NAMES if n in config]:
        _, macro, _, _, _, _, desc = FMT[n]
        out.append(f"// {desc}")
        for suffix, val in (("W", width(config, n)), ("I", config[n][0])):
            out += [f"#ifndef {macro}_{suffix}", f"#define {macro}_{suffix} {val}", "#endif"]
        out.append("")
    out += ["", "// ============================================================",
            "// Types utilisés par le reste du code",
            "// ============================================================"]
    for n in NAMES:
        _, macro, signed, typ, _, _, _ = FMT[n]
        if typ is None:         # accumulateurs : type défini dans utils.cpp à partir de ACCx_W/I
            continue
        out.append(f"typedef ac_fixed<{macro}_W, {macro}_I, {'true' if signed else 'false'}> {typ};")
    out += ["", "#endif // CONFIG_HPP", ""]
    return "\n".join(out)
