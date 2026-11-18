import os

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

from read_image import load_batch, load_label_names, DATA_DIR
from extractCoeff import parse_tensors, COEF_DIR
from cnn import cnn
from cnn_fast import cnn_fast
from utils import POOL_TF_SAME, POOL_CENTERED


def main() :
    # get tensors :
    label_names = load_label_names(DATA_DIR)

    
    
    
    # counteurs 
    works, failed, total, cumul_error, predection_error = 0, 0, 0, 0, 0
    
    # Configuration
    slow = False
    affichage, printing = False, False
    
    max_count = 0
    k_size = 5
    max_pool_ksize = 5
    pool_mode = POOL_TF_SAME  # POOL_TF_SAME | POOL_CENTERED
    
    tensors = parse_tensors(os.path.join(
        COEF_DIR, f"CNN_coeff_{k_size}x{k_size}.txt"))
    images, labels = load_batch(os.path.join(
        DATA_DIR, "data_batch_1.bin"), apply_normalize=True)
    
    for img, true_label in tqdm(zip(images, labels)) :
        # affiche image:
        if affichage:
            plt.imshow(img)
        
        # Calculte results
        label_fast = cnn_fast(img, tensors,pool_mode=pool_mode, max_pool_ksize=max_pool_ksize)
        if slow:
            label = cnn(img, tensors, pool_mode=pool_mode,
                        max_pool_ksize=max_pool_ksize)
            cumul_error += np.sum(np.absolute(label - label_fast))
        
        total += 1
        
        
        if affichage:
            plt.show()
        
        # Verifications
        if (true_label == label_fast.argmax()):
            if printing : print(f"✓ Correct Lablel : {label_names[label_fast.argmax()]}")
            works += 1
            
        else :
            if printing : print(f"✓ NOPE      Got : {label_names[label_fast.argmax()]}, but was : {label_names[true_label]}")
            failed += 1
        
        if (slow and label_fast.argmax() != label.argmax()):
            predection_error += 1
            
        # Break early
        if total >= max_count and max_count > 0:
            break
    
    
    print("##### finished ######")
    print(f"Resulsts for a {k_size}x{k_size} kernel")
    print(f"size of maxpool : {max_pool_ksize}x{max_pool_ksize} in mode :{pool_mode}")
    print(f"Got an accuracy of {works/total*100:.2f}%")
    if slow: print(f"Got an accumulating error of {cumul_error} and predediction eror : {predection_error} !")
        
        
        
        
        

if __name__ == "__main__":
    main()