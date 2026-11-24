# CLAUDE.md — contexte du projet (à lire en premier)

Projet d'intégration SEI-SoC (Phelma S9, module AlgoArchi, encadrant S. Mancini, en binôme).
But : porter un **CNN CIFAR-10 déjà entraîné** (inférence seule) de Python → C++ virgule fixe
(`ac_fixed`) → HLS Catapult → FPGA Zybo Z7 avec caméra et affichage HDMI.
Note < 10 sans démo sur carte ; minimum exigé : une convolution sur flux vidéo live.
Évaluation : rapport + interview 20 min à la dernière séance.

Langue du projet : **français** (commentaires, messages, docstrings, commits, docs). Garder ce style.

## État d'avancement (au 2026-11-20)

| Phase | Contenu | État |
|---|---|---|
| 1. Référence Python | `python/` : CNN boucles + version numpy vectorisée, lecture CIFAR/coefs, mesure de dynamique | ✅ fini |
| 2a. C++ virgule fixe | `cpp/` : même réseau en `ac_fixed<W,I,S>`, formats dans `cpp/config.hpp` | ✅ fini, ~89 % sur 200 img |
| 2b. Exploration des formats | `Exploration/` : recherche auto du nb de bits minimal par format | ✅ 12 runs complets (+2 anciens), **non commité** (`?? Exploration/`) |
| 2c. HLS Catapult | `hls/AUDIT_HLS.md` (A-01…D-08) ; code C++ rendu synthétisable (étapes A et B, bit-exact) | 🔄 en cours : reste C (testbench SCVerify, Tcl) et D |
| 3. FPGA Vivado / Zybo Z7 | `fpga/` vide | ⏳ pas commencé |
| Rapport | `rapport/` vide | ⏳ pas commencé |

Fichiers modifiés non commités au moment de l'écriture : `Makefile`, `cpp/*` (ajout `--order`/`--trace`,
accumulateurs `ACCx`), `requirements.txt` (ajout `rich`).

## Le réseau (identique partout)

```
image 32x32x3 → crop centre 24x24x3 → normalisation (μ, σ sur les 1728 valeurs, σ ≥ 1/√1728)
conv1 k×k 3→64  + biais → ReLU → maxpool 3x3/2 → 12x12x64
conv2 k×k 64→32 + biais → ReLU → maxpool 3x3/2 → 6x6x32
conv3 k×k 32→20 + biais → ReLU → maxpool 3x3/2 → 3x3x20
flatten (ordre HWC !) → 180 → perceptron 180x10 + biais → 10 scores (argmax, pas de softmax)
```
- k = 3 ou 5 → `data/coef/CNN_coeff_3x3.txt` / `CNN_coeff_5x5.txt`. **k=5 par défaut** (meilleur).
- Convolution « SAME » avec padding à zéro.
- Max-pool mode **TF 'SAME'** : fenêtre `[i*2, i*2+2]` (pas centrée). C'est ainsi que le réseau a été appris.
  Le mode centré fait perdre ~13 points.
- Tenseurs du fichier de coefs : `convN/weights (M,N,L,C)`, `convN/biases (C)`, `local3/weights (180,10)`,
  `local3/biases (10)` — format texte numpy (`tensor_name: ...` puis tableau entre crochets).

Précision de référence (float, `Results/PythonResults.md`, 10 000 img) :
3x3/TF_SAME/pool3 = 77.03 %, **5x5/TF_SAME/pool3 = 87.81 %**, 5x5 centré = 74.51 %, 5x5 pool5 = 71.27 %.
**Attention : ces chiffres sont sur `data_batch_1` (images d'entraînement).** Sur `test_batch` (vraie
généralisation), le float 5x5 fait **81.62 %** (`Exploration/validate.py`, 2026-11-24, `Exploration/runs/validation_k5.md`).

## Arborescence

