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
// Matrix accumulation
// ============================================================

template <
    int M, int N,
    int W_acc, int I_acc,
    int W_a, int I_a, bool S_a,
    int W_m, int I_m, bool S_m,
    int W_c, int I_c, bool S_c,
    int W_o, int I_o, bool S_o
>
void m_acc(
    const ac_fixed<W_a, I_a, S_a> A[M],
    const ac_fixed<W_m, I_m, S_m> B[M * N],
    const ac_fixed<W_c, I_c, S_c> C[N],
    ac_fixed<W_o, I_o, S_o>       S[N]
) {
    // S_j = sum_k A_k * B_{k,j} + C_j
    typedef typename ac_fixed<W_a, I_a, S_a>::template rt<W_m, I_m, S_m>::mult mult_t;
    constexpr int G      = 8;
    constexpr int F_auto = AC_MAX(mult_t::width - mult_t::i_width, W_c - I_c);
    constexpr int I_auto = AC_MAX(mult_t::i_width + G, I_c) + 1;
    typedef ac_fixed<(W_acc > 0 ? W_acc : I_auto + F_auto), (W_acc > 0 ? I_acc : I_auto), true> acc_t;

    // Boucle k externe, j interne : B est parcourue ligne par ligne (contiguë)
    acc_t acc[N];
    for (int j = 0; j < N; j++)
        acc[j] = C[j];
    for (int k = 0; k < M; k++)
        for (int j = 0; j < N; j++)
            acc[j] += A[k] * B[k * N + j];

    for (int j = 0; j < N; j++)
        S[j] = acc[j];
}



// ============================================================
// Max Pool
// ============================================================

template <
    int C, int H, int WD,
    int OH, int OW,
    int W_i, int I_i, bool S_i,
    int W_o, int I_o, bool S_o
>
void max_pool(
    const ac_fixed<W_i, I_i, S_i> img[C * H * WD],
    ac_fixed<W_o, I_o, S_o>       img_o[C * OH * OW],
    int size,
    int stride,
    bool centered
) {
    // centered = false : fenêtre [i*stride, i*stride + size - 1]   (TF 'SAME', réseau entraîné ainsi)
    // centered = true  : fenêtre [i*stride - size/2, i*stride + size/2]
    const int off = centered ? -(size / 2) : 0;

    for (int chan = 0; chan < C; chan++)
        for (int row = 0; row < OH; row++)
            for (int col = 0; col < OW; col++) {
                const ac_fixed<W_i, I_i, S_i>* plane = img + chan * H * WD;
                // Le pixel (row*stride, col*stride) est toujours dans l'image : bonne valeur initiale
                ac_fixed<W_i, I_i, S_i> max_value = get_valid_pixel<H, WD>(plane, row * stride, col * stride);
                for (int m = 0; m < size; m++)
                    for (int n = 0; n < size; n++) {
                        // Hors image -> 0, comme en Python (sans effet après ReLU car tout est >= 0)
                        ac_fixed<W_i, I_i, S_i> v =
                            get_valid_pixel<H, WD>(plane, row * stride + m + off, col * stride + n + off);
                        if (v > max_value)
                            max_value = v;
                    }
                img_o[(chan * OH + row) * OW + col] = max_value;
            }
}

#endif // UTILS_CPP
