"""Version vectorisée (numpy) du CNN CIFAR-10.

Même réseau que cnn.py, mais sans boucles Python sur les pixels :
~1000x plus rapide, utilisable pour mesurer la précision sur un batch complet.
cnn.py reste le modèle de référence « boucles » qui servira pour le C++/HLS.

Format : NHWC (N images, H lignes, W colonnes, C canaux).
"""
import numpy as np

from utils import POOL_TF_SAME, POOL_CENTERED


def convolution_fast(x, kernel, bias):
    """Convolution 'SAME' avec padding à zéro.

    x      : (N, H, W, L)
    kernel : (M, M, L, C)
    bias   : (C,)
    sortie : (N, H, W, C)
    """
    M = kernel.shape[0]
    p = M // 2
    _, H, W, _ = x.shape
    xp = np.pad(x, ((0, 0), (p, p), (p, p), (0, 0)))
    out = np.zeros(x.shape[:3] + (kernel.shape[3],), dtype=np.float32)
    # Pour chaque position (m, n) du noyau : décalage de l'image puis produit
    # matriciel sur l'axe des canaux (L -> C).
    for m in range(M):
        for n in range(M):
            out += xp[:, m:m + H, n:n + W, :] @ kernel[m, n]
    return out + bias


def relu_fast(x):
    return np.maximum(x, 0)


def max_pool_fast(x, size, stride, mode=POOL_TF_SAME):
    """Max-pool size x size, pas stride, mêmes fenêtres que utils.max_pool.

    x      : (N, H, W, C)
    sortie : (N, H//stride, W//stride, C)
    Le padding vaut 0 comme dans utils.get_valid_pixel.
    """
    _, H, W, _ = x.shape
    H_out, W_out = H // stride, W // stride
    if mode == POOL_TF_SAME:
        before = 0
    elif mode == POOL_CENTERED:
        before = size // 2
    else:
        raise ValueError(f"mode de max_pool inconnu : {mode}")
    after_h = max((H_out - 1) * stride + size - before - H, 0)
    after_w = max((W_out - 1) * stride + size - before - W, 0)
    xp = np.pad(x, ((0, 0), (before, after_h), (before, after_w), (0, 0)))

    out = np.full((x.shape[0], H_out, W_out, x.shape[3]), -np.inf, dtype=x.dtype)
    for m in range(size):
        for n in range(size):
            window = xp[:, m:m + stride * H_out:stride, n:n + stride * W_out:stride, :]
            out = np.maximum(out, window)
    return out


def cnn_fast(images, tensors, pool_mode=POOL_TF_SAME, max_pool_ksize=3):
    """CNN vectorisé.

    images : (24, 24, 3) pour une image, ou (N, 24, 24, 3) pour un batch
    sortie : (10,) ou (N, 10) — scores avant softmax, argmax = classe prédite
    """
    single = images.ndim == 3
    x = images[None] if single else images
    x = x.astype(np.float32)
    assert x.shape[1:] == (24, 24, 3), f"{x.shape}"

    for k in (1, 2, 3):
        x = convolution_fast(x, tensors[f"conv{k}/weights"], tensors[f"conv{k}/biases"])
        x = relu_fast(x)
        x = max_pool_fast(x, max_pool_ksize, 2, pool_mode)

    x = x.reshape(len(x), -1)                                   # (N, 180), ordre HWC
    out = x @ tensors["local3/weights"] + tensors["local3/biases"]
    return out[0] if single else out
