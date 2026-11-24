# Validation des configurations (k=5)

Généré par `Exploration/validate.py` le 2026-11-24 13:21.

| config | bits mem | test_batch.bin [0, 10000) | data_batch_2.bin [0, 10000) | total |
|---|---|---|---|---|
| s5949 | 10.83 | 80.65 % [79.9, 81.4] | 86.47 % [85.8, 87.1] | 83.56 % [83.0, 84.1]  (20000 img) |
| s5947 | 12.56 | 80.79 % [80.0, 81.6] | 86.72 % [86.0, 87.4] | 83.75 % [83.2, 84.3]  (20000 img) |
| s5949:ref | 22.10 | 81.62 % [80.8, 82.4] | 87.88 % [87.2, 88.5] | 84.75 % [84.2, 85.2]  (20000 img) |
| float | 32 (float) | 81.62 % [80.8, 82.4] | 87.93 % [87.3, 88.6] | 84.78 % [84.3, 85.3]  (20000 img) |

Comparaison appariée avec **s5949** (mêmes images) : écart ± IC95 (pertes / gains)

| config | test_batch.bin | data_batch_2.bin | total |
|---|---|---|---|
| s5947 | +0.14 ± 0.42 pt  (218/232) | +0.25 ± 0.41 pt  (202/227) | +0.19 ± 0.29 pt  (420/459) |
| s5949:ref | +0.97 ± 0.45 pt  (210/307) | +1.41 ± 0.43 pt  (175/316) | +1.19 ± 0.31 pt  (385/623) |
| float | +0.97 ± 0.44 pt  (209/306) | +1.46 ± 0.43 pt  (171/317) | +1.21 ± 0.31 pt  (380/623) |

- s5949 : final du run 20261119-223144_k5_t1_s5949 (88.1 % sur 1000 img d'exploration)
- s5947 : final du run 20261119-202628_k5_t1_s5947 (88.0 % sur 1000 img d'exploration)
- s5949:ref : référence du run 20261119-223144_k5_t1_s5949 (89.0 % sur 1000 img d'exploration)
- float : python/cnn_fast.py, float32
