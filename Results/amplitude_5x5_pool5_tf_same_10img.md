# Dynamique des valeurs du CNN → choix des `ac_fixed<W,I,S>`

Généré le 2026-11-19 14:16, sur **10 images**.

- noyau : `5x5`
- max-pool : `5x5, mode tf_same`
- modèle mesuré : `cnn (boucles)`
- précision : `70.00%`

## Méthode

- Chaque étape est cumulée sur toutes les images : min/max exacts, percentiles de |x| sur l'ensemble des valeurs (histogramme log2, 16 cases/octave, arrondi vers le haut).
- **S** = `true` si une valeur négative a été vue.
- **I** (bits entiers, signe compris) : plus petit I tel que |x| < 2^(I-1) en signé, |x| < 2^I en non signé.
  - colonne *sans saturation* : I calculé sur max|x| → aucun débordement sur ce jeu de données ;
  - colonne *saturé* : I calculé sur le p99.9 de |x| → 0.1 % des valeurs saturent, à utiliser avec `AC_SAT`.
- **F = W - I** (heuristique) : la médiane des |x| non nuls est codée sur 8 bits significatifs. À valider en simulant le réseau quantifié.

## Coefficients (constantes)

| Étape | N | min | max | moy ± σ | % zéros | \|x\| p50 | \|x\| p99 | \|x\| p99.9 | sans saturation | saturé (p99.9) |
|---|---|---|---|---|---|---|---|---|---|---|
| `conv1/biases` | 64 | -3.495 | 0.3936 | -1.056 ± 0.8169 | 0.0 | 0.8781 | 3.495 | 3.495 | `ac_fixed<11,3,true>` | `ac_fixed<11,3,true>` |
| `conv1/weights` | 4800 | -2.616 | 2.469 | -0.002692 ± 0.3632 | 0.0 | 0.1928 | 1.139 | 2 | `ac_fixed<13,3,true>` | `ac_fixed<13,3,true>` |
| `conv2/biases` | 32 | -2.217 | 2.335 | -0.2529 ± 1.027 | 0.0 | 0.8781 | 2.335 | 2.335 | `ac_fixed<11,3,true>` | `ac_fixed<11,3,true>` |
| `conv2/weights` | 51200 | -0.8887 | 0.8271 | -0.008901 ± 0.1466 | 0.0 | 0.09639 | 0.4204 | 0.6209 | `ac_fixed<12,1,true>` | `ac_fixed<12,1,true>` |
| `conv3/biases` | 20 | -1.56 | 3.014 | 0.8295 ± 1.234 | 0.0 | 1.044 | 3.014 | 3.014 | `ac_fixed<10,3,true>` | `ac_fixed<10,3,true>` |
| `conv3/weights` | 16000 | -0.6306 | 1.079 | -0.01967 ± 0.1252 | 0.0 | 0.07433 | 0.3856 | 0.5694 | `ac_fixed<13,2,true>` | `ac_fixed<12,1,true>` |
| `local3/biases` | 10 | 0.5131 | 2.74 | 1.625 ± 0.6121 | 0.0 | 1.61 | 2.74 | 2.74 | `ac_fixed<9,2,false>` | `ac_fixed<9,2,false>` |
| `local3/weights` | 1800 | -0.08612 | 0.1767 | 0.003792 ± 0.03383 | 0.0 | 0.01562 | 0.1197 | 0.1693 | `ac_fixed<14,1,true>` | `ac_fixed<14,1,true>` |

## Données (par étape du réseau)

| Étape | N | min | max | moy ± σ | % zéros | \|x\| p50 | \|x\| p99 | \|x\| p99.9 | sans saturation | saturé (p99.9) |
|---|---|---|---|---|---|---|---|---|---|---|
| `input` | 17280 | -2.189 | 3.521 | -1.18e-08 ± 1 | 0.0 | 0.7384 | 2.484 | 3.221 | `ac_fixed<11,3,true>` | `ac_fixed<11,3,true>` |
| `conv1/acc` | 368640 | -13.6 | 15.03 | -0.01937 ± 1.684 | 0.0 | 0.8052 | 5.657 | 8.354 | `ac_fixed<13,5,true>` | `ac_fixed<13,5,true>` |
| `conv1/acc+bias` | 368640 | -14.2 | 14.72 | -1.076 ± 1.851 | 0.0 | 1.189 | 6.727 | 9.514 | `ac_fixed<12,5,true>` | `ac_fixed<12,5,true>` |
| `conv1/pool` | 92160 | 0 | 14.72 | 1.141 ± 1.371 | 29.6 | 0.7384 | 5.907 | 9.514 | `ac_fixed<11,4,false>` | `ac_fixed<11,4,false>` |
| `conv2/acc` | 46080 | -113.5 | 33.43 | -14.25 ± 14.22 | 0.0 | 12.34 | 58.69 | 86.67 | `ac_fixed<12,8,true>` | `ac_fixed<12,8,true>` |
| `conv2/acc+bias` | 46080 | -112.7 | 31.94 | -14.51 ± 14 | 0.0 | 12.34 | 58.69 | 86.67 | `ac_fixed<12,8,true>` | `ac_fixed<12,8,true>` |
| `conv2/pool` | 11520 | 0 | 31.94 | 2.182 ± 3.972 | 57.2 | 0 | 18.22 | 28.1 | `ac_fixed<11,5,false>` | `ac_fixed<11,5,false>` |
| `conv3/acc` | 7200 | -123 | 38.25 | -25.43 ± 19.27 | 0.0 | 22.63 | 83 | 107.6 | `ac_fixed<11,8,true>` | `ac_fixed<11,8,true>` |
| `conv3/acc+bias` | 7200 | -122.9 | 38.57 | -24.6 ± 19.31 | 0.0 | 21.67 | 83 | 107.6 | `ac_fixed<11,8,true>` | `ac_fixed<11,8,true>` |
| `conv3/pool` | 1800 | 0 | 38.57 | 1.507 ± 3.966 | 75.2 | 0 | 16.71 | 38.57 | `ac_fixed<11,6,false>` | `ac_fixed<11,6,false>` |
| `fc/acc` | 100 | -8.378 | 21.09 | 1.336 ± 5.205 | 0.0 | 2.484 | 18.22 | 21.09 | `ac_fixed<12,6,true>` | `ac_fixed<12,6,true>` |
| `fc/out` | 100 | -6.973 | 21.61 | 2.962 ± 5.105 | 0.0 | 2.709 | 19.87 | 21.61 | `ac_fixed<12,6,true>` | `ac_fixed<12,6,true>` |

## Légende des étapes

- `input` : image normalisée en entrée de conv1
- `convK/acc` : somme des produits pixel × poids, avant biais (accumulateur)
- `convK/acc+bias` : sortie de la convolution, avant ReLU
- `convK/pool` : après ReLU + max-pool = entrée de la couche suivante (mémoire)
- `fc/acc` : produit matriciel de la couche dense, avant biais
- `fc/out` : scores de sortie (10 classes)
