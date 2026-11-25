# ExplorationHLS : exploration automatique des directives Catapult

Cherche une configuration de directives (pipeline, déroulage, mémoires) selon l'un des deux objectifs (`--goal`) :

- `cost` (défaut) : la configuration **la moins coûteuse** dont la latence tient la cible ;
- `perf` : la configuration **la plus rapide** (latence + débit) qui tient tous les budgets, débarrassée ensuite
  de ce qui ne sert pas. Ce run garde aussi la moins chère sous la cible (`cheapest_directives.tcl`).

Le **débit** est le nombre de cycles entre deux images : les quatre blocs travaillent en parallèle sur des
images successives, donc le débit est fixé par le bloc le plus lent (le « goulot », ◆ dans l'affichage). Le code C++ ne change pas : seules les directives varient, et chaque candidat
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
make explore-hls ARGS="run --goal perf"   # le plus rapide possible sous les budgets
```

- Le dépôt doit être cloné dans un chemin **sans espace**.
- Si `make venv-ecole` a affiché « installation dans ~/.local (pip --user) » (cas constaté le 2026-11-25 :
  pas de `python3-venv`), effacer le dossier `.venv/` incomplet. `make explore-hls` utilise alors `python3`,
  qui voit les paquets `--user`. Signe du problème : affichage texte et pas de graphes même sans `--plain`.
- `--jobs N` lance N synthèses en parallèle. Chacune prend une licence et a son propre projet de base.
- **Ctrl-C** arrête proprement. Relancer la même commande reprend : les synthèses déjà faites sont en cache.
- `--plain` donne un affichage texte, une ligne par événement (utile avec `nohup … > explo.txt &`).
- Sans `rich` ni `matplotlib`, l'outil tourne quand même : affichage texte, pas de graphes.

## Run long (plusieurs heures, sans surveillance)

```bash
# tmux (si installé) : le run survit à la fermeture du terminal ; Ctrl-b d pour se détacher, tmux attach -t explo
tmux new -s explo
make explore-hls ARGS="run --goal perf --hours 10"

# sinon nohup + affichage texte, et suivre le journal
nohup make explore-hls ARGS="run --goal perf --hours 10 --plain" > ExplorationHLS/explo.txt 2>&1 &
tail -f ExplorationHLS/explo.txt
```

- Ordre de grandeur : 2 à 5 minutes par synthèse, donc environ 15 à 25 synthèses par heure avec 1 licence.
  Par défaut : au plus 300 synthèses (`--max-evals`), 45 minutes au plus par synthèse (`--timeout`).
- **Phase 4, polissage** (désactivable avec `--no-polish`) : une fois la montée et le repli finis, on synthétise
  *tous* les voisins à un réglage près de la meilleure config, sans laisser le modèle trancher. Le premier meilleur
  est retenu et on recommence, jusqu'à ce qu'aucun voisin ne fasse mieux. C'est là que le temps long sert.
- **Licence prise par quelqu'un d'autre** : la synthèse n'est pas comptée comme ratée. On réessaie chaque minute,
  puis le run s'arrête proprement au bout de `--license-wait` minutes (30 par défaut).
- **Sauvegarde à chaque pas retenu** : `summary.json`, `best_directives.tcl` et les graphes sont réécrits. Si la
  session est coupée (déconnexion, reboot la nuit), relancer la même commande repart du cache sans rien refaire.

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
   | 5 MAC/cycle, entrée en 5 bancs | `MAC_N` déroulée, poids et carte d'entrée en 5 bancs, II = 1 (puis 2) |
   | 10 MAC/cycle | `MAC_N` déroulée + `MAC_CI` ×2, poids en 10 bancs, entrée en 5 bancs double port |

   La carte d'entrée de layer2 et layer3 est la copie locale `x` du canal (`x = in.read()` dans `cnn.cpp`).
   Un canal n'accepte pas `INTERLEAVE`, mais cette copie l'accepte : 5 pixels consécutifs tombent dans
   5 bancs différents. Pour layer1, l'entrée est l'interface `image` ; si Catapult refuse de la découper,
   le refus est mémorisé et le réglage n'est plus reproposé pour ce bloc.

   Le modèle analytique (`hlsexplo/model.py`) prédit le gain en cycles et le surcoût de chaque candidat.
   Un candidat qui ne peut pas gagner 2 % est écarté sans synthèse (« inutile (modèle) »). Les autres
   partent en synthèse par ordre de gain/surcoût. Un pas est retenu s'il est valide et gagne au moins
   2 %. Après chaque synthèse, le modèle est recalé sur les vrais chiffres de Catapult.
4. **Repli**, une fois la cible atteinte : on retire ce qui coûte (×10 → ×5, double port → simple, pipeline,
   ping-pong), le plus économe d'abord, tant que tous les seuils tiennent (et, en `perf`, la vitesse à 1 % près).
5. **Polissage** : voir « Run long » ci-dessus.

## Affichage

- **Configuration retenue vs seuils** : une jauge par grandeur (latence, débit en images/s, BRAM, DSP, LUT, slack). Le trait `│` marque le seuil ; la barre est
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

1. la ligne `découverte : N boucles nommées dans 4 blocs`. S'il n'y a aucune boucle, l'erreur affiche le début de
   `work/w0/loops.txt` ; le journal est dans `work/w0/discover.log`. Le projet de base est **gardé** : après une
   correction, relancer refait seulement la découverte (`discover.tcl` : `project load` + `directive get`), pas
   `go analyze`. Le premier essai (2026-11-25) a trouvé 0 boucle : le parseur exigeait `fonction:LABEL`, alors
   qu'une boucle labellisée s'appelle souvent juste `LABEL` (manuel Catapult, « Labels ») ; c'est corrigé ;
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
