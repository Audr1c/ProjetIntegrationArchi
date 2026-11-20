#ifndef UTILS_CPP
#define UTILS_CPP

#include "utils.hpp"



// ============================================================
// ReLU
// ============================================================

template <int W, int I, bool S>
void relu(
    imageT<W, I, S>& img
) {
    // En place : les valeurs négatives sont mises à 0
    for (size_t i = 0; i < img.value.size(); i++)
        if (img.value[i] < 0)
            img.value[i] = 0;
}

// ============================================================
// Get valid pixel
// ============================================================

template <int W, int I, bool S>
ac_fixed<W, I, S> get_valid_pixel(
    const imageT<W, I, S>& img,
    int row,
    int col,
    int chan
) {
    if (0 <= row  && row  < img.height &&
        0 <= col  && col  < img.width  &&
        0 <= chan && chan < img.channels)
        return img.value[(chan * img.height + row) * img.width + col];
    return ac_fixed<W, I, S>(0);   // padding à zéro
}


// ============================================================
// Convolution feature
// ============================================================

template <
    int W_o, int I_o, bool S_o,  // Image output
    int W_acc, int I_acc,        // Accumulateur (0 = automatique)
    int W_i, int I_i, bool S_i,  // Image input
    int W_k, int I_k, bool S_k,  // Kernel
    int W_b, int I_b, bool S_b   // Bias
>
imageT<W_o, I_o, S_o> convolution_feature(
    const imageT<W_i, I_i, S_i>& img,
    const kernelT<W_k, I_k, S_k>& ker,
    const biasT<W_b, I_b, S_b>& bia
) {
    // image  : [L][H][W]      kernel : [C][L][M][N]      sortie : [C][H][W]
    // S[c][r][k] = sum_{l,m,n} I[l][r+m-M/2][k+n-N/2] * K[c][l][m][n] + b[c]

    // Accumulateur : imposé (W_acc > 0) ou automatique = produit exact + G bits de garde + biais
    typedef typename ac_fixed<W_i, I_i, S_i>::template rt<W_k, I_k, S_k>::mult mult_t;
    constexpr int G      = 11;
    constexpr int F_auto = AC_MAX(mult_t::width - mult_t::i_width, W_b - I_b);
    constexpr int I_auto = AC_MAX(mult_t::i_width + G, I_b) + 1;
    typedef ac_fixed<(W_acc > 0 ? W_acc : I_auto + F_auto), (W_acc > 0 ? I_acc : I_auto), true> acc_t;

    imageT<W_o, I_o, S_o> img_o;
    img_o.channels = ker.C;
    img_o.height   = img.height;
    img_o.width    = img.width;
    img_o.value.resize(img_o.channels * img_o.height * img_o.width);

    // chan en externe : les 3 boucles internes lisent K[chan][.][.][.] de façon contiguë
    for (int chan = 0; chan < img_o.channels; chan++)
        for (int row = 0; row < img_o.height; row++)
            for (int col = 0; col < img_o.width; col++) {
                acc_t acc = 0;
                const int k_base = chan * ker.L * ker.M * ker.N;
                for (int chan_i = 0; chan_i < ker.L; chan_i++)
                    for (int m = 0; m < ker.M; m++)
                        for (int n = 0; n < ker.N; n++)
                            acc += get_valid_pixel(img, row + m - ker.M / 2, col + n - ker.N / 2, chan_i)
                                 * ker.value[k_base + (chan_i * ker.M + m) * ker.N + n];
                acc += bia.value[chan];
                img_o.value[(chan * img_o.height + row) * img_o.width + col] = acc;  // une seule quantification
            }
    return img_o;
}

// ============================================================
// Matrix accumulation
// ============================================================

template <
    int W_o, int I_o, bool S_o,  // Sortie S
    int W_acc, int I_acc,        // Accumulateur (0 = automatique)
    int W_a, int I_a, bool S_a,  // Input A
    int W_m, int I_m, bool S_m,  // Matrix B
    int W_c, int I_c, bool S_c   // Input C
>
vector<ac_fixed<W_o, I_o, S_o>> m_acc(
    const vector<ac_fixed<W_a, I_a, S_a>>& A,
    const matrix2<W_m, I_m, S_m>& B,
    const vector<ac_fixed<W_c, I_c, S_c>>& C
) {
    // S_j = sum_k A_k * B_{k,j} + C_j      B : M lignes (= A.size()) x N colonnes (= C.size())
    typedef typename ac_fixed<W_a, I_a, S_a>::template rt<W_m, I_m, S_m>::mult mult_t;
    constexpr int G      = 8;
    constexpr int F_auto = AC_MAX(mult_t::width - mult_t::i_width, W_c - I_c);
    constexpr int I_auto = AC_MAX(mult_t::i_width + G, I_c) + 1;
    typedef ac_fixed<(W_acc > 0 ? W_acc : I_auto + F_auto), (W_acc > 0 ? I_acc : I_auto), true> acc_t;

    // Boucle k externe, j interne : B est parcourue ligne par ligne (contiguë)
    vector<acc_t> acc(B.N);
    for (int j = 0; j < B.N; j++)
        acc[j] = C[j];
    for (int k = 0; k < B.M; k++)
        for (int j = 0; j < B.N; j++)
            acc[j] += A[k] * B.value[k * B.N + j];

    vector<ac_fixed<W_o, I_o, S_o>> S(B.N);
    for (int j = 0; j < B.N; j++)
        S[j] = acc[j];
    return S;
}



// ============================================================
// Max Pool
// ============================================================

template <
    int W_o, int I_o, bool S_o,  // Image output
    int W_i, int I_i, bool S_i   // Image input
>
imageT<W_o, I_o, S_o> max_pool(
    const imageT<W_i, I_i, S_i>& img,
    int size,
    int stride,
    bool centered
) {
    // centered = false : fenêtre [i*stride, i*stride + size - 1]   (TF 'SAME', réseau entraîné ainsi)
    // centered = true  : fenêtre [i*stride - size/2, i*stride + size/2]
    imageT<W_o, I_o, S_o> img_o;
    img_o.channels = img.channels;
    img_o.height   = img.height / stride;
    img_o.width    = img.width  / stride;
    img_o.value.resize(img_o.channels * img_o.height * img_o.width);

    const int off = centered ? -(size / 2) : 0;

    for (int chan = 0; chan < img_o.channels; chan++)
        for (int row = 0; row < img_o.height; row++)
            for (int col = 0; col < img_o.width; col++) {
                // Le pixel (row*stride, col*stride) est toujours dans l'image : bonne valeur initiale
                ac_fixed<W_i, I_i, S_i> max_value = get_valid_pixel(img, row * stride, col * stride, chan);
                for (int m = 0; m < size; m++)
                    for (int n = 0; n < size; n++) {
                        // Hors image -> 0, comme en Python (sans effet après ReLU car tout est >= 0)
                        ac_fixed<W_i, I_i, S_i> v =
                            get_valid_pixel(img, row * stride + m + off, col * stride + n + off, chan);
                        if (v > max_value)
                            max_value = v;
                    }
                img_o.value[(chan * img_o.height + row) * img_o.width + col] = max_value;
            }
    return img_o;
}

#endif // UTILS_CPP
