import numpy as np

def convolution_feature(image, kernel, bias):
    """_summary_
    kernel : 3/5,3/5,l,c
    bias : C
    image : (H,W,l)
    output_image : (H,W,c)
    (i,j) \in (H,W) : posisition image de sortie
    L : nb composatne entrée
    C : nb de composante sortie
    $$S_{i,j,c} = \sum_{m,n\in [-1,1], l\in [1,L]} (I_{i+m,j+n, l}\times K_{m,n,l,c}) +bias_c$$
    
    """
    

    return image_out


def max_pool(image, size : int, stride: int):
    """
    image (H,W, c)
    size = AxA, the window
    stride =  BxB, the step 

    
    image_out : (H/B, W/B, c)
    """

    H_in, W_in, channels = image.shape
    H_out, W_out = H_in//stride, W_in//stride
    image_out = np.zeros((H_out, W_out, channels))

    for c in range(channels):

        for i in range(H_out):
            for j in range(W_out):

                max_value = -float('inf')

                for m in range( -(size//stride), size//stride + 1 ):
                    for n in range( -(size//stride), size//stride + 1 ):
                        current_value = get_valid_pixel(image, i*stride+m, j*stride+n, c)
                        if current_value > max_value:
                            max_value = current_value
                
                image_out[i,j,c] = max_value


    return image_out


    
def relu(image): 
    """
    image (H,W, c)
    image_out (H,W, c)    
    
    """

    return image_out
