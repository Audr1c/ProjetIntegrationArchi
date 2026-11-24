#include "cnn.hpp"


// Aplatissement avant le perceptron.
// L'image est rangée en [C][H][W] mais les poids "local3/weights" ont été appris
// sur reshape(180) d'une image (H, W, C) : on aplatit donc dans l'ordre HWC.
template <int C, int H, int WD, int W, int I, bool S>
static void flatten_hwc(const ac_fixed<W, I, S> img[C * H * WD], ac_fixed<W, I, S> out[C * H * WD]) {
    for (int chan = 0; chan < C; chan++)
        for (int row = 0; row < H; row++)
            for (int col = 0; col < WD; col++)
                out[(row * WD + col) * C + chan] = img[(chan * H + row) * WD + col];
}

#pragma hls_design top
void cnn(
    const input_t image[IN_SIZE],
    const ker1_t  ker1[K1_SIZE],  const bias1_t bia1[C1],
    const ker2_t  ker2[K2_SIZE],  const bias2_t bia2[C2],
    const ker3_t  ker3[K3_SIZE],  const bias3_t bia3[C3],
    const fck_t   fck[FCK_SIZE],  const fcb_t   fcb[N_CLASSES],
    out_t         scores[N_CLASSES]
) {
    // Feature maps intermédiaires : mémoires internes.
    // static : hors de la pile (conv1 = 36 864 valeurs), sans effet sur le matériel.
    static conv1_t image2[C1 * IN_H * IN_WD];
    static pool1_t image3[C1 * P1_H * P1_H];
    static conv2_t image4[C2 * P1_H * P1_H];
    static pool2_t image5[C2 * P2_H * P2_H];
    static conv3_t image6[C3 * P2_H * P2_H];
    static pool3_t image7[C3 * P3_H * P3_H];
    static pool3_t image8[FC_IN];

    //=== 1ST CONV ===//                                  24x24x3 -> 24x24x64
    convolution_feature<IN_C, IN_H, IN_WD, C1, KS, ACC1_W, ACC1_I>(image, ker1, bia1, image2);
    relu<C1 * IN_H * IN_WD>(image2);

    //=== 1ST MAX POOL ===//                              -> 12x12x64
    max_pool<C1, IN_H, IN_WD, P1_H, P1_H>(image2, image3);


    //=== 2ND CONV ===//                                  -> 12x12x32
    convolution_feature<C1, P1_H, P1_H, C2, KS, ACC2_W, ACC2_I>(image3, ker2, bia2, image4);
    relu<C2 * P1_H * P1_H>(image4);

    //=== 2ND MAX POOL ===//                              -> 6x6x32
    max_pool<C2, P1_H, P1_H, P2_H, P2_H>(image4, image5);


    //=== 3RD CONV ===//                                  -> 6x6x20
    convolution_feature<C2, P2_H, P2_H, C3, KS, ACC3_W, ACC3_I>(image5, ker3, bia3, image6);
    relu<C3 * P2_H * P2_H>(image6);

    //=== 3RD MAX POOL ===//                              -> 3x3x20
    max_pool<C3, P2_H, P2_H, P3_H, P3_H>(image6, image7);


    //=== PERCEPTRON ===//                                180 -> 10
    flatten_hwc<C3, P3_H, P3_H>(image7, image8);

    m_acc<FC_IN, N_CLASSES, ACCFC_W, ACCFC_I>(image8, fck, fcb, scores);
}
