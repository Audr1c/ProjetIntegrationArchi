#ifndef UTILS_HPP
#define UTILS_HPP

#include "../hls/include/ac_fixed.h"

/*
 * Briques du CNN, écrites pour être synthétisables par Catapult (voir hls/AUDIT_HLS.md) :
 *   - tableaux C de taille fixe, pas de std::vector ni d'allocation dynamique    (A-02)
 *   - dimensions en paramètres template -> bornes de boucles constantes          (A-03, B-01)
 *   - résultats écrits dans un tableau passé en paramètre, pas de retour         (A-04)
 *
 * Rangement des données :
 *   feature map : [C][H][W]           -> x[(c*H + r)*W + k]
 *   noyau       : [C_out][C_in][K][K] -> ker[((co*C_in + ci)*K + m)*K + n]
 *   matrice FC  : [M][N] ligne par ligne -> mat[k*N + j]
 *
 * ac_fixed parameters:
 * W: total width in bits
 * I: width of integer part
 * S: true for signed, false for unsigned
 */


// ============================================================
// ReLU (en place)
// ============================================================

template <int N, int W, int I, bool S>
void relu(
    ac_fixed<W, I, S> x[N]
);


// ============================================================
// Get valid pixel (padding à zéro)
// ============================================================

template <int H, int WD, int W, int I, bool S>
ac_fixed<W, I, S> get_valid_pixel(
    const ac_fixed<W, I, S>* img,       // un plan [H][WD]
    int row,
    int col
);


// ============================================================
// Convolution feature (« SAME », padding à zéro)
// ============================================================

/*
 * Accumulateur ac_fixed<W_acc, I_acc, true> : W_acc = 0 -> format automatique, sans aucune perte :
 * produit exact + 11 bits de garde (ceil(log2(64*5*5)), pire cas du réseau) + place pour le biais.
 * En AC_WRAP (défaut), les débordements intermédiaires se compensent : I_acc n'a besoin que
 * de couvrir la dynamique du résultat final.
 */
template <
    int C_IN, int H, int WD, int C_OUT, int K,  // Dimensions (explicites)
    int W_acc, int I_acc,                       // Accumulateur (0 = automatique)
    int W_i, int I_i, bool S_i,                 // Image input   (déduit)
    int W_k, int I_k, bool S_k,                 // Kernel        (déduit)
    int W_b, int I_b, bool S_b,                 // Bias          (déduit)
    int W_o, int I_o, bool S_o                  // Image output  (déduit)
>
void convolution_feature(
    const ac_fixed<W_i, I_i, S_i> img[C_IN * H * WD],
    const ac_fixed<W_k, I_k, S_k> ker[C_OUT * C_IN * K * K],
    const ac_fixed<W_b, I_b, S_b> bia[C_OUT],
    ac_fixed<W_o, I_o, S_o>       img_o[C_OUT * H * WD]
);


// ============================================================
// Matrix accumulation : S = A x B + C
// ============================================================

// Accumulateur : comme convolution_feature (W_acc = 0 -> automatique, 8 bits de garde = ceil(log2(180)))
template <
    int M, int N,                       // B : M lignes (= taille de A) x N colonnes (= taille de C)
    int W_acc, int I_acc,               // Accumulateur (0 = automatique)
    int W_a, int I_a, bool S_a,         // Input A   (déduit)
    int W_m, int I_m, bool S_m,         // Matrix B  (déduit)
    int W_c, int I_c, bool S_c,         // Input C   (déduit)
    int W_o, int I_o, bool S_o          // Sortie S  (déduit)
>
void m_acc(
    const ac_fixed<W_a, I_a, S_a> A[M],
    const ac_fixed<W_m, I_m, S_m> B[M * N],
    const ac_fixed<W_c, I_c, S_c> C[N],
    ac_fixed<W_o, I_o, S_o>       S[N]
);


// ============================================================
// Max Pool
// ============================================================

template <
    int C, int H, int WD,               // Image input (explicites)
    int OH, int OW,                     // Image output (explicites)
    int W_i, int I_i, bool S_i,         // Image input  (déduit)
    int W_o, int I_o, bool S_o          // Image output (déduit)
>
void max_pool(
    const ac_fixed<W_i, I_i, S_i> img[C * H * WD],
    ac_fixed<W_o, I_o, S_o>       img_o[C * OH * OW],
    int size = 3,
    int stride = 2,
    bool centered = false
);



// Templates : les définitions doivent être visibles là où on les instancie
#include "utils.cpp"

#endif //UTILS_HPP
