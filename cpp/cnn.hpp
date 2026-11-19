#ifndef CNN_HPP
#define CNN_HPP

#include <vector>
#include "config.hpp"
#include "utils.hpp"

using namespace std;

/*
 * CNN CIFAR-10 complet (voir python/cnn.py)
 *     24x24x3 -conv1+relu-> 24x24x64 -pool 3x3/2-> 12x12x64
 *             -conv2+relu-> 12x12x32 -pool 3x3/2-> 6x6x32
 *             -conv3+relu-> 6x6x20   -pool 3x3/2-> 3x3x20
 *             -flatten(HWC)-> 180 -perceptron-> 10
 *
 * Noyau des convolutions : 3x3 ou 5x5 (lu dans les coefficients).
 * Formats virgule fixe : config.hpp
 */

// Coefficients du réseau, dans les formats de config.hpp
struct CnnCoeffs {
    kernelT<K1_W, K1_I, true>   ker1;
    biasT  <B1_W, B1_I, true>   bia1;
    kernelT<K2_W, K2_I, true>   ker2;
    biasT  <B2_W, B2_I, true>   bia2;
    kernelT<K3_W, K3_I, true>   ker3;
    biasT  <B3_W, B3_I, true>   bia3;
    matrix2<FCK_W, FCK_I, true> fc_k;   // 180 x 10
    vector<fcb_t>               fc_b;   // 10
};

// Scores des 10 classes
vector<out_t> cnn(const imageT<IN_W, IN_I, true>& image, const CnnCoeffs& coef);

#endif // CNN_HPP
