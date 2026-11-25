"""
Partie RÉDIGÉE À LA MAIN de la carte du projet (doc/carte/carte.html, générée par gen_carte.py).

Le générateur trouve tout seul : les fichiers, les #include, les imports Python, les cibles make
(avec leur description « ## »), les scripts lancés par make / Tcl / shell, et la description de
chaque fichier (docstring ou commentaire d'en-tête). Ici, on ajoute ce qu'il ne peut pas deviner :

    ROLES       rôle d'un fichier en une ligne (affiché sous son nom)
    VIRTUELS    nœuds qui ne sont pas des fichiers du dépôt : outils, dossiers générés, binaires
    LIENS       qui ÉCRIT / LIT / LANCE quoi (surtout « écrit » : ce que l'analyse ne voit pas)
    PARCOURS    procédures pas à pas, surlignées dans la carte

Après avoir ajouté ou changé un script : compléter ROLES / LIENS ici, puis `make carte`.
Les fichiers sans description apparaissent en pointillés et dans « À documenter ».
Identifiants : chemin relatif à la racine pour un fichier, « préfixe:nom » pour un nœud virtuel.
"""

# Colonnes de la carte, de gauche à droite : (id, titre)
GROUPES = [
    ("make",    "Commandes make"),
    ("python",  "Python : référence"),
    ("explo",   "Exploration des formats"),
    ("cpp",     "Modèle C++ virgule fixe"),
    ("hls",     "HLS : Catapult, SCVerify"),
    ("outils",  "Outils externes"),
    ("donnees", "Données, résultats, docs"),
]

