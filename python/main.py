import os

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

from read_image import load_batch, load_label_names, DATA_DIR
from extractCoeff import parse_tensors, COEF_DIR
from cnn import cnn
from cnn_fast import cnn_fast
from utils import POOL_TF_SAME, POOL_CENTERED
from amplitude import AmplitudeStats

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Results")


def main() :
    # get tensors :
    label_names = load_label_names(DATA_DIR)

    
    
    
    # counteurs 
    works, failed, total, cumul_error, predection_error = 0, 0, 0, 0, 0
    
    # Configuration
    slow = True
    affichage, printing = False, False
    
    max_count = 10
    k_size = 5
    max_pool_ksize = 5
    pool_mode = POOL_TF_SAME  # POOL_TF_SAME | POOL_CENTERED
    
    tensors = parse_tensors(os.path.join(
        COEF_DIR, f"CNN_coeff_{k_size}x{k_size}.txt"))
    images, labels = load_batch(os.path.join(
        DATA_DIR, "data_batch_1.bin"), apply_normalize=True)
    
    # Dynamique de chaque étape, cumulée sur toutes les images (-> ac_fixed)
    stats = AmplitudeStats()
    stats.record_coefficients(tensors)
    
    for img, true_label in tqdm(zip(images, labels)) :
        # affiche image:
        if affichage:
            plt.imshow(img)
        
        # Calculte results
        # Stats prises sur cnn (boucles) si slow, sinon sur cnn_fast (mêmes valeurs)
        label_fast = cnn_fast(img, tensors, pool_mode=pool_mode, max_pool_ksize=max_pool_ksize,
                              stats=None if slow else stats)
        if slow:
            label = cnn(img, tensors, pool_mode=pool_mode,
                        max_pool_ksize=max_pool_ksize, stats=stats)
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
    
    report = os.path.join(RESULTS_DIR,
        f"amplitude_{k_size}x{k_size}_pool{max_pool_ksize}_{pool_mode}_{total}img.md")
    stats.save_report(report, config={
        "noyau": f"{k_size}x{k_size}",
        "max-pool": f"{max_pool_ksize}x{max_pool_ksize}, mode {pool_mode}",
        "modèle mesuré": "cnn (boucles)" if slow else "cnn_fast",
        "précision": f"{works/total*100:.2f}%",
    })
    print(f"Dynamique des valeurs -> {os.path.relpath(report)}")
        
        
        
        
        

if __name__ == "__main__":
    main()