from utils import *

def cnn(image, k_size, tensors):
    """ 
     | image1 24 x 24 x 3 
    convolution "conv1/weights" (k_size, k_size, 3, 64)
       + add biases "conv1/biases" : 64
     | image2 24x24x64
    MaxPool size:3x3  stride:2x2
     | image3 12x12x64
    convolution "conv2/weights" (k_size, k_size, 64, 32)
        + add biases "conv2/biases" :32
     | image4 12x12x32
    MaxPool size:3x3  stride:2x2
     | image5 6x6x32
    convolution "conv3/weights" (k_size, k_size, 32, 20)
        + add biases "conv3/biases" :20
     | image6 6x6x20
    MaxPool size:3x3  stride:2x2
     | image7 3x3x20
    Reshape : 3x3x20 -> 180
     | image7 180
    Fully connected perceptron "local1/weights" 180x10
        + add biases "local1/biases" :10
     | image8 10
    
    """
    
    
    