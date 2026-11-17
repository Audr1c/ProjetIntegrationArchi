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
    return image_out
    
def relu(image): 
    """
    image (H,W, c)
    image_out (H,W, c)    
    
    """

    return image_out
