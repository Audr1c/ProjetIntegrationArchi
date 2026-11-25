#ifndef UTILS_HPP
#define UTILS_HPP

#include <ac_fixed.h>          // voir config.hpp (C-04)

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

/*
 * Coefficients en ROM : deux représentations, lues par rom_value() (voir cnn.cpp et hls/gen_coeffs.py).
 *   ac_fixed<W, I, S>  : PC (tableaux double convertis au premier appel) ; rom_value = identité.
 *   RomWord<T>         : synthèse (CNN_ROM_RAW) : motif binaire de l'ac_fixed signé T, déjà quantifié,
 *                        rangé dans un entier C natif. Agrégat sans constructeur : initialiser 74 000
 *                        objets ac_fixed coûte ~17 min à go analyze (et ~7 s à g++), un tableau
 *                        d'entiers ~20x moins. rom_value recopie les bits (set_slc) : aucun matériel.
 */
template <bool LE8, bool LE16> struct rom_int_sel             { typedef int         type; };
template <bool LE16>           struct rom_int_sel<true, LE16> { typedef signed char type; };
template <>                    struct rom_int_sel<false, true> { typedef short      type; };

template <class T>
struct RomWord {
    static_assert(T::sign && T::width <= 32, "RomWord : format signe de 32 bits au plus");
    typename rom_int_sel<(T::width <= 8), (T::width <= 16)>::type v;
};

template <class T> struct rom_type              { typedef T type; };   // type ac_fixed lu
template <class T> struct rom_type<RomWord<T> > { typedef T type; };

template <int W, int I, bool S>
inline ac_fixed<W, I, S> rom_value(const ac_fixed<W, I, S>& x) { return x; }

template <class T>
inline T rom_value(const RomWord<T>& r) {
    T x;
    x.set_slc(0, ac_int<T::width, true>(r.v));
    return x;
}



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
    class TK, class TB,                         // Kernel, bias : ac_fixed ou RomWord<ac_fixed> (déduits)
    int W_o, int I_o, bool S_o                  // Image output  (déduit)
>
void convolution_feature(
    const ac_fixed<W_i, I_i, S_i> img[C_IN * H * WD],
    const TK                      ker[C_OUT * C_IN * K * K],
    const TB                      bia[C_OUT],
    ac_fixed<W_o, I_o, S_o>       img_o[C_OUT * H * WD]
);


// ============================================================
// Perceptron : S = flatten_HWC(A) x B + C
// ============================================================

/*
 * A est une feature map rangée [C][H][W], mais les poids du perceptron ont été appris sur
 * reshape(180) d'une image (H, W, C) : A est lue directement dans l'ordre HWC (pas de copie),
 * indice aplati f = (row*W + col)*C + chan, croissant comme dans l'ancien flatten_hwc
 * -> même ordre d'accumulation, résultat identique même avec un accumulateur tronqué.
 * Accumulateur : comme convolution_feature (W_acc = 0 -> automatique, 8 bits de garde = ceil(log2(180)))
 */
template <
    int C, int H, int WD, int N,        // A : [C][H][W] ; B : (C*H*W) lignes x N colonnes ; C, S : N
    int W_acc, int I_acc,               // Accumulateur (0 = automatique)
    int W_a, int I_a, bool S_a,         // Input A   (déduit)
    class TM, class TC,                 // Matrix B, input C : ac_fixed ou RomWord<ac_fixed> (déduits)
    int W_o, int I_o, bool S_o          // Sortie S  (déduit)
>
void m_acc_hwc(
    const ac_fixed<W_a, I_a, S_a> A[C * H * WD],
    const TM                      B[C * H * WD * N],
    const TC                      Cb[N],
    ac_fixed<W_o, I_o, S_o>       S[N]
);


// ============================================================
// Max Pool 3x3, pas de 2, mode TF 'SAME'
// ============================================================

// Fenêtre [i*2, i*2 + 2], tronquée au bord (padding à 0) : c'est ainsi que le réseau a été appris.
#define POOL_SIZE   3
#define POOL_STRIDE 2

template <
    int C, int H, int WD,               // Image input (explicites) ; sortie [C][H/2][W/2]
    int W_i, int I_i, bool S_i,         // Image input  (déduit)
    int W_o, int I_o, bool S_o          // Image output (déduit)
>
void max_pool(
    const ac_fixed<W_i, I_i, S_i> img[C * H * WD],
    ac_fixed<W_o, I_o, S_o>       img_o[C * (H / POOL_STRIDE) * (WD / POOL_STRIDE)]
);



// Templates : les définitions doivent être visibles là où on les instancie
#include "utils.cpp"

#endif //UTILS_HPP
