import os

import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

from read_image import load_batch, load_label_names, DATA_DIR
from extractCoeff import parse_tensors, COEF_DIR
from cnn import cnn


def main() :
    # get tensors :
    label_names = load_label_names(DATA_DIR)

    
    tensors = parse_tensors(os.path.join(COEF_DIR, "CNN_coeff_3x3.txt"))
    images, labels = load_batch(os.path.join(DATA_DIR, "data_batch_1.bin"), apply_normalize=True)
    
    for img, true_label in tqdm(zip(images, labels)) :
        # affiche image :
        plt.imshow(img)
        
        plt.show()
        label = cnn(img, tensors)
        print(label)
        ind = list(label).index(max(label))
        print("true label : ", label_names[true_label], " VS we got:" , label_names[ind])
        if (true_label == ind) :
            print("Youppi") 
        else :
            print(" OHhh NONNN")

        
        
        
        

if __name__ == "__main__":
    main()