# Rôle en une ligne (le détail vient de la docstring / du commentaire d'en-tête du fichier)
ROLES = {
    "python/main.py":          "Évalue le CNN Python sur N images, mesure la dynamique",
    "python/cnn.py":           "CNN en boucles Python : modèle « matériel », lent",
    "python/cnn_fast.py":      "Même CNN vectorisé numpy (~1000x plus rapide)",
    "python/utils.py":         "conv, relu, max-pool, MAC en boucles",
    "python/read_image.py":    "Lecture CIFAR binaire, rognage, normalisation",
    "python/extractCoeff.py":  "Lit les coefficients texte (data/coef)",
    "python/amplitude.py":     "Histogramme log2 des valeurs → propose ac_fixed",

    "cpp/config.hpp":          "TOUS les formats ac_fixed<W,I> (surchargeables par -D)",
    "cpp/cnn.hpp":             "Dimensions du réseau, KS, prototype du top cnn()",
    "cpp/cnn.cpp":             "Top synthétisable cnn() : 3 conv + pools + perceptron, ROM",
    "cpp/utils.hpp":           "Briques templates : conv, relu, pool, perceptron, RomWord",
    "cpp/utils.cpp":           "Corps des templates (inclus par utils.hpp)",
    "cpp/main.cpp":            "Programme PC : précision sur N images, --trace, --dump",
    "cpp/read_image.cpp":      "Lecture CIFAR + rognage + normalisation (double)",
    "cpp/read_image.hpp":      "Interface de read_image.cpp",
    "cpp/tb_common.hpp":       "Signature des formats, lecture/écriture des scores de réf.",
    "cpp/coeffs_k5.hpp":       "ROM 5x5 en double (PC) — GÉNÉRÉ",
    "cpp/coeffs_k3.hpp":       "ROM 3x3 en double (PC) — GÉNÉRÉ",
    "cpp/coeffs_k5_raw.hpp":   "ROM 5x5 entières quantifiées (synthèse) — GÉNÉRÉ",
    "cpp/coeffs_k3_raw.hpp":   "ROM 3x3 entières quantifiées (synthèse) — GÉNÉRÉ",
    "cpp/CMakeLists.txt":      "Construit main, main_raw, tb_hls",

    "hls/cnn.tcl":             "Script Catapult complet : analyse → RTL → SCVerify → rapports",
    "hls/cnn_report.tcl":      "Procédures cnn_report, cnn_summary, cnn_sim_cmd, cnn_sim_env",
    "hls/catapult_report.py":  "Lit rtl.rpt / cycle.rpt / sim.log → résumé Markdown, JSON",
    "hls/sim_rtl.sh":          "Simulation RTL Questa hors Catapult, en tâche de fond",
    "hls/sim_progress.tcl":    "Compteur de cycles dans vsim : %, image, temps restant",
    "hls/tb_hls.cpp":          "Testbench SCVerify : N images, compare aux scores de réf.",
    "hls/gen_coeffs.py":       "data/coef → ROM C++ (double et entières quantifiées)",
    "hls/stub/mc_scverify.h":  "Faux mc_scverify.h pour compiler tb_hls sur PC",
    "hls/bash_mentor_24":      "Environnement école : Catapult, Questa, Precision, licences",
    "hls/demoFir.tcl":         "Script de la démo FIR de l'encadrant",
    "hls/AUDIT_HLS.md":        "Audit du passage à Catapult : A, B, C, D + résultats",
    "hls/ref/scores_k5.txt":   "Scores exacts de 200 images (5x5) : référence bit-exacte",
    "hls/ref/scores_k3.txt":   "Scores exacts de 200 images (3x3)",
    "hls/ref/images_200.bin":  "200 premières images de data_batch_1 (versionnées)",

    "Exploration/explore.py":  "Point d'entrée : run, list, show, pareto, plot, select",
    "Exploration/validate.py": "Teste des configs sur test_batch / autres batches",
    "Exploration/bits_stats.py": "Statistiques des bits par variable, tous runs",
    "Exploration/efficiency.py": "Efficacité des pas de descente des runs",
    "Exploration/explo/cli.py":      "Sous-commandes de explore.py",
    "Exploration/explo/search.py":   "Descente variable par variable (exponentielle + dichotomie)",
    "Exploration/explo/runner.py":   "Compile une config (-D) et lance cpp/main --trace",
    "Exploration/explo/monitor.py":  "Arrêt anticipé : comparaison appariée à la référence",
    "Exploration/explo/cache.py":    "Cache des évaluations (cache.jsonl) et lecture des runs",
    "Exploration/explo/formats.py":  "Les 20 formats, poids, hash du code, export config.hpp",
    "Exploration/explo/paths.py":    "Chemins et options du compilateur",
    "Exploration/explo/plots.py":    "Graphes matplotlib (progression, Pareto, formats)",
    "Exploration/explo/dashboard.py": "Tableau de bord rich en direct",
    "Exploration/explo/sessions.py": "Sessions reprenables après Ctrl-C",
    "Exploration/pistes_prochaine_exploration.md": "Idées pour les prochains runs",

    "CLAUDE.md":        "Contexte complet du projet (à lire en premier)",
    "README.md":        "Présentation du projet",
    "AGENTS.md":        "Consignes pour les agents IA",
    "requirements.txt": "Dépendances Python du venv",
    "doc/carte/gen_carte.py": "Génère cette carte (make carte, et à chaque commit)",
    "doc/carte/modele.py":    "Partie rédigée de cette carte : rôles, liens, parcours",
}