```
python/            référence algorithmique (UNIQUEMENT des .py, vérifié par make tree-check)
  main.py          boucle d'évaluation + rapport de dynamique → Results/amplitude_*.md
  read_image.py    lecture CIFAR binaire, crop, normalize (sortie HWC float32)
  extractCoeff.py  parse_tensors(path) → {nom: np.ndarray}
  utils.py         conv/relu/max_pool/macc en boucles Python (modèle « matériel », lent)
  cnn.py           cnn() en boucles ; cnn_fast.py : même réseau vectorisé numpy (~1000x plus rapide)
  amplitude.py     AmplitudeStats : histogramme log2 de |x| par étape → propose ac_fixed<W,I,S>
cpp/               modèle C++ virgule fixe ; partie synthétisable (cnn.cpp, utils.*, coeffs_k*.hpp) + testbench PC
  config.hpp       TOUS les formats : macros X_W / X_I (#ifndef → surchargeables par -D) + typedefs (regénéré par explore.py)
  utils.hpp/.cpp   templates sur tableaux C fixes : relu, convolution_feature, m_acc_hwc (perceptron), max_pool 3x3/2
  cnn.hpp/.cpp     KS (taille noyau, -DKS=3) + dimensions ; top Catapult cnn(input_t image[1728], out_t scores[10])
  coeffs_k3/k5.hpp ROM des coefficients, GÉNÉRÉES par hls/gen_coeffs.py, incluses DANS cnn() (macros CNN_ROM_*)
  read_image.*     load_image(path, n) → RawImage (double, CHW, crop+normalize), to_image(raw, tableau)
  main.cpp         CLI : ./main [nb_images=100] [k=5] [batch=data_batch_1.bin] [--order F] [--trace] ; k doit valoir KS
  CMakeLists.txt   cible `main`, Release par défaut, définit PROJECT_ROOT
Exploration/       outil d'exploration bits/précision (Python + rich), voir plus bas
  explore.py       point d'entrée (docstring = doc complète des options)
  bits_stats.py    stats agrégées par variable sur tous les runs → runs/bits_stats/
  efficiency.py    efficacité des pas passés (Δbits pondérés / Δacc), où part la marge → runs/efficiency/
  validate.py      teste des configs (run, run:ref, id, .hpp, current, float) sur test_batch / autres
                   batches, en parallèle ; résultats image par image en cache dans runs/validation.jsonl
  pistes_prochaine_exploration.md   idées pour les prochains runs (ordre par poids, seuil progressif)
  explo/           paths, formats, runner, monitor, search, cache, sessions, dashboard, plots, cli
  runs/            résultats (cache.jsonl ~5600 évals, un dossier par run, sessions/ ; PNG non versionnés)
  build/           binaires temporaires de l'exploration (ignoré par git)
Results/           rapports Markdown (précision Python, dynamique des valeurs)
data/              CIFAR-10 binaire (ignoré par git, ~180 Mo) ; data/coef/ versionné ; SEI_data.tgz = archive source
doc/               SEI_CNN.pdf (sujet, 61 p.), BoiteAOutilsHLSImage.pdf (Catapult/Vivado/Zybo, 42 p.),
                   ac_datatypes_ref.pdf ; doc/hls/ (ignoré) : bluebook HLS, ref Catapult, scripts d'env école
hls/include/       ac_fixed.h, ac_int.h (Mentor/Siemens AC datatypes) — inclus par cpp/config.hpp
hls/AUDIT_HLS.md   audit du passage à Catapult : codes A (bloquant) B (structure) C (testbench/flot) D (QoR), plan
hls/gen_coeffs.py  data/coef/*.txt → cpp/coeffs_k3.hpp, coeffs_k5.hpp (texte des nombres recopié tel quel)
hls/Demo_FIR/      démo Catapult de l'encadrant (FIR) ; hls/demoFir.tcl : script de la démo
fpga/ rapport/ build/   vides (.gitkeep)
```

## Commandes

```bash
make                 # aide (liste des cibles)
make venv            # crée .venv + requirements.txt (numpy, matplotlib, pillow, tqdm, rich)
make run             # tree-check + python/main.py (config en dur dans main(), voir pièges)
make explore ARGS="run --runs 3"      # = .venv/bin/python Exploration/explore.py run --runs 3
make validate ARGS="<run> <run>:ref float -b test 2 [--start S -n N] [--md fichier.md]"
make efficiency [ARGS="-s 1"]         # graphes + tableaux dans runs/efficiency/
make tree-check      # vérifie l'arborescence imposée (liste blanche ROOT_OK dans le Makefile)

# Modèle C++
cmake -S cpp -B cpp/build && cmake --build cpp/build -j
cpp/build/main 1000 5                 # 1000 images, noyau 5x5 → ~89 %, ~30 ms/image en Release
cmake -S cpp -B cpp/build -DCMAKE_CXX_FLAGS="-DCONV1_W=12 -DCONV1_I=6"   # changer un format sans éditer

# Exploration (depuis la racine, avec le venv)
.venv/bin/python Exploration/explore.py list | show <run> | pareto | plot --no-show | select <run|id> [--apply]
```
Les chemins de données sont absolus (`PROJECT_ROOT` défini par CMake, `os.path.dirname(__file__)` en Python) :
on peut lancer depuis n'importe quel dossier.

