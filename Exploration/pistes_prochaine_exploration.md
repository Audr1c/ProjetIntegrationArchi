# Pistes pour la prochaine exploration

Deux idées pour rendre la descente moins dépendante du hasard et faire baisser le nombre de bits final :

1. un **ordre des variables pondéré par leur poids** (déterministe, ou tiré au hasard avec des probabilités proportionnelles au poids) ;
2. un **seuil de précision croissant au fil des passes** (0 point de perte toléré au début, puis on relâche petit à petit jusqu'au seuil max).

## Constat de départ (12 runs, k=5, seuil 1 pt, 1000 images)

Sources : `runs/bits_stats/bits_all.png`, `bits_mean.csv`, et le champ `path` de chaque `runs/<run>/state.json`.

- Selon le run, la config finale va de **10,83 à 17,67 bits moyens par valeur** (médiane 14,7). Le seul paramètre qui change entre les runs est l'ordre aléatoire des variables.
- Les **I** finissent presque toujours à la même valeur (écart-type ≤ 0,6 bit), car ils sont fixés par la dynamique des valeurs. Toute la variabilité porte sur les **F** (±2 à 3,5 bits d'un run à l'autre).
- Un run est **bon partout ou mauvais partout**. Pour presque toutes les variables, le F final est positivement corrélé au total du run (jusqu'à +0,8), même une fois retirée la contribution de la variable elle-même. On ne voit aucun compromis du type « une variable courte, les autres longues ».
- **Cause : la marge de 1 point est dépensée dès les 0 à 9 premières étapes**, sur 40 à 49. Ensuite, la descente ne peut plus rien réduire qui coûte une image.

| run | bits finaux | marge épuisée à l'étape | variables qui l'ont dépensée (poids `mem`) |
|---|---|---|---|
| s5949 (meilleur) | **10,83** | 4 / 43 | ker2.F (30 %), conv1.I (21,6 %) |
| s5958 | 12,86 | 2 / 49 | pool1.F (5,4 %), acc3.I (0,4 %) |
| s5948 | 17,12 | 0 / 42 | bias1.F (≈0 %), acc3.F (0,4 %), pool3.F (0,1 %) |
| s5951 | 17,57 | 0 / 40 | acc3.F (0,4 %), accfc.I (≈0 %) |

Le run est bon quand la marge est dépensée sur une variable lourde. Il est mauvais quand des variables qui ne pèsent rien en mémoire (biais, acc3, accfc, pool3) la consomment, car les grosses variables restent alors larges.

Remarque : le run `s4816` (ancien, sans variables `acc`) n'est pas comparable. Il faut l'exclure des statistiques de `bits_stats.py`.

## Idée 1 : ordre des variables selon leur poids

### Poids des variables

Le poids d'une variable est sa part dans la métrique visée. Pour `mem`, c'est le nombre de valeurs stockées, déjà calculé par `explo/formats.py:usage_counts`. Pour k=5, le total est de 170 606 valeurs :

| variable | poids `mem` | | variable | poids `mem` |
|---|---|---|---|---|
| ker2 | 30,0 % | | conv2 | 2,7 % |
| acc1 | 21,6 % | | fck | 1,1 % |
| conv1 | 21,6 % | | input | 1,0 % |
| ker3 | 9,4 % | | pool2 | 0,7 % |
| pool1 | 5,4 % | | acc3, conv3 | 0,4 % |
| ker1 | 2,8 % | | pool3 | 0,1 % |
| acc2 | 2,7 % | | biais, fcb, accfc, out | < 0,05 % |

Les trois premières variables (ker2, acc1, conv1) représentent **73 %** du total. Ce sont elles qui doivent passer en premier.

Le I et le F d'une même variable ont le même poids : un bit retiré sur l'un ou sur l'autre rapporte autant.

### Deux variantes

- **`--order weight`** (déterministe) : tri par poids décroissant. Il donne un seul résultat reproductible, mais il n'explore plus du tout l'espace des ordres.
- **`--order weighted-random`** (aléatoire pondéré) : tirage sans remise avec une probabilité proportionnelle à `poids ** alpha`. La méthode Efraimidis–Spirakis le fait en une ligne : on trie par `u ** (1 / w)`, avec `u` uniforme dans ]0, 1[, en ordre décroissant.
  - `alpha = 0` : ordre uniforme (comportement actuel) ;
  - `alpha = 1` : proportionnel au poids ;
  - `alpha` grand : on se rapproche du tri déterministe.
  - Il faut un **poids plancher** (par exemple 0,1 %). Sinon les biais, dont le poids est quasi nul, tombent toujours en dernier et ne sont jamais réduits avant que la marge soit épuisée. C'est peut-être sans importance, puisqu'ils ne coûtent rien, mais autant le contrôler.

### Où modifier

- `explo/cli.py` : ajouter les choix `weight` et `weighted-random` à `--order`, plus une option `--order-alpha` (1 par défaut).
- `explo/search.py`, construction de `self.plan` (vers la ligne 430) : remplacer `self.rng.shuffle(vs)` par le tri pondéré, en utilisant `self.rng` pour que la graine reste reproductible.
- Enregistrer `order` et `alpha` dans `params.json` / `summary.json` pour pouvoir comparer les runs.

## Idée 2 : seuil croissant au fil des passes

### Principe

Au lieu d'une seule passe avec un seuil de 1 point, on fait **plusieurs passes avec un seuil qui augmente**, par exemple `0 → 0,25 → 0,5 → 1` point.

- **Passe à 0 point** : chaque variable descend aussi bas que possible *sans perte nette d'image* par rapport à la référence. Toutes les variables récupèrent ainsi les bits « gratuits », quel que soit leur ordre de passage. Aujourd'hui, une variable visitée après l'épuisement de la marge n'obtient même pas ces bits-là.
- **Passes suivantes** : la marge est libérée par petites tranches. Aucune variable ne peut plus dépenser le point entier à elle seule dès le début.

Les seuils sont **cumulés et mesurés par rapport à la référence de départ** : précision ≥ `ref_acc − seuil_de_la_passe`. Ce ne sont pas des marges supplémentaires à chaque passe. On ne recalcule pas la référence entre les passes.

### Combinaison avec l'idée 1

Les deux idées se complètent :

- à seuil 0, l'ordre compte peu ;
- dans les passes à seuil > 0, la marge est rare, donc il faut la donner en priorité aux variables lourdes (ordre pondéré).

Variante à tester : faire passer **uniquement les variables lourdes** (poids > 1 %) dans les dernières passes, pour gagner du temps.

### Points d'attention

- **Le seuil est utilisé à trois endroits dans `explo/search.py`**. Ils doivent tous lire le seuil de la passe en cours, et non plus `self.threshold` :
  - `status_of()` : décision ok/ko ;
  - `PairedMonitor(...)` : arrêt anticipé ;
  - `T` dans `_eval()` : réutilisation des évaluations coupées.
  
  `Descent` connaît déjà son `pass_no` : on en déduit le seuil, qu'il faut ensuite passer en paramètre à `_eval()` et à `status_of()`, qui ne le reçoivent pas aujourd'hui.
- **Le cache reste valable.** Un candidat coupé avec `min_loss > T` à un seuil élevé reste coupé à un seuil plus bas. Le test existant (`hit["min_loss"] > T`) gère déjà ce cas. En revanche, un candidat coupé à seuil 0 doit être réévalué à seuil 1, ce que le test fait aussi.
- **Le seuil 0 est sévère avec le moniteur apparié.** La passe à 0 refusera beaucoup de pas, mais ces refus sont rapides (arrêt anticipé). Il faudra surveiller si `z = 2` tue trop tôt des candidats qui sont en réalité neutres, à ±1 image près. Si c'est le cas, on peut commencer à 0,1 point au lieu de 0.
- **Le nom du run** contient `t{threshold}`. Il faut y mettre le seuil max, et enregistrer la liste complète des seuils dans `params.json`.

### Interface proposée

```bash
make explore ARGS="run --order weighted-random --order-alpha 1 --threshold-schedule 0 0.25 0.5 1 --runs 6"
```

- `--threshold-schedule S1 S2 …` remplace `--threshold` et `--passes` : une passe par seuil.
- Sans cette option, on garde le comportement actuel (une passe au seuil `--threshold`).

## Comment comparer les stratégies

On ne juge pas une stratégie sur un seul run : la dispersion actuelle est de ±3,5 bits. Pour chaque stratégie, il faut **au moins 6 runs avec des graines différentes**, puis comparer :

- la **médiane** et le **pire cas** des bits finaux, et pas seulement le meilleur run. La référence actuelle est : médiane 14,7, meilleur 10,83, pire 17,67 ;
- la **dispersion**, puisque l'objectif est aussi de dépendre moins de la graine ;
- le **temps par run**, car plusieurs passes coûtent plus cher (aujourd'hui environ 1 h par run avec `--parallel-vars 2`) ;
- la précision finale sur un **autre lot d'images** (`data_batch_2.bin`), pour vérifier que les gains ne viennent pas d'un surapprentissage sur les 1000 images de l'exploration.

Stratégies à comparer, dans l'ordre :

1. `random`, seuil 1 en une passe (les 12 runs existants) ;
2. `weight`, seuil 1 en une passe (un seul run suffit, c'est déterministe) ;
3. `weighted-random` avec alpha = 1, seuil 1 en une passe ;
4. `random` avec le seuil progressif `0 0.25 0.5 1` ;
5. `weighted-random` avec le seuil progressif `0 0.25 0.5 1`.

Comparer 2 et 3 à 1 mesure l'effet de l'ordre seul. Comparer 4 à 1 mesure l'effet du seuil progressif seul. La stratégie 5 combine les deux.
