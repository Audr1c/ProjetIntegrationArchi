"""Mesure de la dynamique des valeurs du CNN pour choisir les ac_fixed<W, I, S>.

Usage :
    stats = AmplitudeStats()
    stats.record_coefficients(tensors)        # poids et biais (une seule fois)
    for img in images:
        cnn(img, tensors, stats=stats)        # chaque étape appelle stats.record(...)
    stats.save_report("Results/amplitude.md", config={...})

Chaque étape (« conv1/acc », « conv1/pool », ...) est accumulée sur TOUTES les
images : min et max sont exacts, et les percentiles sont calculés sur l'ensemble
des valeurs vues (et non en moyennant des percentiles par image, ce qui serait
faux). Pour garder une mémoire bornée, |x| est rangé dans un histogramme en
échelle log2 (16 cases par octave, soit ~4 % de précision sur les percentiles,
arrondis vers le haut : l'estimation est prudente).

Rappel ac_fixed<W, I, S> :
    W : nombre total de bits
    I : bits de partie entière, bit de signe compris si S = true
    S : signé ou non
    F = W - I : bits de partie fractionnaire, pas de quantification 2^-F
    plage signée   [-2^(I-1), 2^(I-1) - 2^-F]
    plage non signée [0, 2^I - 2^-F]
"""
import math
import os
from datetime import datetime

import numpy as np

# Histogramme de log2(|x|)
LOG2_MIN, LOG2_MAX = -40, 40
BINS_PER_OCTAVE = 16
N_BINS = (LOG2_MAX - LOG2_MIN) * BINS_PER_OCTAVE

# Bits significatifs voulus sur la valeur médiane (heuristique pour F)
DEFAULT_SIG_BITS = 8
# Percentile utilisé pour la variante « saturée » (AC_SAT)
SAT_PERCENTILE = 99.9

KIND_COEF = "coef"
KIND_DATA = "data"


class _Stage:
    def __init__(self, kind):
        self.kind = kind
        self.count = 0
        self.zeros = 0
        self.min = math.inf
        self.max = -math.inf
        self.sum = 0.0
        self.sum_sq = 0.0
        self.hist = np.zeros(N_BINS, dtype=np.int64)

    def add(self, a):
        a = np.asarray(a, dtype=np.float64).ravel()
        if a.size == 0:
            return
        self.count += a.size
        self.min = min(self.min, float(a.min()))
        self.max = max(self.max, float(a.max()))
        self.sum += float(a.sum())
        self.sum_sq += float(np.dot(a, a))

        mag = np.abs(a)
        nz = mag[mag > 0]
        self.zeros += a.size - nz.size
        idx = np.floor((np.log2(nz) - LOG2_MIN) * BINS_PER_OCTAVE).astype(np.int64)
        np.clip(idx, 0, N_BINS - 1, out=idx)
        self.hist += np.bincount(idx, minlength=N_BINS)

    @property
    def max_abs(self):
        return max(abs(self.min), abs(self.max))

    @property
    def mean(self):
        return self.sum / self.count

    @property
    def std(self):
        return math.sqrt(max(self.sum_sq / self.count - self.mean ** 2, 0.0))

    def abs_percentile(self, q, nonzero_only=False):
        """Percentile q (0-100) de |x|, borne haute de la case de l'histogramme."""
        total = self.count - self.zeros if nonzero_only else self.count
        if total == 0:
            return 0.0
        target = q / 100 * total
        if not nonzero_only:
            if target <= self.zeros:
                return 0.0
            target -= self.zeros
        cum = np.cumsum(self.hist)
        i = int(np.searchsorted(cum, target))
        edge = 2.0 ** (LOG2_MIN + (i + 1) / BINS_PER_OCTAVE)
        return min(edge, self.max_abs)


def magnitude_bits(bound):
    """Plus petit n tel que bound < 2^n (peut être négatif ou nul)."""
    if bound <= 0:
        return 0
    return math.floor(math.log2(bound)) + 1


def ac_fixed_type(bound, signed, frac_bits):
    """(W, I, S) pour représenter |x| <= bound avec frac_bits bits fractionnaires."""
    I = magnitude_bits(bound) + (1 if signed else 0)
    I = max(I, 1)
    W = max(I + frac_bits, 1)
    return W, I, signed


def fmt_type(W, I, S):
    return f"`ac_fixed<{W},{I},{'true' if S else 'false'}>`"


def fmt(x):
    if x == 0:
        return "0"
    return f"{x:.4g}"


