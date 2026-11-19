from utils import convolution_feature, relu, max_pool, macc, POOL_TF_SAME


def cnn(image, tensors, pool_mode=POOL_TF_SAME, max_pool_ksize=3, stats=None):
    """
    k_size = 3 or 5
     | image1 24 x 24 x 3
    convolution "conv1/weights" (k_size, k_size, 3, 64)
       + add biases "conv1/biases" : 64
    Relu
     | image2 24x24x64
    MaxPool size:3x3  stride:2x2
     | image3 12x12x64
    convolution "conv2/weights" (k_size, k_size, 64, 32)
        + add biases "conv2/biases" :32
    Relu
     | image4 12x12x32
    MaxPool size:3x3  stride:2x2
     | image5 6x6x32
    convolution "conv3/weights" (k_size, k_size, 32, 20)
        + add biases "conv3/biases" :20
    Relu
     | image6 6x6x20
    MaxPool size:3x3  stride:2x2
     | image7 3x3x20
    Reshape : 3x3x20 -> 180
     | image8 180
    Fully connected perceptron "local3/weights" 180x10
        + add biases "local3/biases" :10
     | image9 10

    pool_mode : POOL_TF_SAME (défaut) ou POOL_CENTERED, voir utils.max_pool
    stats     : amplitude.AmplitudeStats optionnel, cumule la dynamique de chaque étape
    """
    image1 = image
    H, W, L = image1.shape
    assert 24 == W == H and L == 3
    if stats is not None:
        stats.new_image()
        stats.record("input", image1)

    image2 = relu(convolution_feature(
        image1, tensors["conv1/weights"], tensors["conv1/biases"], stats=stats, name="conv1"))

    image3 = max_pool(image2, max_pool_ksize, 2, pool_mode)
    if stats is not None:
        stats.record("conv1/pool", image3)

    image4 = relu(convolution_feature(
        image3, tensors["conv2/weights"], tensors["conv2/biases"], stats=stats, name="conv2"))

    image5 = max_pool(image4, max_pool_ksize, 2, pool_mode)
    if stats is not None:
        stats.record("conv2/pool", image5)

    image6 = relu(convolution_feature(
        image5, tensors["conv3/weights"], tensors["conv3/biases"], stats=stats, name="conv3"))

    image7 = max_pool(image6, max_pool_ksize, 2, pool_mode)
    if stats is not None:
        stats.record("conv3/pool", image7)

    image8 = image7.reshape(180)

    image9 = macc(image8, tensors["local3/weights"], tensors["local3/biases"], stats=stats, name="fc")

    return image9
