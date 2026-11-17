from read_image import *
from extractCoeff import *
from utils import *
from cnn import *
from tqdm import *
import numpy as np
import matplotlib.pyplot as plt
import os


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