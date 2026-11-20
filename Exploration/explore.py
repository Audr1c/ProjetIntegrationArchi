#!/usr/bin/env python3
"""
Exploration bits / précision des formats virgule fixe du CNN C++ (cpp/).

Chaque format ac_fixed<W, I, S> de cpp/config.hpp est décrit par deux variables :
    I : bits de partie entière (dynamique)
    F : bits de partie fractionnaire (précision),  W = I + F

Algorithme (une exploration) :
    1. Référence : configuration large (beaucoup de bits), évaluée image par image.
       Pour chaque image on note la marge = score(bonne classe) - meilleur autre score.
    2. Ordre des images : d'abord celles à petite marge (près de la frontière de décision,
       ce sont elles qui basculent quand on retire des bits), avec quelques images très sûres
       intercalées pour voir tout de suite un effondrement. Le même ordre sert à tous les candidats.
    3. Descentes : pour une variable de valeur v, on lance v-1, v-2, v-4, v-8, v-16... puis, dès
       qu'un worker se libère, on relance au milieu du plus grand intervalle encore inconnu
       (dichotomie asynchrone). Un calcul devenu inutile est tué (v-4 casse : v-8 ne sert plus).
       On garde la plus petite valeur dont la précision reste >= référence - seuil.
       --parallel-vars P : P descentes en même temps (variables différentes), ~workers/P cœurs
       chacune. Un succès obtenu avant qu'une autre descente ne valide une réduction est
       revérifié sur la configuration à jour avant d'être retenu (un échec, lui, reste valable).
    4. Arrêt anticipé : chaque candidat est comparé image par image à la référence
       (mêmes images, même ordre). On l'arrête dès que, même en étant optimiste sur les images
       restantes, il ne peut plus repasser sous le seuil (voir PairedMonitor).

Abscisse des graphes : nombre de bits pondéré par l'utilisation de chaque type
    mem : pondéré par le nombre de valeurs stockées de ce type
    ops : pondéré par le nombre de lectures comme opérande (MAC, pool, relu)
affiché en bits moyens par valeur (axe du bas) et en total (axe du haut).

Code : Exploration/explo/
    paths.py      chemins, compilateur            formats.py   formats explorés, bits pondérés, config.hpp
    runner.py     compile et lance cpp/main       monitor.py   comparaison à la référence, ordre des images
    search.py     descentes et exploration        cache.py     cache des évaluations, runs stockés
    dashboard.py  affichage rich                  plots.py     graphes (PNG)
    sessions.py   sessions / reprise              cli.py       commandes et options

Tout est stocké dans Exploration/runs/ :
    cache.jsonl             toutes les configurations déjà évaluées, une ligne chacune (réutilisées entre runs)
    <run>/params.json       paramètres de l'exploration
    <run>/reference.json    référence image par image (marge, succès) et ordre des images
    <run>/order.txt         ordre d'évaluation des images
    <run>/history.jsonl     chaque évaluation (variable, valeur, précision, bits, statut, courbe)
    <run>/summary.json      référence, configuration finale, chemin suivi, gains de temps
    <run>/config.hpp        configuration finale, prête à remplacer cpp/config.hpp
    <run>/plot.png          nuage de points bits / précision
    <run>/curves.png        écart à la référence image par image (quand coupe-t-on)
    <run>/plot_zoom.png     même nuage, zoomé sur la partie haute (réductions retenues annotées)
    <run>/formats.png       barres des formats : départ / final
    <run>/state.json        état pour reprendre un run interrompu
    sessions/<id>.json      liste de runs prévue (graines, seuils) et leur statut
    all_k*_n*_mem[_zoom].png  toutes les explorations + front de Pareto (zoom : ids des points)
    selected.json           historique des configurations sélectionnées

Interruption : Ctrl-C arrête proprement la run en cours (tout est sauvegardé), un 2e Ctrl-C arrête net.
Relancer la même commande propose de continuer la session (runs restants, run interrompu repris
à la dernière variable terminée ; les évaluations déjà faites viennent du cache).

Commandes :
    python explore.py run    [options]           lance une ou plusieurs explorations
    python explore.py list                       tableau de toutes les explorations
    python explore.py show   <run>               formats finaux d'une exploration (début du nom suffit)
    python explore.py pareto [--k 5]             meilleurs compromis bits/précision, tous runs confondus
    python explore.py plot   [--k 5] [--metric mem|ops]   regénère tous les graphes
    python explore.py select <run|id> [--apply]  choisit une configuration ; --apply écrit cpp/config.hpp
    (depuis la racine : make explore ARGS="run --runs 3")

Options de `run` [valeur par défaut] :

  Ce qu'on mesure
    --k 3|5                 [5]     taille du noyau des convolutions (choisit le fichier de coefficients)
    --images N              [1000]  nombre d'images évaluées par configuration (précision au 0,1 % près)
    --batch FICHIER         [data_batch_1.bin]  fichier CIFAR-10 utilisé

  Quand une réduction est acceptée
    --threshold PTS         [1.0]   perte de précision tolérée, en points de % sous la référence
                                    (ex. référence 88,6 % et 1.0 -> on accepte tant que >= 87,6 %)
    --threshold-range A B   [-]     seuil tiré au hasard entre A et B pour chaque run (remplace --threshold)
    --start-F N             [12]    bits fractionnaires de départ de tous les formats (point "large")

  Ordre et nombre d'explorations
    --runs N                [1]     nombre d'explorations à la suite (graines seed, seed+1, ...)
    --seed S                [hasard] graine qui fixe l'ordre aléatoire des variables
    --order random|fixed    [random] ordre des 32 variables : mélangé, ou format par format
    --passes N              [1]     nombre de passages sur toutes les variables

  Parallélisme
    --workers N             [nb de cœurs]  évaluations C++ lancées en même temps
    --parallel-vars P       [1]     variables descendues en même temps (~workers/P cœurs chacune)

  Gagner du temps sur les configurations perdues
    --no-early-stop                 évalue toujours les N images (désactive l'arrêt anticipé)
    --z Z                   [2.0]   prudence de l'arrêt anticipé : plus grand = coupe moins et plus tard
    --min-images N          [20]    nombre d'images minimum avant d'avoir le droit de couper
    --no-reorder                    garde l'ordre naturel des images (sinon : difficiles d'abord)
    --easy-frac F           [0.1]   part d'images très sûres intercalées au début (détecte un effondrement)
    --easy-every N          [4]     une image sûre toutes les N images

  Reprise
    --resume                        reprend sans poser la question une session identique non terminée
    --new                           ignore la session non terminée et en démarre une nouvelle

Exemples :
    python explore.py run                                    # 1 exploration, réglages par défaut
    python explore.py run --runs 4 --threshold-range 0.5 2   # 4 explorations, seuils différents
    python explore.py run --parallel-vars 2 --threshold 0.5  # 2 descentes à la fois, plus exigeant
    python explore.py run --images 200 --runs 1              # essai rapide (moins fiable)
"""

import sys

try:
    import rich  # noqa: F401
    import matplotlib  # noqa: F401
except ImportError:
    sys.exit("Modules manquants : .venv/bin/pip install -r requirements.txt")

from explo.cli import main

if __name__ == "__main__":
    main(__doc__)
