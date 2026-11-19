#include "cnn.hpp"


// Aplatissement avant le perceptron.
// L'image est rangée en [C][H][W] mais les poids "local3/weights" ont été appris
// sur reshape(180) d'une image (H, W, C) : on aplatit donc dans l'ordre HWC.
template <int W, int I, bool S>
static vector<ac_fixed<W, I, S>> flatten_hwc(const imageT<W, I, S>& img) {
    vector<ac_fixed<W, I, S>> out(img.value.size());
    for (int chan = 0; chan < img.channels; chan++)
        for (int row = 0; row < img.height; row++)
            for (int col = 0; col < img.width; col++)
                out[(row * img.width + col) * img.channels + chan] =
                    img.value[(chan * img.height + row) * img.width + col];
    return out;
}


vector<out_t> cnn(const imageT<IN_W, IN_I, true>& image1, const CnnCoeffs& coef) {

    //=== 1ST CONV ===//                                  24x24x3 -> 24x24x64
    imageT<CONV1_W, CONV1_I, true> image2;
    image2 = convolution_feature<CONV1_W, CONV1_I, true>(image1, coef.ker1, coef.bia1);
    relu(image2);

    //=== 1ST MAX POOL ===//                              -> 12x12x64
    imageT<POOL1_W, POOL1_I, false> image3;
    image3 = max_pool<POOL1_W, POOL1_I, false>(image2);


    //=== 2ND CONV ===//                                  -> 12x12x32
    imageT<CONV2_W, CONV2_I, true> image4;
    image4 = convolution_feature<CONV2_W, CONV2_I, true>(image3, coef.ker2, coef.bia2);
    relu(image4);

    //=== 2ND MAX POOL ===//                              -> 6x6x32
    imageT<POOL2_W, POOL2_I, false> image5;
    image5 = max_pool<POOL2_W, POOL2_I, false>(image4);


    //=== 3RD CONV ===//                                  -> 6x6x20
    imageT<CONV3_W, CONV3_I, true> image6;
    image6 = convolution_feature<CONV3_W, CONV3_I, true>(image5, coef.ker3, coef.bia3);
    relu(image6);

    //=== 3RD MAX POOL ===//                              -> 3x3x20
    imageT<POOL3_W, POOL3_I, false> image7;
    image7 = max_pool<POOL3_W, POOL3_I, false>(image6);


    //=== PERCEPTRON ===//                                180 -> 10
    vector<pool3_t> image8 = flatten_hwc(image7);

    return m_acc<OUT_W, OUT_I, true>(image8, coef.fc_k, coef.fc_b);
}
