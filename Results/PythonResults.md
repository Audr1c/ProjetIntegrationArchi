# CNN fast vs  CNN slow python 
Config : 3x3 
On 100 images
somme des errurs cumulé : 0.0005520820117566327

```log
##### finished ######
Resulsts for a 3x3 kernel
Got an accuracy of 77.00%
Got an accumulating error of 0.0005520820117566327
```


# results cnn_fas :

| size      | poolmode           | pool_size | Results      |
| --------- | ------------------ | --------- | ------------ |
| 3x3       | POOL_CENTERED      | 3x3       | 62.36%       |
| ==🟡3x3== | ==🟡POOL_TF_SAME== | ==🟡3x3== | ==🟡77.03%== |
| 5x5       | POOL_CENTERED      | 3x3       | 74.51%       |
| ==🟡5x5== | ==🟡POOL_TF_SAME== | ==🟡3x3== | ==🟡87.81%== |
| 5x5       | POOL_TF_SAME       | 5x5       | 71.27%       |
