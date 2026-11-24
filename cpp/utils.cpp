#ifndef UTILS_CPP
#define UTILS_CPP

#include "utils.hpp"



// ============================================================
// ReLU
// ============================================================

template <int N, int W, int I, bool S>
void relu(
    ac_fixed<W, I, S> x[N]
) {
    // En place : les valeurs négatives sont mises à 0
    for (int i = 0; i < N; i++)
        if (x[i] < 0)
            x[i] = 0;
}

// ============================================================
// Get valid pixel
// ============================================================

template <int H, int WD, int W, int I, bool S>
ac_fixed<W, I, S> get_valid_pixel(
    const ac_fixed<W, I, S>* img,
    int row,
    int col
) {
    if (0 <= row && row < H && 0 <= col && col < WD)
        return img[row * WD + col];
    return ac_fixed<W, I, S>(0);   // padding à zéro
}


// ============================================================
// Convolution feature
// ============================================================

template <
    int C_IN, int H, int WD, int C_OUT, int K,
    int W_acc, int I_acc,
    int W_i, int I_i, bool S_i,
    int W_k, int I_k, bool S_k,
    int W_b, int I_b, bool S_b,
    int W_o, int I_o, bool S_o
>
void convolution_feature(
    const ac_fixed<W_i, I_i, S_i> img[C_IN * H * WD],
    const ac_fixed<W_k, I_k, S_k> ker[C_OUT * C_IN * K * K],
    const ac_fixed<W_b, I_b, S_b> bia[C_OUT],
    ac_fixed<W_o, I_o, S_o>       img_o[C_OUT * H * WD]
) {
    // image  : [L][H][W]      kernel : [C][L][M][N]      sortie : [C][H][W]
    // S[c][r][k] = sum_{l,m,n} I[l][r+m-M/2][k+n-N/2] * K[c][l][m][n] + b[c]

    // Accumulateur : imposé (W_acc > 0) ou automatique = produit exact + G bits de garde + biais
    typedef typename ac_fixed<W_i, I_i, S_i>::template rt<W_k, I_k, S_k>::mult mult_t;
    constexpr int G      = 11;
    constexpr int F_auto = AC_MAX(mult_t::width - mult_t::i_width, W_b - I_b);
    constexpr int I_auto = AC_MAX(mult_t::i_width + G, I_b) + 1;
    typedef ac_fixed<(W_acc > 0 ? W_acc : I_auto + F_auto), (W_acc > 0 ? I_acc : I_auto), true> acc_t;

    // chan en externe : les 3 boucles internes lisent K[chan][.][.][.] de façon contiguë
    for (int chan = 0; chan < C_OUT; chan++)
        for (int row = 0; row < H; row++)
            for (int col = 0; col < WD; col++) {
                acc_t acc = 0;
                const int k_base = chan * C_IN * K * K;
                for (int chan_i = 0; chan_i < C_IN; chan_i++)
                    for (int m = 0; m < K; m++)
                        for (int n = 0; n < K; n++)
                            acc += get_valid_pixel<H, WD>(img + chan_i * H * WD, row + m - K / 2, col + n - K / 2)
                                 * ker[k_base + (chan_i * K + m) * K + n];
                acc += bia[chan];
                img_o[(chan * H + row) * WD + col] = acc;  // une seule quantification
            }
}

// ============================================================
// Perceptron
// ============================================================

template <
    int C, int H, int WD, int N,
    int W_acc, int I_acc,
    int W_a, int I_a, bool S_a,
    int W_m, int I_m, bool S_m,
    int W_c, int I_c, bool S_c,
    int W_o, int I_o, bool S_o
>
void m_acc_hwc(
    const ac_fixed<W_a, I_a, S_a> A[C * H * WD],
    const ac_fixed<W_m, I_m, S_m> B[C * H * WD * N],
    const ac_fixed<W_c, I_c, S_c> Cb[N],
    ac_fixed<W_o, I_o, S_o>       S[N]
) {
    // S_j = sum_f A_f * B_{f,j} + C_j     avec f = (row*W + col)*C + chan (ordre HWC)
    typedef typename ac_fixed<W_a, I_a, S_a>::template rt<W_m, I_m, S_m>::mult mult_t;
    constexpr int G      = 8;
    constexpr int F_auto = AC_MAX(mult_t::width - mult_t::i_width, W_c - I_c);
    constexpr int I_auto = AC_MAX(mult_t::i_width + G, I_c) + 1;
    typedef ac_fixed<(W_acc > 0 ? W_acc : I_auto + F_auto), (W_acc > 0 ? I_acc : I_auto), true> acc_t;

    acc_t acc[N];
    for (int j = 0; j < N; j++)
        acc[j] = Cb[j];
    // row, col, chan : f croît de 1 à chaque itération ; B est parcourue ligne par ligne (contiguë)
    for (int row = 0; row < H; row++)
        for (int col = 0; col < WD; col++)
            for (int chan = 0; chan < C; chan++) {
                const int f = (row * WD + col) * C + chan;
                const ac_fixed<W_a, I_a, S_a> a = A[(chan * H + row) * WD + col];
                for (int j = 0; j < N; j++)
                    acc[j] += a * B[f * N + j];
            }

    for (int j = 0; j < N; j++)
        S[j] = acc[j];
}



// ============================================================
// Max Pool
// ============================================================

template <
    int C, int H, int WD,
    int W_i, int I_i, bool S_i,
    int W_o, int I_o, bool S_o
>
void max_pool(
    const ac_fixed<W_i, I_i, S_i> img[C * H * WD],
    ac_fixed<W_o, I_o, S_o>       img_o[C * (H / POOL_STRIDE) * (WD / POOL_STRIDE)]
) {
    constexpr int OH = H / POOL_STRIDE;
    constexpr int OW = WD / POOL_STRIDE;

    for (int chan = 0; chan < C; chan++)
        for (int row = 0; row < OH; row++)
            for (int col = 0; col < OW; col++) {
                const ac_fixed<W_i, I_i, S_i>* plane = img + chan * H * WD;
                // Le pixel (row*stride, col*stride) est toujours dans l'image : bonne valeur initiale
                ac_fixed<W_i, I_i, S_i> max_value = get_valid_pixel<H, WD>(plane, row * POOL_STRIDE, col * POOL_STRIDE);
                for (int m = 0; m < POOL_SIZE; m++)
                    for (int n = 0; n < POOL_SIZE; n++) {
                        // Hors image -> 0, comme en Python (sans effet après ReLU car tout est >= 0)
                        ac_fixed<W_i, I_i, S_i> v =
                            get_valid_pixel<H, WD>(plane, row * POOL_STRIDE + m, col * POOL_STRIDE + n);
                        if (v > max_value)
                            max_value = v;
                    }
                img_o[(chan * OH + row) * OW + col] = max_value;
            }
}

#endif // UTILS_CPP
