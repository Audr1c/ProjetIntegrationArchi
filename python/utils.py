import numpy as np


# Position de la fenêtre du max-pool
POOL_TF_SAME = "tf_same"     # fenêtre [i*stride, i*stride + size - 1] (TensorFlow padding='SAME')
POOL_CENTERED = "centered"   # fenêtre centrée sur i*stride


def get_valid_pixel(image, row, col, chan):
    """Pixel image[row, col, chan], ou 0 s'il est hors de l'image (padding)."""
    H, W, L = image.shape
    if 0 <= row < H and 0 <= col < W and 0 <= chan < L:
        return image[row, col, chan]
    return 0


def convolution_feature(image: np.ndarray, kernel: np.ndarray, bias: np.ndarray, stats=None, name="conv"):
    r"""
    kernel : (M, N, L, C)  M = N = 3 ou 5
    bias   : (C,)
    image  : (H, W, L)
    sortie : (H, W, C)
    (i, j) \in (H, W) : position dans l'image de sortie
    L : nb de composantes en entrée
    C : nb de composantes en sortie
    $$S_{i,j,c} = \sum_{m,n\in [-1,1], l\in [1,L]} (I_{i+m,j+n, l}\times K_{m,n,l,c}) +bias_c$$
    """
    H, W, L = image.shape
    M, N, L2, C = kernel.shape
    assert M == N
    assert L == L2
    assert bias.shape == (C,), f"{bias.shape}"
    image_out = np.zeros((H, W, C))
    for i in range(H):
        for j in range(W):
            for c in range(C):
                for l in range(L):
                    for m in range(-(M//2), M//2 + 1):
                        for n in range(-(N//2), N//2 + 1):
                            image_out[i, j, c] += get_valid_pixel(image, i + m, j + n, l) * kernel[m + M//2, n + N//2, l, c]
                            
    if stats is not None:
        stats.record(f"{name}/acc", image_out)
    for i in range(H):
        for j in range(W):
            for c in range(C):
                image_out[i, j, c] += bias[c]
    if stats is not None:
        stats.record(f"{name}/acc+bias", image_out)
    return image_out


def macc(A: np.ndarray, B: np.ndarray, C: np.ndarray, stats=None, name="fc"):
    r"""
    S = A . B + C
    $$S_{j} = \sum_{k} (A_{k}\times B_{k,j}) + C_{j}$$
    """
    acc = np.matmul(A, B)
    result = acc + C
    if stats is not None:
        stats.record(f"{name}/acc", acc)
        stats.record(f"{name}/out", result)
    return result


def max_pool(image, size: int, stride: int, mode: str = POOL_TF_SAME):
    """
    image : (H, W, c)
    size  : fenêtre size x size
    stride: pas stride x stride
    mode  : POOL_TF_SAME  -> lignes [i*stride, i*stride + size - 1]  (réseau entraîné ainsi)
            POOL_CENTERED -> lignes [i*stride - size//2, i*stride + size//2]

    image_out : (H/stride, W/stride, c)
    """
    H_in, W_in, channels = image.shape
    H_out, W_out = H_in // stride, W_in // stride
    image_out = np.zeros((H_out, W_out, channels))

    if mode == POOL_TF_SAME:
        offsets = range(size)
    elif mode == POOL_CENTERED:
        offsets = range(-(size//2), size//2 + 1)
    else:
        raise ValueError(f"mode de max_pool inconnu : {mode}")

    for c in range(channels):
        for i in range(H_out):
            for j in range(W_out):
                max_value = -float('inf')
                for m in offsets:
                    for n in offsets:
                        current_value = get_valid_pixel(image, i*stride + m, j*stride + n, c)
                        if current_value > max_value:
                            max_value = current_value
                image_out[i, j, c] = max_value

    return image_out


def relu(image):
    """
    image     : (H, W, c)
    image_out : (H, W, c)
    """
    H, W, C = image.shape
    image_out = np.zeros((H, W, C))
    for i in range(H):
        for j in range(W):
            for c in range(C):
                image_out[i, j, c] = max(image[i, j, c], 0)

    return image_out