## Conventions de données (source fréquente de bugs)

| | Python | C++ |
|---|---|---|
| image / feature map | `(H, W, C)` HWC | tableau `x[(c*H + r)*W + k]` **CHW** |
| noyau | `(M, N, L, C)` comme le fichier | `ker[((c*L + l)*M + m)*N + n]` (réordonné par `hls/gen_coeffs.py`) |
| matrice FC | `(180, 10)` | `fck[k*N + j]`, ligne par ligne |
| flatten avant FC | `reshape(180)` HWC | pas de copie : `m_acc_hwc` lit la carte CHW dans l'ordre **HWC** (sinon les poids FC ne collent plus) |

## Virgule fixe (`cpp/config.hpp`)

- `ac_fixed<W, I, S>` : W bits au total, I bits entiers (signe compris), F = W − I fractionnaires.
  I peut être négatif ou > W. Quantification par défaut `AC_TRN`, débordement `AC_WRAP` (aucun AC_SAT utilisé).
- 20 formats nommés : `IN`, `K1 B1 ACC1 CONV1 POOL1`, `K2 B2 ACC2 CONV2 POOL2`, `K3 B3 ACC3 CONV3 POOL3`,
  `FCK FCB ACCFC OUT`. Chacun a `<NOM>_W` et `<NOM>_I`. Les `POOLx` sont **non signés** (après ReLU), le reste signé.
- Accumulateurs `ACCx_W = 0` ⇒ format automatique sans perte (produit exact + 11 bits de garde pour les
  convs, 8 pour le FC) calculé dans `utils.cpp`. Une seule quantification par sortie de couche.
- `config.hpp` actuel = config **large 16 bits** (tout W=16) : point de départ, pas la config optimisée.
  Les configs optimisées sont dans `Exploration/runs/<run>/config.hpp` ; `explore.py select <run> --apply`
  remplace `cpp/config.hpp`.
- Dynamique mesurée en float : `Results/amplitude_5x5_pool5_tf_same_10img.md` (attention : mesurée avec pool 5x5).

## Exploration/ — comment ça marche

40 variables = 20 formats × {I, F}. Pour chaque run (graine → ordre aléatoire des variables) :
1. **Référence** : config large (I de départ dans `explo/formats.py:FORMATS`, F = `--start-F` 12 + bonus),
   évaluée sur N=1000 images, marge par image enregistrée.
2. **Ordre des images** : petites marges d'abord (+10 % d'images sûres intercalées) → les échecs se voient vite.
3. **Descente par variable** : v-1, v-2, v-4… puis dichotomie asynchrone sur le plus grand trou ;
   on garde la plus petite valeur avec précision ≥ référence − seuil (1 pt). `--parallel-vars P` descend P variables à la fois.
4. **Arrêt anticipé** (`explo/monitor.py:PairedMonitor`) : comparaison appariée image par image avec la référence,
   borne statistique (z=2) → on tue les candidats perdus d'avance.
- Chaque évaluation = compilation de `cpp/main.cpp + cpp/cnn.cpp` avec `-D<NOM>_W/_I -DKS=<k>` + objet commun
  `read_image.o`, puis `main N k batch --trace --order order.txt`.
- **Cache** `runs/cache.jsonl` indexé par sha1(code C++ hors config.hpp, k, n, batch, config) : modifier
  n'importe quel `cpp/*.?pp` (sauf config.hpp) invalide tout le cache (hash actuel `c44f86cd67` = celui des runs).
- Métrique en abscisse : bits moyens par valeur pondérés par le stockage (`mem`) ou par les lectures (`ops`).
- Sessions reprenables (Ctrl-C propre, relancer la même commande). Runs ~1 h chacun avec 2 variables en parallèle.

