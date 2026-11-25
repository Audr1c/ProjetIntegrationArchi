# ExplorationHLS : exploration automatique des directives Catapult

Cherche la configuration de directives (pipeline, déroulage, mémoires) **la moins coûteuse en ressources**
qui respecte tous les seuils. Le code C++ ne change pas : seules les directives varient, et chaque candidat
repart du même projet Catapult déjà analysé (pas de `go analyze`).

## Seuils (`hlsexplo/limits.py`)

| Seuil | Valeur par défaut | Option |
|---|---|---|
| Latence par image | ≤ 10 M cycles (100 ms à 100 MHz, soit 10 img/s) | `--target 10` |
| BRAM18 | ≤ 60 % de 280 = 168 | `--bram 60` |
| DSP | ≤ 50 % de 220 = 110 | `--dsp 50` |
| LUT | ≤ 50 % de 53 200 = 26 600 | `--lut 50` |
| Slack (estimation Catapult) | ≥ 0 ns | `--slack 0` |
| Directives | toutes appliquées (sinon le résultat ne correspond pas à la config demandée) | — |
| Durée d'une synthèse | ≤ 30 min, sinon la synthèse est tuée | `--timeout 30` |

La bit-exactitude (SCVerify) et le timing réel (Precision ou Vivado) ne sont pas vérifiés pendant
l'exploration. Ils se vérifient sur la configuration retenue (voir la dernière section).

## À l'école

```bash
source hls/bash_mentor_24                 # Catapult dans le PATH
make venv-ecole                           # une seule fois : Python 3.8, sans sudo (requirements-ecole.txt)
make explore-hls ARGS="run --fake"        # 1 minute, sans licence : pour voir l'outil tourner
make explore-hls ARGS="run"               # la vraie exploration (1 licence Catapult)
```

- Le dépôt doit être cloné dans un chemin **sans espace**.
- `--jobs N` lance N synthèses en parallèle. Chacune prend une licence et a son propre projet de base.
- **Ctrl-C** arrête proprement. Relancer la même commande reprend : les synthèses déjà faites sont en cache.
- `--plain` donne un affichage texte, une ligne par événement (utile avec `nohup … > explo.txt &`).
- Sans `rich` ni `matplotlib`, l'outil tourne quand même : affichage texte, pas de graphes.

## Méthode (`hlsexplo/search.py`)

1. **Projet de base**, construit une fois par version du code : `hls/cnn.tcl` est sourcé avec
   `CNN_STOP_AT = assembly`, donc sans aucune directive de boucle ni de mémoire. Catapult liste ensuite les
   chemins exacts des boucles et des mémoires (`loops.txt`, `resources.txt`), puis le projet est sauvé.
2. **Référence** : aucune directive.
3. **Montée**, tant que la latence dépasse la cible. Pour chaque bloc (`layer1`, `layer2`, `layer3`, `dense`),
   le barreau suivant de l'échelle devient un candidat :

   | Barreau | Directives |
   |---|---|
   | ReLU + pool pipelinés | II = 1 sur `RELU` et `POOL_CO` |
   | MAC pipelinées | II = 1 (puis 2) sur `CONV_CO` : Catapult aplatit toutes les boucles internes |
   | 2 MAC/cycle + RAM double port | `MAC_N` déroulée par 2, poids en 2 bancs, cartes en `BLOCK_DPRAM_RBW` |
   | 5 MAC/cycle | `MAC_N` déroulée complètement, poids en 5 bancs, II = 3 (puis 4) |

   Le modèle analytique (`hlsexplo/model.py`) prédit le gain en cycles et le surcoût de chaque candidat.
   Un candidat qui ne peut pas gagner 2 % est écarté sans synthèse (« inutile (modèle) »). Les autres
   partent en synthèse par ordre de gain/surcoût. Un pas est retenu s'il est valide et gagne au moins
   2 %. Après chaque synthèse, le modèle est recalé sur les vrais chiffres de Catapult.
4. **Repli**, une fois la cible atteinte : on retire ce qui coûte (×5 → ×2, double port → simple, pipeline,
   ping-pong), le plus économe d'abord, tant que tous les seuils tiennent.

## Affichage

- **Configuration retenue vs seuils** : une jauge par grandeur. Le trait `│` marque le seuil ; la barre est
  verte sous le seuil et rouge au-dessus. Dessous : la latence empilée par bloc et le chemin suivi.
- **Réglages par bloc** : pipeline, MAC en parallèle, type de RAM, latence mesurée, part du total, prédiction.
- **Workers Catapult** : l'étape en cours (loops, memories, …, extract) et le temps écoulé.
- **Dernières évaluations** : les valeurs précédées de `~` sont des prédictions du modèle, sans synthèse.

## Fichiers

```
explore_hls.py           point d'entrée (docstring = toutes les options)
hlsexplo/                paths, space (réglages, directives), limits (seuils), model, backend (Catapult / faux),
                         search, store, dashboard, plots, report
runs/cache.jsonl         toutes les synthèses (versionné)
runs/<run>/              params.json, history.jsonl, summary.json, best_directives.tcl, discovery.json,
                         evals/<id>/ (cand.tcl, directives_log.txt, fin du journal, rtl.rpt.gz, cycle.rpt.gz),
                         pareto.png, evolution.png (non versionnés : make explore-hls ARGS="plot <run>")
runs_fake/               runs du faux Catapult (non versionné)
work/w<N>/               projets Catapult (non versionné ; base.log, cand.log en cas de problème)
```

## Premier vrai run : ce qu'il faut regarder

L'outil a été testé sous Python 3.8 + pip 21.1.2, avec un faux Catapult et une maquette de l'exécutable
`catapult`, mais **jamais encore avec le vrai Catapult**. Au premier run, vérifier :

1. la ligne `découverte : N boucles nommées dans 4 blocs`. S'il y a 0 boucle, regarder
   `work/w0/loops.txt` (la syntaxe de `directive get … -match glob` est peut-être différente en 2024.2) ;
2. le statut `! directive refusée` dans le tableau : le détail est dans `runs/<run>/evals/<id>/directives_log.txt`
   (lignes `KO`). Les points les plus incertains sont `-INTERLEAVE` sur une ROM et le double port sur un canal ;
3. en cas d'échec, la fin du journal Catapult se trouve dans `evals/<id>/catapult_fin.txt`.

## Utiliser le résultat

```bash
make explore-hls ARGS="show"     # chemin suivi et configuration retenue
make explore-hls ARGS="tcl"      # directives retenues
```

Dans `hls/cnn.tcl` : `set DIRECTIVES_FILE ExplorationHLS/runs/<run>/best_directives.tcl`, puis relancer
le script complet. Il génère le RTL avec ces directives, lance SCVerify en C++, puis la simulation RTL
(`hls/sim_rtl.sh`), désormais raisonnable avec ~10 M cycles par image. Ensuite, Precision ou Vivado
donnent le vrai timing.
