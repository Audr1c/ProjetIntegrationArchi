# Audit : passage du modèle C++ (`cpp/`) à la HLS Catapult

Date : 2026-11-24. Périmètre : `cpp/` au commit `dd12d0b` + modification locale de `cnn.cpp`.
Modèle de flot : `hls/Demo_FIR/` (sources, `demo_sim.tcl`, log Catapult 2024.2 sans erreur) et `hls/demoFir.tcl`.

## Sources

| Réf. | Document |
|---|---|
| **[UR]** | *Catapult C Synthesis User and Reference Manual* v10.4b, `doc/hls/catapult_useref.pdf` |
| **[BB]** | *HLS Bluebook* v10.4b, `doc/hls/hls_bluebook.pdf` |
| **[BAO]** | *Boîte à outils HLS Image* (S. Mancini), `doc/BoiteAOutilsHLSImage.pdf` |
| **[SUJ]** | Sujet SEI CNN, `doc/SEI_CNN.pdf` |
| **[FIR]** | Démo `hls/Demo_FIR/` (`FIR_SIMPLE.cpp`, `FIR_TYPES.h`, `FIR_TESTBENCH.cpp`, `demo_sim.tcl`, `HLS/catapult.log`) |

## Légende

| Préfixe | Catégorie |
|---|---|
| **A** | **Bloquant** : Catapult refuse le code (`go analyze` / `go compile`) ou ne trouve pas le top. |
| **B** | **Structure / mémoire** : le code passe ou passerait, mais le matériel est faux, ingérable ou non intégrable. |
| **C** | **Testbench, scripts, projet** : SCVerify, Tcl, includes, non-régression, impact sur `Exploration/`. |
| **D** | **Qualité du matériel** (après une première synthèse réussie) : surface, latence, BRAM, DSP. |

Gravité : 🔴 bloquant · 🟠 majeur · 🟡 mineur · ⚪ info.

---

## Récapitulatif

