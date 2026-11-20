"""Comparaison image par image avec la référence (arrêt anticipé) et ordre des images."""

import math
from collections import deque

# ============================================================
# Comparaison image par image avec la référence
# ============================================================

class PairedMonitor:
    """
    Le candidat et la référence voient les mêmes images dans le même ordre.
    Après k images :
        D = (succès de la référence) - (succès du candidat)    -> pertes nettes
        Le candidat est accepté à la fin si D_final <= T  (T = seuil x n / 100 images)
    Sur les images restantes, le candidat ne peut que :
        - perdre encore des images (on suppose 0 perte : hypothèse optimiste pour lui)
        - gagner des images que la référence rate (au plus W_rest, nombre connu)
    Borne exacte       : D - W_rest > T                         -> échec certain
    Borne statistique  : D - gain_max > T, avec gain_max = W_rest*g + z*sqrt(W_rest*g*(1-g))
                         g = taux de gain observé sur les erreurs de la référence (Laplace)
    Comme les images difficiles passent en premier, les gains restants sont surestimés :
    la borne est prudente, elle ne coupe que les candidats nettement perdus.
    """

    def __init__(self, ref_seq, threshold_pts, z, min_images):
        self.ref = ref_seq
        self.n = len(ref_seq)
        self.T = threshold_pts * self.n / 100
        self.z = z
        self.min_images = min_images
        self.wrong_after = [0] * (self.n + 1)          # erreurs de la référence après la position k
        for i in range(self.n - 1, -1, -1):
            self.wrong_after[i] = self.wrong_after[i + 1] + (1 - ref_seq[i])
        self.k = self.D = self.G = self.W = 0

    def update(self, correct):
        r = self.ref[self.k]
        self.D += r - correct
        if r == 0:
            self.W += 1
            self.G += correct
        self.k += 1

    def min_loss(self):
        w_rest = self.wrong_after[self.k]
        g = (self.G + 1) / (self.W + 2)
        gain_max = w_rest * g + self.z * math.sqrt(w_rest * g * (1 - g))
        return self.D - gain_max, self.D - w_rest

    def should_stop(self):
        if self.k < self.min_images or self.k >= self.n:
            return False
        return self.min_loss()[0] > self.T

    def boundary(self):
        """Valeur de D au-delà de laquelle on coupe, en fonction de k (pour les graphes, G = 0)."""
        out = []
        for k in range(self.n + 1):
            w_rest = self.wrong_after[k]
            w_seen = self.wrong_after[0] - w_rest
            g = 1 / (w_seen + 2)
            out.append(self.T + w_rest * g + self.z * math.sqrt(w_rest * g * (1 - g)))
        return out


def make_order(margins, easy_frac, easy_every):
    """
    margins : {indice: marge de la référence}
    Images à petite |marge| d'abord ; une image très sûre (grande marge positive)
    toutes les `easy_every` positions, pour `easy_frac` des images.
    """
    idx = list(margins)
    hard = sorted(idx, key=lambda i: abs(margins[i]))
    easy = sorted((i for i in idx if margins[i] > 0), key=lambda i: -margins[i])
    easy = easy[:int(easy_frac * len(idx))]
    easy_set = set(easy)
    hard = deque(i for i in hard if i not in easy_set)
    order, e = [], 0
    while hard or e < len(easy):
        if e < len(easy) and (len(order) % easy_every == easy_every - 1 or not hard):
            order.append(easy[e])
            e += 1
        else:
            order.append(hard.popleft())
    return order
