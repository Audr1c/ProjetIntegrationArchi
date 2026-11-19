#ifndef EXTRACT_COEFF_HPP
#define EXTRACT_COEFF_HPP

/*
 * Lecture des coefficients du CNN (data/coef/CNN_coeff_KxK.txt)
 * Équivalent C++ de python/extractCoeff.py
 *
 * Format du fichier : une suite de blocs
 *     tensor_name:  conv1/weights
 *     [[[[ ... ]]]]          (tableau numpy imprimé, ordre "row-major")
 *
 * Formes dans le fichier (ordre TensorFlow) :
 *     convX/weights  : (M, N, L, C)
 *     convX/biases   : (C)
 *     local3/weights : (180, 10)
 *     local3/biases  : (10)
 */

#include <map>
#include <string>
#include <vector>
#include <stdexcept>
#include "utils.hpp"

using namespace std;

// Tenseur brut lu dans le fichier (valeurs en double, rangées comme dans le fichier)
struct Tensor {
    vector<double> value;
    vector<int>    shape;
};

// Lit tout le fichier : {nom du tenseur -> tenseur}
map<string, Tensor> parse_tensors(const string& path);

// Récupère un tenseur en vérifiant son nombre de dimensions
const Tensor& get_tensor(const map<string, Tensor>& tensors, const string& name, int ndim);


// ============================================================
// Conversion vers les types ac_fixed du modèle
// ============================================================

// (M, N, L, C) du fichier  ->  [C][L][M][N] (ordre de kernelT)
template <int W, int I, bool S>
kernelT<W, I, S> to_kernel(const Tensor& t) {
    if (t.shape.size() != 4) throw runtime_error("to_kernel : tenseur 4D attendu");
    kernelT<W, I, S> ker;
    ker.M = t.shape[0];
    ker.N = t.shape[1];
    ker.L = t.shape[2];
    ker.C = t.shape[3];
    ker.value.resize(t.value.size());
    for (int m = 0; m < ker.M; m++)
        for (int n = 0; n < ker.N; n++)
            for (int l = 0; l < ker.L; l++)
                for (int c = 0; c < ker.C; c++)
                    ker.value[((c * ker.L + l) * ker.M + m) * ker.N + n] =
                        ac_fixed<W, I, S>(t.value[((m * ker.N + n) * ker.L + l) * ker.C + c]);
    return ker;
}

template <int W, int I, bool S>
biasT<W, I, S> to_bias(const Tensor& t) {
    if (t.shape.size() != 1) throw runtime_error("to_bias : tenseur 1D attendu");
    biasT<W, I, S> b;
    b.C = t.shape[0];
    for (double v : t.value)
        b.value.push_back(ac_fixed<W, I, S>(v));
    return b;
}

// (M, N) du fichier -> matrix2, rangée ligne par ligne : value[k * N + j]
template <int W, int I, bool S>
matrix2<W, I, S> to_matrix(const Tensor& t) {
    if (t.shape.size() != 2) throw runtime_error("to_matrix : tenseur 2D attendu");
    matrix2<W, I, S> mat;
    mat.M = t.shape[0];
    mat.N = t.shape[1];
    for (double v : t.value)
        mat.value.push_back(ac_fixed<W, I, S>(v));
    return mat;
}

template <int W, int I, bool S>
vector<ac_fixed<W, I, S>> to_vector(const Tensor& t) {
    vector<ac_fixed<W, I, S>> vec;
    for (double v : t.value)
        vec.push_back(ac_fixed<W, I, S>(v));
    return vec;
}

#endif // EXTRACT_COEFF_HPP