**Meilleur résultat (k=5, 1000 img, seuil 1 pt)** : run `20261119-223144_k5_t1_s5949`,
88.1 % (réf 89.0 %), **10.83 bits moyens/valeur** (réf 22.10). Formats finaux `<W,I>` :
input<15,4> ker1<12,3> bias1<13,3> acc1<14,5> conv1<9,5> pool1<8,4> ker2<10,1> bias2<6,3> acc2<18,8>
conv2<8,8> pool2<5,5> ker3<11,2> bias3<8,3> acc3<15,9> conv3<10,9> pool3<7,6> fck<5,-1> fcb<7,3> accfc<13,6> out<7,6>.
Les 12 runs complets du code actuel (`s5947`→`s5958`) finissent entre 10.8 et 17.7 bits : la descente gloutonne dépend beaucoup de l'ordre des variables.

## Pièges connus

- `python/main.py` a `max_pool_ksize = 5` en dur → 71 % au lieu de 87.8 %. Le réseau attend **3**. Le C++ est figé à 3x3/2 TF_SAME.
- `python/main.py` : `slow = True` lance aussi la version boucles (très lente) ; `max_count = 10` images seulement.
- `cpp/utils.cpp` n'est **pas** compilé à part : il est `#include` à la fin de `utils.hpp` (templates).
- Ajouter un `.cpp` au modèle ⇒ mettre à jour `cpp/CMakeLists.txt` **et** `Exploration/explo/runner.py` (liste de compilation codée en dur).
- `KS` est fixé à la compilation (défaut 5, dans `cnn.hpp`, pas dans `config.hpp` qui est regénéré) : `main` refuse un
  `k` différent ; build 3x3 : `cmake -DCMAKE_CXX_FLAGS=-DKS=3`.
- Coefficients modifiés dans `data/coef/` ⇒ relancer `.venv/bin/python hls/gen_coeffs.py`. Les ROM sont en
  `static const double` sur PC (converties au 1er appel) et en `static const ac_fixed` sous `__SYNTHESIS__` :
  g++ met ~40 s / 1,3 Go à compiler la version `__SYNTHESIS__`, ne pas l'utiliser hors Catapult.
- La partie synthétisable (cnn.cpp, utils.*, coeffs) : pas de `std::`, pas d'allocation, dimensions constantes.
  Toute modification doit rester **bit-exacte** (même ordre d'accumulation, quantification avant ReLU).
- Ajouter un format ⇒ `config.hpp`, `main.cpp` (print_format), `cnn.*`, **et** `Exploration/explo/formats.py:FORMATS` + `usage_counts`.
- `make tree-check` échoue si un fichier non listé dans `ROOT_OK` (Makefile) est à la racine : tout nouveau
  fichier racine doit y être ajouté. Il ignore les périphériques caractère (dotfiles fantômes du sandbox Claude).
- Claude Code crée des dossiers `.claude/.cc-writes` là où il écrit : ignorés par git (`.claude/`), sans importance.
- `.gitignore` ignore `data/*` sauf `data/coef/`, `doc/hls/`, `doc/HLS.zip`, `build/`, `bin/`, `obj/`, `*.bin`, `.claude/`, `.vscode/`.
- `Exploration/runs/` : les données texte sont versionnées (cache, history, summary, config.hpp ≈ 1 Mo compressé),
  les **PNG sont ignorés** (`Exploration/runs/**/*.png`) → regénérer avec `explore.py plot --no-show`
  (sauf `curves.png`, produit seulement pendant un run). Graphes du README copiés dans `doc/img/`.
- Appeler le venv par un chemin sans `..` (ex. `.venv/bin/python` depuis la racine), sinon warning `sys.prefix`.

## Pour la suite (phase HLS / FPGA)

- Suivre `hls/AUDIT_HLS.md` : A et B faits (tableaux fixes, top `cnn(image, scores)`, coefficients en ROM).
  Frontière HW/SW décidée : rognage + normalisation hors matériel (testbench / ARM). Config de formats : large
  (16 bits) pour l'instant, optimisation plus tard (D-01). B-06 (budget BRAM) reporté.
- Prochaine étape : C (testbench SCVerify `CCS_MAIN`/`CCS_DESIGN`, script Tcl, includes `<ac_fixed.h>`).
- Outils école : Catapult 10.5c, Questa, Precision, Vivado 2017.1 (scripts d'environnement dans `doc/hls/bash_*`,
  chemins `/softslin/...`). Cible : Zybo Z7 (Zynq), canevas de plateformes fournis par l'encadrant
  (`/tp-fmr/smancini/SEI_SoC_CNN/`). Méthodo HLS + plateformes : `doc/BoiteAOutilsHLSImage.pdf`.
- Normalisation de l'image : pas obligatoire en matériel (peut rester côté ARM).