# Nœuds qui ne sont pas des fichiers versionnés.
#   id : (groupe, titre, rôle, description, [motifs reconnus dans le code -> lien automatique])
VIRTUELS = {
    "data:cifar":    ("donnees", "data/cifar-10-batches-bin/", "CIFAR-10 binaire (non versionné, ~180 Mo)",
                      "6 fichiers de 10 000 images 32x32x3 : data_batch_1..5 (entraînement) et test_batch. "
                      "Les précisions « de référence » sont mesurées sur data_batch_1.",
                      [r"cifar-10-batches-bin", r"data_batch_1\.bin", r"test_batch"]),
    "data:coef":     ("donnees", "data/coef/*.txt", "Coefficients appris du CNN (3x3 et 5x5)",
                      "Format texte numpy : convN/weights (M,N,L,C), convN/biases, local3/weights (180,10), local3/biases.",
                      [r"data/coef", r"CNN_coeff_", r"COEF_DIR"]),
    "dir:results":   ("donnees", "Results/", "Rapports Markdown : précision Python, dynamique",
                      "PythonResults.md (précisions float) et amplitude_*.md (dynamique des valeurs par étape).",
                      [r"Results/"]),
    "dir:runs":      ("donnees", "Exploration/runs/", "Résultats des explorations (cache, runs, graphes)",
                      "cache.jsonl (~5600 évaluations), un dossier par run (history, summary, config.hpp), "
                      "sessions/, validation.jsonl, bits_stats/, efficiency/. PNG non versionnés.",
                      [r"runs/"]),
    "dir:hlswork":   ("donnees", "hls/work/ (projet Catapult)", "Projet Catapult : RTL, rapports, SCVerify (non versionné)",
                      "Catapult_N/cnn.vK/ : rtl.vhdl, rtl.rpt, cycle.rpt, messages.txt, scverify/ (Makefiles, sim.log) ; "
                      "catapult.log = transcript complet. Créé en lançant cnn.tcl depuis hls/work/.",
                      [r"hls/work", r"rtl\.rpt", r"cycle\.rpt"]),
    "dir:rapports":  ("donnees", "hls/rapports/", "Rapports Catapult sauvegardés (versionnés) + resume.md",
                      "Un dossier <solution>_<date>/ par sauvegarde : rtl.rpt, cycle.rpt, messages.txt, directives.tcl, "
                      "sim.log, catapult.log et resume.md (tableau lisible).",
                      [r"hls/rapports", r"rapports"]),
    "dir:build":     ("donnees", "build/", "Sorties temporaires (scores de nonreg…)",
                      "build/scores_k5.txt et build/scores_k5_raw.txt produits par make nonreg.", [r"build/scores"]),
    "dir:demofir":   ("hls", "hls/Demo_FIR/", "Démo FIR de l'encadrant (modèle de flot)",
                      "Sources, scripts de directives, projet Catapult de référence (rapports v1..v8).", [r"Demo_FIR"]),
    "dir:acinclude": ("cpp", "hls/include/ac_fixed.h", "AC datatypes (copie PC ; Catapult a la sienne)",
                      "ac_fixed.h et ac_int.h de Mentor/Siemens, inclus via -I hors Catapult.", [r"<ac_fixed\.h>", r"ac_fixed\.h"]),

    "bin:main":      ("cpp", "cpp/build/main", "Binaire PC : précision, --trace, --dump",
                      "Compilé par CMake depuis main.cpp + cnn.cpp + read_image.cpp (ROM en double).",
                      [r"cpp/build/main(?!_)"]),
    "bin:main_raw":  ("cpp", "cpp/build/main_raw", "Même binaire avec les ROM de synthèse",
                      "Compilé avec -DCNN_ROM_RAW : vérifie que coeffs_k*_raw.hpp donne les mêmes scores.",
                      [r"main_raw"]),
    "bin:tb_hls":    ("cpp", "cpp/build/tb_hls", "Testbench HLS compilé sur PC (sans Catapult)",
                      "hls/tb_hls.cpp + hls/stub/mc_scverify.h.", [r"cpp/build/tb_hls"]),

    "ext:gpp":       ("outils", "g++ / CMake", "Compilation du modèle C++", "Utilisé par CMake (make nonreg, tb-hls) et par l'exploration (runner.py).", []),
    "ext:catapult":  ("outils", "Catapult 2024.2 (école)", "Synthèse HLS : C++ → RTL VHDL",
                      "go analyze → compile → libraries → assembly → architect → allocate → extract. "
                      "Bibliothèques mgc_Xilinx-ZYNQ-1_beh, Xilinx_RAMS, Xilinx_ROMS.", []),
    "ext:questa":    ("outils", "Questa / vsim (école)", "Simulation RTL, comparée au C++ par SCVerify",
                      "Lancé par les Makefiles SCVerify (scverify/Verify_rtl_vhdl_msim.mk).", [r"\bvsim\b", r"msim"]),
    "ext:precision": ("outils", "Precision (école)", "Synthèse FPGA du RTL (rtl.vhdl.psr) — pas encore utilisé",
                      "Donnerait l'occupation réelle (LUT, DSP, BRAM).", []),
    "ext:vivado":    ("outils", "Vivado 2017.1 (à venir)", "Intégration Zynq : bitstream, caméra, HDMI", "Phase 3 : dossier fpga/ vide.", []),
    "ext:zybo":      ("outils", "Zybo Z7-20 (à venir)", "XC7Z020-1CLG400C : 280 RAMB18, 220 DSP",
                      "Carte cible : caméra, HDMI, ARM Cortex-A9.", []),
}