class AmplitudeStats:
    """Collecte, étape par étape, la dynamique des valeurs du réseau."""

    def __init__(self, sig_bits=DEFAULT_SIG_BITS, sat_percentile=SAT_PERCENTILE):
        self.sig_bits = sig_bits
        self.sat_percentile = sat_percentile
        self.stages = {}       # ordre d'insertion = ordre du pipeline
        self.n_images = 0

    def record(self, name, array, kind=KIND_DATA):
        stage = self.stages.get(name)
        if stage is None:
            stage = self.stages[name] = _Stage(kind)
        stage.add(array)

    def record_coefficients(self, tensors):
        for name, tensor in tensors.items():
            self.record(name, tensor, kind=KIND_COEF)

    def new_image(self, n=1):
        self.n_images += n

    # ------------------------------------------------------------------
    def summary(self):
        """Liste de dict, une entrée par étape, avec les types proposés."""
        rows = []
        for name, s in self.stages.items():
            signed = s.min < 0
            med = s.abs_percentile(50, nonzero_only=True)
            frac = self.sig_bits - magnitude_bits(med)
            p_sat = s.abs_percentile(self.sat_percentile)
            rows.append({
                "name": name, "kind": s.kind, "count": s.count,
                "min": s.min, "max": s.max, "mean": s.mean, "std": s.std,
                "zeros": s.zeros / s.count,
                "p50": s.abs_percentile(50), "p99": s.abs_percentile(99),
                "p_sat": p_sat, "med_nz": med,
                "type_max": ac_fixed_type(s.max_abs, signed, frac),
                "type_sat": ac_fixed_type(p_sat, signed, frac),
            })
        return rows

    def to_markdown(self, config=None):
        rows = self.summary()
        ps = f"p{self.sat_percentile:g}"
        lines = ["# Dynamique des valeurs du CNN → choix des `ac_fixed<W,I,S>`", ""]
        lines.append(f"Généré le {datetime.now():%Y-%m-%d %H:%M}, sur **{self.n_images} images**.")
        if config:
            lines.append("")
            lines += [f"- {k} : `{v}`" for k, v in config.items()]
        lines += [
            "",
            "## Méthode",
            "",
            "- Chaque étape est cumulée sur toutes les images : min/max exacts, "
            "percentiles de |x| sur l'ensemble des valeurs (histogramme log2, "
            f"{BINS_PER_OCTAVE} cases/octave, arrondi vers le haut).",
            "- **S** = `true` si une valeur négative a été vue.",
            "- **I** (bits entiers, signe compris) : plus petit I tel que "
            "|x| < 2^(I-1) en signé, |x| < 2^I en non signé.",
            f"  - colonne *sans saturation* : I calculé sur max|x| → aucun débordement sur ce jeu de données ;",
            f"  - colonne *saturé* : I calculé sur le {ps} de |x| → {100 - self.sat_percentile:g} % "
            "des valeurs saturent, à utiliser avec `AC_SAT`.",
            f"- **F = W - I** (heuristique) : la médiane des |x| non nuls est codée sur "
            f"{self.sig_bits} bits significatifs. À valider en simulant le réseau quantifié.",
            "",
        ]

        header = (f"| Étape | N | min | max | moy ± σ | % zéros | \\|x\\| p50 | \\|x\\| p99 "
                  f"| \\|x\\| {ps} | sans saturation | saturé ({ps}) |")
        sep = "|" + "---|" * 11
        for kind, title in ((KIND_COEF, "Coefficients (constantes)"),
                            (KIND_DATA, "Données (par étape du réseau)")):
            sel = [r for r in rows if r["kind"] == kind]
            if not sel:
                continue
            lines += [f"## {title}", "", header, sep]
            for r in sel:
                lines.append(
                    f"| `{r['name']}` | {r['count']} | {fmt(r['min'])} | {fmt(r['max'])} "
                    f"| {fmt(r['mean'])} ± {fmt(r['std'])} | {100 * r['zeros']:.1f} "
                    f"| {fmt(r['p50'])} | {fmt(r['p99'])} | {fmt(r['p_sat'])} "
                    f"| {fmt_type(*r['type_max'])} | {fmt_type(*r['type_sat'])} |")
            lines.append("")

        lines += [
            "## Légende des étapes",
            "",
            "- `input` : image normalisée en entrée de conv1",
            "- `convK/acc` : somme des produits pixel × poids, avant biais (accumulateur)",
            "- `convK/acc+bias` : sortie de la convolution, avant ReLU",
            "- `convK/pool` : après ReLU + max-pool = entrée de la couche suivante (mémoire)",
            "- `fc/acc` : produit matriciel de la couche dense, avant biais",
            "- `fc/out` : scores de sortie (10 classes)",
            "",
        ]
        return "\n".join(lines)

    def save_report(self, path, config=None):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_markdown(config))
        return path
