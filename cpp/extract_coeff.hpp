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
#include "../hls/include/ac_fixed.h"

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
// Conversion vers les tableaux ac_fixed du modèle
// ============================================================

// (M, N, L, C) du fichier  ->  [C][L][M][N] (ordre des noyaux de convolution_feature)
template <int W, int I, bool S>
void to_kernel(const Tensor& t, int C_out, int C_in, int K, ac_fixed<W, I, S>* ker) {
    if (t.shape.size() != 4 || t.shape[0] != K || t.shape[1] != K || t.shape[2] != C_in || t.shape[3] != C_out)
        throw runtime_error("to_kernel : forme inattendue (noyau " + to_string(K) + "x" + to_string(K) +
                            " attendu, recompiler avec -DKS=" + to_string(t.shape.size() == 4 ? t.shape[0] : 0) + " ?)");
    for (int m = 0; m < K; m++)
        for (int n = 0; n < K; n++)
            for (int l = 0; l < C_in; l++)
                for (int c = 0; c < C_out; c++)
                    ker[((c * C_in + l) * K + m) * K + n] =
                        ac_fixed<W, I, S>(t.value[((m * K + n) * C_in + l) * C_out + c]);
}

// Tenseur quelconque recopié dans l'ordre du fichier (biais, matrice FC ligne par ligne : value[k * N + j])
template <int W, int I, bool S>
void to_array(const Tensor& t, int size, ac_fixed<W, I, S>* out) {
    if ((int)t.value.size() != size)
        throw runtime_error("to_array : " + to_string(size) + " valeurs attendues, " +
                            to_string(t.value.size()) + " lues");
    for (int i = 0; i < size; i++)
        out[i] = ac_fixed<W, I, S>(t.value[i]);
}

#endif // EXTRACT_COEFF_HPP
