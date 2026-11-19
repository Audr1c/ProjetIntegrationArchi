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

template <
    int W_i, int I_i, bool S_i,
    int W_o, int I_o, bool S_o
>
imageT<W_o, I_o, S_o> relu(
    const imageT<W_i, I_i, S_i>& img
);


// ============================================================
// Get valid pixel
// ============================================================

template <int W, int I, bool S>
vector<ac_fixed<W, I, S>> get_valid_pixel(
    const imageT<W, I, S>& img,
    int row,
    int col,
    int chan
);


// ============================================================
// Convolution feature
// ============================================================

template <
    int W_i, int I_i, bool S_i,  // Image input
    int W_k, int I_k, bool S_k,  // Kernel
    int W_b, int I_b, bool S_b,  // Bias
    int W_o, int I_o, bool S_o   // Image output
>
imageT<W_o, I_o, S_o> convolution_feature(
    const imageT<W_i, I_i, S_i>& img,
    const kernelT<W_k, I_k, S_k>& ker,
    const biasT<W_b, I_b, S_b>& bia
);


// ============================================================
// Matrix accumulation
// ============================================================

template <
    int W_a, int I_a, bool S_a,  // Input A
    int W_m, int I_m, bool S_m,  // Matrix B
    int W_c, int I_c, bool S_c   // Input C
>
void m_acc(
    const vector<ac_fixed<W_a, I_a, S_a>>& A,
    matrix2<W_m, I_m, S_m>& B,
    const vector<ac_fixed<W_c, I_c, S_c>>& C
);



// ============================================================
// Max Pool
// ============================================================

template <
    int W_i, int I_i, bool S_i,  // Image input
    int W_o, int I_o, bool S_o   // Image output
>
imageT<W_o, I_o, S_o> max_pool(
    const imageT<W_i, I_i, S_i>& img
);








#endif //UTILS_HPP