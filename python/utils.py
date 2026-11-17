import numpy as np


def get_valid_pixel(image, x, y, chan):
    H, W, L = image.shape()
    if 0 <= x < W and 0 <= y < H and 0 <= chan < L :
        return image[x,y,chan]
    return 0

def convolution_feature(image: np.ndarray, kernel: np.ndarray, bias: np.ndarray):
    """_summary_
    kernel : M:3/5,N3/5,l,c
    bias : C
    image : (H,W,l)
    output_image : (H,W,c)
    (i,j) \in (H,W) : posisition image de sortie
    L : nb composatne entrée
    C : nb de composante sortie
    $$S_{i,j,c} = \sum_{m,n\in [-1,1], l\in [1,L]} (I_{i+m,j+n, l}\times K_{m,n,l,c}) +bias_c$$
    
    """
    H, W, L = image.shape()
    M,N, L2, C = kernel.shape()
    assert(M == N)
    assert (L == L2)
    assert(bias.shape == (C))
    image_out = np.zeros(H,W,C)
    for i in range(W): 
        for j in range(H):
            for c in range(C):
                for l in range(L):
                    for m in range(-(M//2),M//2+1):
                        for n in range(-(N//2),N//2+1):
                            image_out[i, j, c] += get_valid_pixel(image, i + m, j + n, l) * kernel[m,n,l,c]
                image_out[i, j, c] += bias[c]

    return image_out


def max_pool(image, size : int, stride: int):
    """
    image (H,W, c)
    size = AxA, the window
    stride =  BxB, the step 

    
    image_out : (H/B, W/B, c)
    """
    return image_out
    
def relu(image): 
    """
    image (H,W, c)
    image_out (H,W, c)    
    
    """
    H, W, C = image.shape()
    image_out = np.zeros(H,W,C)
    for i in range(W): 
        for j in range(H):
            for c in range(C):
                image_out[i, j, c] =  max(image_out[i, j, c],0)

    return image_out