| Code | Grav. | Fichier | Problème | État |
|---|---|---|---|---|
| A-01 | 🔴 | `cnn.cpp:18` | Pragma `hls_design_top` mal écrit | ✅ fait (commit A) |
| A-02 | 🔴 | `utils.hpp:22-48` | `std::vector` dans `imageT`, `kernelT`, `biasT`, `matrix2` | ✅ fait (commit A) |
| A-03 | 🔴 | `utils.cpp:68-71, 146-149` | Tailles fixées à l'exécution + `resize()` | ✅ fait (commit A) |
| A-04 | 🔴 | `utils.cpp`, `cnn.cpp:8` | Fonctions qui **renvoient** des tableaux (`vector`/`imageT`) | ✅ fait (commit A) |
| A-05 | 🔴 | `cnn.hpp:22-34` | Interface du top : `vector` en retour, `struct` de `vector` en entrée | ✅ fait (commit A) |
| B-01 | 🟠 | `utils.cpp:74-83, 115-119` | Bornes de boucles lues à l'exécution, k=3/5 choisi à l'exécution | À faire |
| B-02 | 🟠 | `extract_coeff.*`, `main.cpp` | Coefficients lus dans un fichier texte : aucune source synthétisable | À faire |
| B-03 | 🟡 | `utils.hpp:128-133` | `max_pool(size, stride, centered)` paramétré à l'exécution | À faire |
| B-04 | 🟡 | `cnn.cpp:7-16, 52` | `flatten_hwc` recopie 180 valeurs dans un buffer | À faire |
| B-05 | 🟠 | interface du top | Tableaux d'interface sans taille déclarée (`-ARRAY_SIZE 1024` par défaut) | À faire |
| B-06 | 🟠 | `cnn.cpp` | Grandes mémoires intermédiaires (36 864 mots pour conv1) : bibliothèque RAM et budget BRAM | À faire |
| B-07 | 🟠 | `read_image.cpp` | Crop + normalisation en `double` dans le testbench : la frontière HW/SW de l'entrée n'est pas définie | À décider |
| C-01 | 🔴 | `main.cpp` | Pas de testbench SCVerify (`CCS_MAIN` / `CCS_DESIGN` / `CCS_RETURN`) | À faire |
| C-02 | 🟠 | script Tcl | Fichiers du testbench à exclure de la synthèse (`-exclude true`) | À faire |
| C-03 | 🟠 | `hls/` | Pas de script Tcl CNN, et la cible de la démo est un Artix-7 au lieu du Zynq-7000 | À faire |
| C-04 | 🟠 | `config.hpp:15`, `utils.hpp:6` | Include de la copie locale `../hls/include/ac_fixed.h` (v4.0) au lieu de celle de Catapult | À faire |
| C-05 | 🟡 | `utils.hpp:5,8`, `cnn.hpp:4,8` | `<vector>` et `using namespace std` dans les en-têtes du design | À faire |
| C-06 | 🟠 | — | Aucune vérification bit-exacte entre l'ancien et le nouveau modèle | À faire |
| C-07 | 🟠 | testbench | Simulation RTL de ~10,7 M MAC/image : impossible sur 1000 images | À faire |
| C-08 | 🟠 | `main.cpp:14-16` | `PROJECT_ROOT` vaut `".."` hors CMake : chemins faux dans le dossier de SCVerify | À faire |
| C-09 | 🟠 | `CMakeLists.txt`, `Exploration/explo/runner.py` | Nouveaux fichiers et `-DKS`, cache d'exploration invalidé | À faire |
| D-01 | 🟠 | `config.hpp` | Config actuelle = 16 bits « large » + accumulateurs auto (~40 bits) | À décider |
| D-02 | 🟡 | `utils.cpp:13-19`, `cnn.cpp` | ReLU = passe complète en plus sur chaque feature map | Après A/B |
| D-03 | 🟡 | `utils.cpp:33-37` | Test de padding (6 comparaisons) à chaque MAC, dont un test de canal inutile | Après A/B |
| D-04 | 🟠 | `cnn.cpp` | conv1 stockée en entier (36 864 mots) avant le pool : fusion conv+pool possible | Après A/B |
| D-05 | 🟡 | `utils.cpp:157` | Max-pool : lecture initiale redondante (10 lectures pour 9 valeurs) | Après A/B |
| D-06 | ⚪ | — | Latence : 10,7 M MAC/image ≈ 107 ms à 1 MAC/cycle et 100 MHz | Info |
| D-07 | 🟡 | boucles | Pas de labels de boucles : impossible de cibler `-UNROLL` / `-PIPELINE_INIT_INTERVAL` | Avec A/B |
| D-08 | 🟡 | sortie | 10 scores en sortie, alors qu'un argmax matériel (`ac_int<4>`) suffirait pour l'affichage | Optionnel |

---

## A : bloquants