# Motifs supplémentaires qui désignent un fichier dans le code (en plus de son chemin et de son nom)
MOTIFS = {
    "cpp/CMakeLists.txt": [r"cmake -S cpp", r"cmake --build cpp"],
}

# Faux positifs de l'analyse automatique (fichier cité dans un message, pas vraiment utilisé) : (source, cible)
IGNORES = [
    ("hls/tb_hls.cpp", "hls/cnn.tcl"),             # message d'erreur « définir CNN_ROOT … dans hls/cnn.tcl »
    ("hls/gen_coeffs.py", "cpp/cnn.cpp"),          # texte de l'en-tête des fichiers générés
    ("make:tree", "data:cifar"),                   # tree exclut ce dossier
    ("Exploration/explo/search.py", "cpp/config.hpp"),   # écrit un config.hpp dans runs/, pas celui de cpp/
]

# Liens rédigés : (source, type, cible, précision affichée sur le lien)
# Types : lance, inclut, importe, lit, ecrit, depend, synthetise, pilote
LIENS = [
    # Python
    ("python/main.py", "lit", "data:cifar", ""),
    ("python/main.py", "lit", "data:coef", ""),
    ("python/main.py", "ecrit", "dir:results", "amplitude_*.md"),
    ("python/extractCoeff.py", "lit", "data:coef", ""),
    ("python/read_image.py", "lit", "data:cifar", ""),

    # Génération des ROM
    ("hls/gen_coeffs.py", "lit", "data:coef", "nombres en texte"),
    ("hls/gen_coeffs.py", "lit", "cpp/config.hpp", "formats K*, B*, FCK, FCB"),
    ("hls/gen_coeffs.py", "ecrit", "cpp/coeffs_k5.hpp", ""),
    ("hls/gen_coeffs.py", "ecrit", "cpp/coeffs_k3.hpp", ""),
    ("hls/gen_coeffs.py", "ecrit", "cpp/coeffs_k5_raw.hpp", "entiers quantifiés"),
    ("hls/gen_coeffs.py", "ecrit", "cpp/coeffs_k3_raw.hpp", "entiers quantifiés"),

    # Modèle C++
    ("cpp/CMakeLists.txt", "lance", "ext:gpp", ""),
    ("ext:gpp", "ecrit", "bin:main", ""),
    ("ext:gpp", "ecrit", "bin:main_raw", "-DCNN_ROM_RAW"),
    ("ext:gpp", "ecrit", "bin:tb_hls", ""),
    ("bin:main", "lit", "data:cifar", ""),
    ("bin:main", "ecrit", "dir:build", "--dump"),
    ("bin:main", "ecrit", "hls/ref/scores_k5.txt", "--dump (nouvelle réf.)"),
    ("bin:main_raw", "ecrit", "dir:build", "--dump"),
    ("bin:tb_hls", "lit", "hls/ref/images_200.bin", ""),
    ("bin:tb_hls", "lit", "hls/ref/scores_k5.txt", "comparaison exacte"),
    ("hls/tb_hls.cpp", "lit", "hls/ref/images_200.bin", ""),
    ("hls/tb_hls.cpp", "lit", "hls/ref/scores_k5.txt", "comparaison exacte"),

    # Exploration
    ("Exploration/explo/runner.py", "lance", "ext:gpp", "-D<NOM>_W/_I -DKS"),
    ("Exploration/explo/runner.py", "lance", "bin:main", "main N k batch --trace --order"),
    ("Exploration/explo/runner.py", "lit", "cpp/main.cpp", "compile"),
    ("Exploration/explo/runner.py", "lit", "cpp/cnn.cpp", "compile"),
    ("Exploration/explo/cache.py", "ecrit", "dir:runs", "cache.jsonl"),
    ("Exploration/explo/search.py", "ecrit", "dir:runs", "history, summary, config.hpp"),
    ("Exploration/explo/plots.py", "ecrit", "dir:runs", "PNG"),
    ("Exploration/explo/cli.py", "ecrit", "cpp/config.hpp", "select --apply"),
    ("Exploration/explo/formats.py", "lit", "cpp/config.hpp", "hash du code (hors config)"),
    ("Exploration/validate.py", "ecrit", "dir:runs", "validation.jsonl"),
    ("Exploration/validate.py", "lit", "data:cifar", "test_batch…"),
    ("Exploration/bits_stats.py", "ecrit", "dir:runs", "bits_stats/"),
    ("Exploration/efficiency.py", "ecrit", "dir:runs", "efficiency/"),

    # HLS
    ("hls/cnn.tcl", "lance", "ext:catapult", "catapult -shell -file ../cnn.tcl"),
    ("ext:catapult", "synthetise", "cpp/cnn.cpp", "top cnn()"),
    ("ext:catapult", "ecrit", "dir:hlswork", "RTL, rapports, scverify/"),
    ("ext:catapult", "lance", "ext:questa", "SCVerify"),
    ("ext:questa", "lance", "hls/tb_hls.cpp", "testbench SystemC"),
    ("ext:questa", "ecrit", "dir:hlswork", "sim.log"),
    ("hls/cnn_report.tcl", "lance", "hls/catapult_report.py", "cnn_report"),
    ("hls/catapult_report.py", "lit", "dir:hlswork", "rtl.rpt, cycle.rpt, sim.log"),
    ("hls/catapult_report.py", "ecrit", "dir:rapports", "--save + resume.md"),
    ("hls/sim_rtl.sh", "lance", "ext:questa", "make … sim"),
    ("hls/sim_rtl.sh", "lit", "dir:hlswork", "latence dans rtl.rpt"),
    ("hls/sim_progress.tcl", "pilote", "ext:questa", "run par tranches"),
    ("hls/bash_mentor_24", "depend", "ext:catapult", "environnement"),
    ("hls/demoFir.tcl", "lit", "dir:demofir", ""),
    ("dir:hlswork", "lance", "ext:precision", "rtl.vhdl.psr (à faire)"),
    ("ext:precision", "lance", "ext:vivado", "(phase 3)"),
    ("ext:vivado", "lance", "ext:zybo", "bitstream (phase 3)"),
]

