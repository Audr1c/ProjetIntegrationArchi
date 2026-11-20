#ifndef UTILS_HPP
#define UTILS_HPP


#include <vector>
#include "../hls/include/ac_fixed.h"

using namespace std;

/*
 * ac_fixed parameters:
 * W: total width in bits
 * I: width of integer part
 * S: true for signed, false for unsigned
 */

// ============================================================
// Data structures
// ============================================================

template <int W, int I, bool S>
struct imageT {
    vector<ac_fixed<W, I, S>> value;
    int width;
    int height;
    int channels;
};

template <int W, int I, bool S>
struct kernelT {
    vector<ac_fixed<W, I, S>> value;
    int M;
    int N;
    int L;
    int C;
};

template <int W, int I, bool S>
struct biasT {
    vector<ac_fixed<W, I, S>> value;
    int C;
};

template <int W, int I, bool S>
struct matrix2 {
    vector<ac_fixed<W, I, S>> value;
    int M;
    int N;
};


// ============================================================
// ReLU
// ============================================================

template <int W, int I, bool S>
void relu(
    imageT<W, I, S>& img   // modifiée en place
);


// ============================================================
// Get valid pixel
// ============================================================

template <int W, int I, bool S>
ac_fixed<W, I, S> get_valid_pixel(
    const imageT<W, I, S>& img,
    int row,
    int col,
    int chan
);


// ============================================================
// Convolution feature
// ============================================================

/*
 * Accumulateur ac_fixed<W_acc, I_acc, true> : W_acc = 0 -> format automatique, sans aucune perte :
 * produit exact + 11 bits de garde (ceil(log2(64*5*5)), pire cas du réseau) + place pour le biais.
 * En AC_WRAP (défaut), les débordements intermédiaires se compensent : I_acc n'a besoin que
 * de couvrir la dynamique du résultat final.
 */
template <
    int W_o, int I_o, bool S_o,          // Image output
    int W_acc = 0, int I_acc = 0,        // Accumulateur (0 = automatique)
    int W_i, int I_i, bool S_i,          // Image input   (déduit)
    int W_k, int I_k, bool S_k,          // Kernel        (déduit)
    int W_b, int I_b, bool S_b           // Bias          (déduit)
>
imageT<W_o, I_o, S_o> convolution_feature(
    const imageT<W_i, I_i, S_i>& img,
    const kernelT<W_k, I_k, S_k>& ker,
    const biasT<W_b, I_b, S_b>& bia
);


// ============================================================
// Matrix accumulation
// ============================================================

// Accumulateur : comme convolution_feature (W_acc = 0 -> automatique, 8 bits de garde = ceil(log2(180)))
template <
    int W_o, int I_o, bool S_o,          // Sortie S
    int W_acc = 0, int I_acc = 0,        // Accumulateur (0 = automatique)
    int W_a, int I_a, bool S_a,          // Input A   (déduit)
    int W_m, int I_m, bool S_m,          // Matrix B  (déduit)
    int W_c, int I_c, bool S_c           // Input C   (déduit)
>
vector<ac_fixed<W_o, I_o, S_o>> m_acc(
    const vector<ac_fixed<W_a, I_a, S_a>>& A,
    const matrix2<W_m, I_m, S_m>& B,
    const vector<ac_fixed<W_c, I_c, S_c>>& C
);



// ============================================================
// Max Pool
// ============================================================

template <
    int W_o, int I_o, bool S_o,   // Image output
    int W_i, int I_i, bool S_i  // Image input
    
>
imageT<W_o, I_o, S_o> max_pool(
    const imageT<W_i, I_i, S_i>& img,
    int size = 3,
    int stride = 2,
    bool centered = false
);








// Templates : les définitions doivent être visibles là où on les instancie
#include "utils.cpp"

#endif //UTILS_HPP