### A-01 🔴 Pragma du top mal écrit — ✅ fait
- **Constat** : `#pragma hls_design_top` (tiret bas). Corrigé en `#pragma hls_design top`.
- **Règle** : « inserting the pragma `#pragma hls_design top` immediately before the top-level function declaration » [UR §1 Step 1, §hls_design]. Dans [FIR] (`FIR_SIMPLE.cpp:23`), le log affiche `Pragma 'hls_design<top>' detected (CIN-6)`.
- **Correction** : rien de plus. Garder le pragma **juste avant la définition** et ne l'utiliser qu'une fois (s'il y a plusieurs `top`, Catapult émet un warning et en choisit un).

### A-02 🔴 `std::vector` dans les structures de données
- **Constat** : `imageT`, `kernelT`, `biasT` et `matrix2` contiennent un `vector<ac_fixed<…>>` (`utils.hpp:22-48`). `m_acc` prend et renvoie des `vector` (`utils.hpp:111-115`). `relu` itère sur `value.size()` (`utils.cpp:17`).
- **Règle** : « Catapult doesn't support dynamic memory allocation » [UR §1 Step 1]. « No dynamic memory allocation is allowed… it would require dynamically creating hardware » [UR §18.1.1]. La STL « will need to be re-written » si elle fait partie du calcul [UR §6, Common Coding Issues].
- **Correction** : tableaux C de taille fixe, avec les dimensions en constantes de compilation, conformément à [BAO §2.3.2] : « une image est un tableau ».
  ```cpp
  conv1_t fm1[C1_OUT * IMG_H * IMG_W];   // [C][H][W], même rangement CHW qu'aujourd'hui
  ```

### A-03 🔴 Tailles déterminées à l'exécution + `resize()`
- **Constat** : `img_o.channels = ker.C; … img_o.value.resize(…)` (`utils.cpp:68-71`, `146-149`). Les dimensions sont des champs `int` remplis à l'exécution.
- **Règle** : le code doit être *statically determinable*, c'est-à-dire que toutes ses propriétés doivent être connues à la compilation [UR §18.1].
- **Correction** : supprimer les champs `width/height/channels/M/N/L/C` et passer les dimensions en **paramètres template** des fonctions (`template<int C_IN, int H, int W, …>`).

### A-04 🔴 Fonctions qui renvoient des tableaux par valeur
- **Constat** : `convolution_feature`, `max_pool`, `m_acc` et `flatten_hwc` construisent un objet local et le renvoient (`return img_o;`).
- **Règle** : une sortie doit être un pointeur ou une référence pour que Catapult infère un port ou une mémoire en écriture ([BB] « a reference or a pointer in order to infer an output » ; [UR §2.5]). Renvoyer un gros objet impose une copie complète (boucle de copie + mémoire temporaire).
- **Correction** : écrire dans un tableau passé en paramètre.
  ```cpp
  void conv_relu(const T_in in[], const T_k ker[], const T_b bias[], T_out out[]);
  ```

### A-05 🔴 Interface de la fonction top
- **Constat** : `vector<out_t> cnn(const imageT<…>& image, const CnnCoeffs& coef)` (`cnn.hpp:34`). Le retour est un `vector` et l'entrée une `struct` de `vector`.
- **Règle** : « All primary interfaces must be pointers or references… Primary interfaces can only be direct inputs/outputs or memories » [UR §2.5]. « An array is considered a pointer » : un tableau d'interface devient un port mémoire [UR §2.5, Determining Port Direction]. Exemple de référence : `void FIR_HARDWARE(ac_channel<d_type>&, c_type coeffs[N_TAPS], ac_channel<d_type>&)` [FIR].
- **Correction** :
  ```cpp
  #pragma hls_design top
  void cnn(const input_t image[IN_C * IMG_H * IMG_W], out_t scores[N_CLASSES]);
  ```
  Les coefficients sortent de l'interface (voir B-02). La fonction top **ne doit pas être un template** [UR §14.3].

---

## B : structure, mémoire, interface

### B-01 🟠 Bornes de boucles lues à l'exécution, k choisi à l'exécution
- **Constat** : les boucles s'arrêtent sur `ker.L`, `ker.M`, `ker.N`, `img_o.height`… (`utils.cpp:74-83`) et sur `B.M`, `B.N` (`utils.cpp:115-119`). Le choix k=3 ou 5 se fait par la ligne de commande (`main.cpp:53`).
- **Règle** : boucles à bornes finies et constantes [UR §6.1.1]. Une borne variable entraîne « loop counter hardware being larger than needed » et « one extra clock cycle to test the loop condition » [BB §4.3.4]. La HLS ne réduit les largeurs que si elle peut prouver l'équivalence [BB §4.3.4].
- **Correction** : `#define KS 5` dans `config.hpp` (surchargeable par `-DKS=3`). Toutes les bornes deviennent des paramètres template ou des macros.

### B-02 🟠 Les coefficients n'ont aucune source synthétisable
- **Constat** : `parse_tensors` lit un fichier texte (`std::map`, `std::string`, `ifstream`), puis `to_kernel`/`to_bias` remplissent des `vector`. Tout cela relève du testbench.
- **Règle** : « le maximum de paramètres sont statiques » ; « Pour initialiser une mémoire par un tableau de constantes, il faut bien spécifier à Catapult-C que la variable est allouée à une RAM ou à une ROM » [BAO p.16, p.26]. Les tableaux constants au-delà de `ROM_THRESHOLD` (64 dans `demo_sim.tcl`) deviennent des ROM.
- **Correction (recommandée)** : un script Python (`hls/gen_coeffs.py`) réutilise `python/extractCoeff.parse_tensors` et produit `cpp/coeffs_k5.hpp` et `cpp/coeffs_k3.hpp`. Les noyaux sont déjà réordonnés en `[C][L][M][N]`, comme le fait `to_kernel` :
  ```cpp
  static const ker1_t  K1[64*3*KS*KS] = { 1.2345678901234567e-02, … };  // littéraux double
  static const bias1_t B1[64]         = { … };
  ```
  Les littéraux restent en `double` et la conversion se fait à la compilation par le constructeur `ac_fixed(double)`, le même que celui de `to_kernel`. Résultat **bit-exact** avec le modèle actuel, et l'en-tête **n'a pas à être regénéré** quand un format change (l'exploration continue de marcher). [BAO §2.3.1] illustre exactement cette forme d'initialisation.
- **Alternative** (plus tard, si on veut changer les poids depuis l'ARM) : les poids deviennent des tableaux d'interface (ports mémoire, comme `coeffs[N_TAPS]` dans [FIR]).

### B-03 🟡 `max_pool` paramétré à l'exécution
- **Constat** : `max_pool(img, int size = 3, int stride = 2, bool centered = false)` (`utils.hpp:128-133`). Le mode `centered` n'est jamais utilisé : le réseau est entraîné en TF 'SAME'.
- **Correction** : fonction `max_pool_3x3s2<C, H, W>` sans paramètre d'exécution, et suppression du mode centré (il reste dans l'historique git et dans `python/`).

### B-04 🟡 `flatten_hwc` recopie dans un buffer
- **Constat** : `cnn.cpp:7-16` recopie les 180 valeurs de `pool3` dans un nouveau `vector` rangé en HWC.
- **Correction** : pas de copie. Le perceptron lit directement `pool3[(c*3 + r)*3 + k]`, avec des boucles **dans l'ordre `r`, `k`, `c`** pour que l'indice aplati `f = (r*3 + k)*20 + c` croisse comme aujourd'hui. Cela garde l'ordre d'accumulation, donc un résultat bit-exact même avec un accumulateur tronqué (`ACCFC_W > 0`).

### B-05 🟠 Tableaux d'interface sans taille déclarée
- **Constat** : `demo_sim.tcl` contient `directive set -ARRAY_SIZE 1024`, la taille par défaut d'un tableau ou pointeur d'interface dont la taille est inconnue. L'image d'entrée fait 1 728 valeurs.
- **Correction** : toujours déclarer la taille dans la signature (`input_t image[1728]`, `out_t scores[10]`), comme `coeffs[N_TAPS]` dans [FIR].

### B-06 🟠 Mémoires intermédiaires et budget BRAM
- **Constat** : les feature maps locales du top deviennent des mémoires internes. Les tableaux au-delà de `MEM_MAP_THRESHOLD` (32) sont mappés en RAM, sinon en registres. Volumes pour k=5 :

  | Donnée | Mots | Bits (config 16 b) | Bits (run `s5949`) |
  |---|---:|---:|---:|
  | Poids + biais (K1 4 800, K2 51 200, K3 16 000, FC 1 800, biais 126) | 73 926 | 1,18 Mbit | 0,76 Mbit |
  | Feature maps (in 1 728, conv1 36 864, pool1 9 216, conv2 4 608, pool2 1 152, conv3 720, pool3 180) | 54 468 | 0,87 Mbit | 0,48 Mbit |
  | **Total** | **128 394** | **2,05 Mbit** | **1,24 Mbit** |

  Zynq-7010 (Zybo Z7-10) : 60 BRAM36 = 2,1 Mbit, 80 DSP. Zynq-7020 (Z7-20) : 140 BRAM36 = 4,9 Mbit, 220 DSP. La plateforme de l'encadrant utilise aussi des BRAM pour la mémoire vidéo.
- **Correction** : ajouter la bibliothèque de RAM (`solution library add Xilinx_RAMS`, comme dans `demo_sim.tcl`). Vérifier quelle carte on a (Z7-10 ou Z7-20). Avec la config 16 bits sur une Z7-10, ça ne tient pas : voir D-01 et D-04.

### B-07 🟠 Frontière HW/SW de l'entrée non définie
- **Constat** : le crop 32→24 et la normalisation (moyenne, écart-type, `sqrt`, division) se font en `double` dans `read_image.cpp`. Sur la carte, la caméra fournit des pixels 8 bits.
- **Règle** : `sqrt` et la division flottante ne sont pas synthétisables tels quels [UR §6 : `math.h`]. [CLAUDE.md] et le sujet admettent une normalisation côté ARM.
- **Décision à prendre** : (a) l'ARM fait crop + normalisation et écrit `input_t image[1728]` en mémoire. C'est le plus simple et l'interface du top ne change pas. (b) Le matériel reçoit les pixels bruts `ac_int<8,false>` et normalise lui-même (`ac_math` pour `sqrt`/division). Recommandation : **(a)** d'abord.

---

## C : testbench, scripts, projet

### C-01 🔴 Pas de testbench SCVerify
- **Constat** : `main.cpp` appelle `cnn()` directement et définit `int main`.
- **Règle / modèle** : `FIR_TESTBENCH.cpp` inclut `mc_scverify.h`, définit `CCS_MAIN(int argc, char **argv)`, appelle `CCS_DESIGN(FIR_HARDWARE)(…)` et se termine par `CCS_RETURN(0)` [FIR]. C'est ce qui permet à SCVerify de rejouer le testbench sur le RTL [UR §15].
- **Correction** : nouveau fichier `cpp/tb_hls.cpp` (ou `hls/cnn/tb_hls.cpp`). `main.cpp` reste l'outil PC et d'exploration, compilable sans Catapult : `mc_scverify.h` n'existe que dans l'installation de Catapult.

### C-02 🟠 Fichiers à exclure de la synthèse
- **Constat** : `extract_coeff.cpp`, `read_image.cpp` et le testbench utilisent `map`, `string` et `fstream`. Dans `demoFir.tcl`, `FIR_SIMPLE_REFERENCE.cpp` est ajouté **sans** `-exclude` : ça passe seulement parce que le top ne l'appelle pas.
- **Correction** : `solution file add … -type C++ -exclude true` pour tout ce qui n'est pas le design, comme dans `demo_sim.tcl`.

### C-03 🟠 Script Tcl du CNN à écrire, cible à changer
- **Constat** : il n'existe que `demoFir.tcl` et `demo_sim.tcl`, qui ciblent un **Artix-7** (`xc7a12tcsg325-2L` / `xc7a50tcsg324-2`). La Zybo Z7 est un **Zynq-7000** (`xc7z010clg400-1` ou `xc7z020clg400-1`).
- **Correction** : `hls/cnn.tcl` sur le modèle de `demo_sim.tcl` :
  ```tcl
  solution file add ../cpp/cnn.cpp        -type C++
  solution file add ../cpp/config.hpp     -type CHEADER
  solution file add ../cpp/utils.hpp      -type CHEADER
  solution file add ../cpp/coeffs_k5.hpp  -type CHEADER
  solution file add ../cpp/tb_hls.cpp     -type C++ -exclude true
  solution file add ../cpp/read_image.cpp -type C++ -exclude true
  go analyze
  directive set -DESIGN_HIERARCHY cnn
  go compile
  # bibliothèque Zynq-7000 : la choisir dans Task Bar → Libraries, puis recopier la commande du log
  solution library add Xilinx_RAMS
  go libraries
  directive set -CLOCKS {clk {-CLOCK_PERIOD 10 …}}
  go assembly
  go architect
  go extract
  ```
  Le nom exact de la bibliothèque Zynq dans Catapult n'est pas vérifié ici : recopier celui que la GUI écrit dans le log.

### C-04 🟠 Include de la copie locale des AC types
- **Constat** : `#include "../hls/include/ac_fixed.h"` (`config.hpp:15`, `utils.hpp:6`). Cette copie est la version 4.0, alors que Catapult fournit la sienne dans `$MGC_HOME/shared/include`. Les deux utilisent la même garde `__AC_FIXED_H` : la première incluse gagne, et `mc_scverify.h` / `ac_channel.h` de Catapult tourneraient alors avec notre version.
- **Règle** : « Catapult automatically includes the source location ($MGC_HOME/shared/includes) in the include search path » [UR §AC datatypes]. [FIR] fait `#include "ac_fixed.h"` et `Demo_FIR/C/Makefile` ajoute `-I…/Mgc_home/shared/include`.
- **Correction** : `#include <ac_fixed.h>` partout, avec `-I hls/include` dans `CMakeLists.txt` (`target_include_directories`) et dans `Exploration/explo/paths.py` (`CXXFLAGS`).

### C-05 🟡 STL et `using namespace std` dans les en-têtes du design
- **Constat** : `utils.hpp` et `cnn.hpp` incluent `<vector>` et font `using namespace std;`. Ils sont inclus par le design.
- **Règle** : la STL dans le design « requires many special define statements and will result in different hardware on different platforms » [UR §6].
- **Correction** : les en-têtes du design n'incluent que `<ac_fixed.h>` et `config.hpp`. `<vector>`, `<string>` et `using namespace std` restent dans les fichiers du testbench.

### C-06 🟠 Pas de vérification bit-exacte ancien → nouveau modèle
- **Constat** : la réécriture touche toute la chaîne de calcul. Une erreur d'indice (CHW/HWC, `[C][L][M][N]`) coûterait des points sans planter.
- **Correction** : **avant** la réécriture, produire une référence avec l'ancien modèle : les 10 scores de N=200 images dans un fichier (option `--dump` dans `main.cpp`). Après, comparer **à l'identique** (`==` sur les `ac_fixed`, pas seulement la précision). Garder les mêmes ordres d'accumulation pour que ce soit possible (voir B-04 et D-02). Le testbench SCVerify relit ce même fichier.

### C-07 🟠 Durée de la simulation RTL
- **Constat** : 10,7 M MAC par image (voir D-06). En RTL sous Questa, c'est de l'ordre de la minute par image au moins.
- **Correction** : `tb_hls.cpp` prend un **petit** nombre d'images (1 à 5), choisies parmi celles de C-06. Il compare les scores RTL aux scores de référence et non aux labels.

### C-08 🟠 Chemins de données dans le dossier de SCVerify
- **Constat** : `PROJECT_ROOT` vient de CMake et vaut `".."` par défaut (`main.cpp:14-16`). SCVerify lance la simulation depuis le dossier du projet Catapult : dans [FIR], `input_signal.txt` est écrit dans `Demo_FIR/HLS/`.
- **Correction** : dans `tb_hls.cpp`, chemin absolu passé par variable d'environnement (`CNN_ROOT`) ou en argument, avec un message d'erreur explicite si le fichier est introuvable.

### C-09 🟠 Impact sur CMake et sur l'exploration
- **Constat** : `runner.py` compile une liste de fichiers codée en dur (`main.cpp`, `cnn.cpp`, objets `extract_coeff.o`, `read_image.o`) et passe k à l'exécution. Le cache est indexé par le hash de tous les `cpp/*.?pp` sauf `config.hpp`.
- **Correction** : ajouter `-DKS=<k>` dans `Runner.defines()`, ajouter les nouveaux fichiers dans `CMakeLists.txt` et `runner.py`, et supprimer `extract_coeff.o` si `main.cpp` ne lit plus les coefficients. Le cache sera invalidé, ce qui est **normal** : si C-06 est bit-exact, les anciens résultats restent valables, mais le hash ne le sait pas.

---

## D : qualité du matériel (après la première synthèse)

### D-01 🟠 Choisir la configuration de formats avant de synthétiser
- `config.hpp` contient la config **large** : tout en 16 bits, avec des accumulateurs automatiques d'environ 40 bits (produit exact + 11 bits de garde). Le run `20261119-223144_k5_t1_s5949` passe à 10,8 bits moyens (88,1 %, réf. 89,0 %), soit environ −40 % de BRAM (voir B-06).
- Le multiplieur d'un DSP48E1 fait 25×18 bits signés. Avec des poids ≤ 18 bits et des données ≤ 25 bits, chaque MAC tient dans un seul DSP.
- Vérifier sur `test_batch` (`make validate`) avant de figer la config.

### D-02 🟡 Fusionner la ReLU dans la convolution
- Aujourd'hui, `relu()` relit et réécrit toute la feature map (36 864 mots pour conv1).
- Pour rester **bit-exact** avec `AC_WRAP`, il faut quantifier **puis** faire la ReLU, comme aujourd'hui :
  ```cpp
  T_out v = acc;                 // quantification (TRN/WRAP), identique à l'actuel
  out[i] = (v < 0) ? T_out(0) : v;
  ```

### D-03 🟡 Simplifier le test de padding
- `get_valid_pixel` fait 6 comparaisons à chaque MAC, dont `chan` toujours valide, et sur des `int` 32 bits.
- Correction : tester seulement `rr` et `cc`, avec des compteurs de largeur réduite. Option : buffer d'entrée déjà bordé de zéros (`(H+K-1)×(W+K-1)`).

### D-04 🟠 Fusionner conv1 et max-pool1
- La sortie de conv1 (36 864 mots) n'est lue que par le pool. En calculant conv1 ligne par ligne et en poolant à la volée avec un buffer de 3 lignes (`ac_window` / line buffer [UR ch. 7]), la plus grosse feature map disparaît.
- À faire seulement si le budget BRAM l'exige (Z7-10).

### D-05 🟡 Lecture redondante dans le max-pool
- `max_pool` lit d'abord le pixel `(2r, 2c)`, puis les 9 pixels de la fenêtre, qui contient ce même pixel.
- Après la ReLU, toutes les valeurs sont ≥ 0 et le padding vaut 0 : initialiser `max = 0` donne **le même résultat** avec 9 lectures au lieu de 10.

### D-06 ⚪ Ordre de grandeur de la latence

| Couche | Sorties | MAC/sortie | MAC |
|---|---:|---:|---:|
| conv1 | 24·24·64 = 36 864 | 3·25 = 75 | 2 764 800 |
| conv2 | 12·12·32 = 4 608 | 64·25 = 1 600 | 7 372 800 |
| conv3 | 6·6·20 = 720 | 32·25 = 800 | 576 000 |
| FC | 10 | 180 | 1 800 |
| **Total** | | | **10 715 400** |

- À 1 MAC/cycle à 100 MHz, environ **107 ms/image (~9 img/s)**, ce qui suffit pour une démo.
- conv2 représente 69 % du calcul. C'est la première cible pour `-UNROLL` (sur `MAC_N`, par exemple ×5), à condition de découper les mémoires (`-BLOCK_SIZE` / `-INTERLEAVE`) pour avoir plusieurs lectures par cycle.

### D-07 🟡 Labels de boucles
- Les directives visent des chemins comme `/FIR_HARDWARE/core/MAC` [FIR]. Sans label, Catapult génère des noms (`for#1`…) qui changent quand le code bouge.
- Correction : nommer toutes les boucles (`CONV_CO:`, `CONV_ROW:`, `CONV_COL:`, `MAC_CI:`, `MAC_M:`, `MAC_N:`, `POOL_*`, `FC_*`).

### D-08 🟡 Argmax en matériel (optionnel)
- Pour l'affichage, seule la classe compte. Une sortie `ac_int<4,false> &classe` en plus (ou à la place) de `scores[10]` simplifie l'interface AXI.
- Garder `scores` tant que C-06 et C-07 s'en servent.

---

## Déjà conforme (rien à changer)

- **C++11** : `main.cpp`, `cnn.cpp`, `extract_coeff.cpp` et `read_image.cpp` passent `g++ -std=c++11 -fsyntax-only` (vérifié le 2026-11-24). SCVerify compile en `-std=gnu++11` (log [FIR]).
- Templates de sous-fonctions et `typedef` d'accumulateurs via `rt<…>::mult`, `constexpr`, `AC_MAX` : synthétisables. Seule la **fonction top** ne doit pas être un template [UR §14.3]. La récursion de templates est autorisée [UR §18.1.1].
- Pas de récursion, pas de pointeur de fonction, pas de `double` dans le chemin de calcul.
- `AC_TRN` / `AC_WRAP` : modes par défaut, sans logique de saturation.
- `utils.cpp` inclus en fin de `utils.hpp` : Catapult suit les `#include`. Ne **pas** l'ajouter en plus comme fichier `C++` dans le Tcl.

---

## Architecture cible (squelette)

```cpp
// ---------- config.hpp (extrait) ----------
#include <ac_fixed.h>
#ifndef KS
#define KS 5
#endif
#define IMG_H 24
#define IMG_W 24
#define C0 3      // canaux d'entrée
#define C1 64
#define C2 32
#define C3 20
#define N_CLASSES 10
#define FC_IN (3*3*C3)   // 180

// ---------- utils.hpp (extrait) ----------
template <int C_IN, int H, int W, int C_OUT, int K, int W_acc, int I_acc,
          class T_in, class T_k, class T_b, class T_out>
void conv_relu(const T_in in[C_IN*H*W], const T_k ker[C_OUT*C_IN*K*K],
               const T_b bias[C_OUT], T_out out[C_OUT*H*W]) {
    typedef /* même calcul d'acc_t qu'aujourd'hui */ acc_t;
    CONV_CO:  for (int co = 0; co < C_OUT; co++)
    CONV_ROW: for (int r = 0; r < H; r++)
    CONV_COL: for (int c = 0; c < W; c++) {
        acc_t acc = 0;
        MAC_CI: for (int ci = 0; ci < C_IN; ci++)
        MAC_M:  for (int m = 0; m < K; m++)
        MAC_N:  for (int n = 0; n < K; n++) {
            int rr = r + m - K/2, cc = c + n - K/2;
            if (rr >= 0 && rr < H && cc >= 0 && cc < W)
                acc += in[(ci*H + rr)*W + cc] * ker[((co*C_IN + ci)*K + m)*K + n];
        }
        acc += bias[co];                        // biais à la fin : même ordre qu'aujourd'hui
        T_out v = acc;
        out[(co*H + r)*W + c] = (v < 0) ? T_out(0) : v;
    }
}

template <int C, int H, int W, class T_in, class T_out>
void max_pool_3x3s2(const T_in in[C*H*W], T_out out[C*(H/2)*(W/2)]);

template <int C, int H, int W, int N, int W_acc, int I_acc,
          class T_in, class T_m, class T_b, class T_out>
void fc_hwc(const T_in in[C*H*W], const T_m mat[C*H*W*N], const T_b bias[N], T_out out[N]);
// boucles r, k, c (indice HWC croissant), lecture in[(c*H + r)*W + k]

// ---------- cnn.cpp ----------
#include "cnn.hpp"
#include KS_COEFF_HEADER        // "coeffs_k5.hpp" : static const K1[], B1[], …, FCK[], FCB[]

#pragma hls_design top
void cnn(const input_t image[C0*IMG_H*IMG_W], out_t scores[N_CLASSES]) {
    static conv1_t fm1[C1*24*24];  static pool1_t fm2[C1*12*12];
    static conv2_t fm3[C2*12*12];  static pool2_t fm4[C2*6*6];
    static conv3_t fm5[C3*6*6];    static pool3_t fm6[C3*3*3];
    conv_relu<C0, 24, 24, C1, KS, ACC1_W, ACC1_I>(image, K1, B1, fm1);
    max_pool_3x3s2<C1, 24, 24>(fm1, fm2);
    conv_relu<C1, 12, 12, C2, KS, ACC2_W, ACC2_I>(fm2, K2, B2, fm3);
    max_pool_3x3s2<C2, 12, 12>(fm3, fm4);
    conv_relu<C2, 6, 6, C3, KS, ACC3_W, ACC3_I>(fm4, K3, B3, fm5);
    max_pool_3x3s2<C3, 6, 6>(fm5, fm6);
    fc_hwc<C3, 3, 3, N_CLASSES, ACCFC_W, ACCFC_I>(fm6, FCK, FCB, scores);
}
```

---

## Plan de migration (ordre conseillé)

1. [ ] **Commit de l'état actuel** (pragma A-01 inclus), puis tag `avant-hls`.
2. [ ] **C-06** : ajouter `--dump` à `main.cpp` et produire `hls/ref/scores_k5_200.txt` avec l'**ancien** modèle.
3. [ ] **B-02** : écrire `hls/gen_coeffs.py`, générer `cpp/coeffs_k5.hpp` et `cpp/coeffs_k3.hpp`.
4. [ ] **A-02 → A-05, B-01, B-03, B-04, D-02, D-05, D-07** : réécrire `utils.*` et `cnn.*` en tableaux fixes (squelette ci-dessus).
5. [ ] **C-04, C-05** : includes `<ac_fixed.h>` + `-I hls/include`, et nettoyage des en-têtes du design.
6. [ ] **C-09** : adapter `main.cpp` (coefficients compilés, `KS`), `CMakeLists.txt` et `runner.py` (`-DKS`).
7. [ ] **Non-régression** : scores identiques sur les 200 images de l'étape 2, et précision inchangée sur 1000 images (`cpp/build/main 1000 5`).
8. [ ] **C-01, C-07, C-08** : écrire `tb_hls.cpp` (1 à 5 images, comparaison aux scores de référence).
9. [ ] **C-02, C-03, B-05, B-06** : écrire `hls/cnn.tcl`, puis `go analyze` / `go compile` sur la machine de l'école.
10. [ ] **B-07, D-01** : décider la frontière HW/SW de l'entrée et la config de formats, puis `go extract` et SCVerify.
11. [ ] **D-03, D-04, D-06, D-08** : optimisations selon les rapports de Catapult (surface, latence, BRAM).