# Parcours : (titre, explication, [(nœud, ce qu'on y fait), ...])
PARCOURS = [
    ("Changer le nombre de bits", "Nouvelle répartition des bits, de l'exploration jusqu'à Catapult.", [
        ("make:explore", "Choisir une config : make explore ARGS=\"pareto\" puis \"select <run> --apply\""),
        ("Exploration/explo/cli.py", "select --apply recopie la config du run"),
        ("cpp/config.hpp", "config.hpp remplacé (ancienne version dans git)"),
        ("make:coeffs", "OBLIGATOIRE : regénérer les ROM entières dans les nouveaux formats"),
        ("hls/gen_coeffs.py", "lit config.hpp + data/coef, écrit coeffs_k*_raw.hpp"),
        ("cpp/coeffs_k5_raw.hpp", "#error à la synthèse si on l'a oublié"),
        ("make:nonreg", "main et main_raw doivent donner les mêmes scores"),
        ("hls/ref/scores_k5.txt", "formats changés : regénérer la réf. (main 200 5 … --dump)"),
        ("hls/cnn.tcl", "à l'école : relancer le script (go analyze obligatoire)"),
        ("dir:rapports", "comparer avec cnn_summary / make hls-report"),
    ]),
    ("Synthèse HLS à l'école", "Du C++ au RTL vérifié, sans interface graphique.", [
        ("hls/bash_mentor_24", "source hls/bash_mentor_24"),
        ("hls/cnn.tcl", "mkdir -p hls/work && cd hls/work && catapult -shell -file ../cnn.tcl"),
        ("ext:catapult", "analyse cnn.cpp (+ coeffs_k5_raw.hpp), génère le RTL"),
        ("cpp/cnn.cpp", "top synthétisé"),
        ("ext:questa", "SCVerify : C++ seul puis compilation du banc RTL"),
        ("hls/tb_hls.cpp", "1 image de hls/ref/images_200.bin, comparée à scores_k5.txt"),
        ("hls/cnn_report.tcl", "cnn_report : sauvegarde + résumé"),
        ("dir:rapports", "git add hls/rapports && commit, pour analyser à la maison"),
    ]),
    ("Simulation RTL longue", "46 M cycles par image : en tâche de fond, avec compteur.", [
        ("hls/cnn_report.tcl", "cnn_sim_cmd affiche la commande"),
        ("hls/sim_rtl.sh", "nohup hls/sim_rtl.sh hls/work/Catapult_1/cnn.v1 1 > …/sim_rtl.out &"),
        ("hls/sim_progress.tcl", "lignes [sim] cycle … / … (%) | reste ~ …"),
        ("ext:questa", "verdict SCVerify PASSED / FAILED"),
        ("hls/catapult_report.py", "rapports + verdict copiés automatiquement"),
        ("dir:rapports", "resume.md"),
    ]),
    ("Explorer les formats", "Recherche automatique du nombre de bits minimal.", [
        ("make:explore", "make explore ARGS=\"run --runs 3\""),
        ("Exploration/explore.py", "point d'entrée"),
        ("Exploration/explo/search.py", "descente variable par variable"),
        ("Exploration/explo/runner.py", "compile la config (-D) et lance main --trace"),
        ("bin:main", "précision image par image"),
        ("Exploration/explo/monitor.py", "arrêt anticipé des candidats perdus"),
        ("Exploration/explo/cache.py", "évaluation mise en cache"),
        ("dir:runs", "résultats ; make explore ARGS=\"plot --no-show\" pour les graphes"),
    ]),
    ("Vérifier sur d'autres images", "La précision d'exploration est mesurée sur data_batch_1 (entraînement).", [
        ("make:validate", "make validate ARGS=\"<run> <run>:ref float -b test 2\""),
        ("Exploration/validate.py", "compile et lance les configs en parallèle"),
        ("data:cifar", "test_batch = vraie généralisation"),
        ("dir:runs", "validation.jsonl (cache image par image)"),
    ]),
    ("Non-régression après une modif du C++", "Toute modif de cnn.cpp / utils.* doit rester bit-exacte.", [
        ("cpp/utils.cpp", "modification"),
        ("make:nonreg", "make nonreg"),
        ("cpp/CMakeLists.txt", "recompile main et main_raw"),
        ("bin:main", "200 images, scores exacts"),
        ("hls/ref/scores_k5.txt", "comparaison au bit près"),
        ("make:tb-hls", "make tb-hls ARGS=3 : même testbench que sous Catapult"),
    ]),
]
