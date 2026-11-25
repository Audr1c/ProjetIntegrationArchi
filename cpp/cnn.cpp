#include "cnn.hpp"


/*
 * ROM des coefficients ker1, bia1, ..., fck, fcb : trois façons de les compiler.
 *
 * 1) CNN_ROM_RAW (défaut en synthèse, ou -DCNN_ROM_RAW sur PC pour le tester) : coeffs_kK_raw.hpp,
 *    GÉNÉRÉ par hls/gen_coeffs.py dans les formats de config.hpp (#error s'ils ont changé depuis :
 *    relancer make coeffs) : static const RomWord<type> nom[taille] = {entiers}; -> ROM.
 *    Valeurs déjà quantifiées (floor(x * 2^F) replié sur W bits = ac_fixed(double) en AC_TRN/AC_WRAP),
 *    lues par rom_value() (utils.hpp). Un tableau d'entiers natifs se compile ~20x plus vite que
 *    74 000 constructeurs ac_fixed : c'est ce qui faisait durer go analyze 17 min.
 * 2) __SYNTHESIS__ avec -DCNN_ROM_DOUBLE (ancienne méthode, secours) : static const <type> nom[taille]
 *    = {double...}; conversion double -> ac_fixed faite par l'outil (lent).
 * 3) PC (défaut) : coeffs_kK.hpp, les mêmes littéraux dans un tableau double, convertis une seule fois
 *    au premier appel par le constructeur ac_fixed(double) -> valeurs identiques à 1) et 2).
 *    Ne dépend pas des formats : Exploration/ peut changer config.hpp par -D sans rien regénérer.
 * Sous SCVerify, le C++ de référence est compilé sans __SYNTHESIS__ (méthode 3) et le RTL vient de 1) :
 * la comparaison RTL / C++ vérifie donc aussi l'encodage des ROM.
 */
#if defined(__SYNTHESIS__) && !defined(CNN_ROM_DOUBLE) && !defined(CNN_ROM_RAW)
#define CNN_ROM_RAW
#endif

#if defined(CNN_ROM_RAW)

// pas de macros : coeffs_kK_raw.hpp déclare directement les tableaux

#elif defined(__SYNTHESIS__)

#define CNN_ROM_BEGIN(T, name, size)  static const T name[size] = {
#define CNN_ROM_END(T, name, size)    };

#else

template <class T, int N>
struct RomCopy {
    T v[N];
    explicit RomCopy(const double (&d)[N]) {
        for (int i = 0; i < N; i++)
            v[i] = T(d[i]);
    }
};

#define CNN_ROM_BEGIN(T, name, size)  static const double name##_d[size] = {
#define CNN_ROM_END(T, name, size)    };                                            \
                                      static const RomCopy<T, size> name##_rom(name##_d); \
                                      const T* const name = name##_rom.v;

#endif


#pragma hls_design top
void cnn(
    const input_t image[IN_SIZE],
    out_t         scores[N_CLASSES]
) {
    // Coefficients ker1, bia1, ..., fck, fcb : ROM (voir CNN_ROM_BEGIN plus haut).
    // Définis dans la fonction top et non en global (manuel Catapult §6.1.2).
#if defined(CNN_ROM_RAW) && KS == 5
#include "coeffs_k5_raw.hpp"
#elif defined(CNN_ROM_RAW)
#include "coeffs_k3_raw.hpp"
#elif KS == 5
#include "coeffs_k5.hpp"
#else
#include "coeffs_k3.hpp"
#endif

    // Feature maps intermédiaires : mémoires internes.
    // static : hors de la pile (conv1 = 36 864 valeurs), sans effet sur le matériel.
    static conv1_t image2[C1 * IN_H * IN_WD];
    static pool1_t image3[C1 * P1_H * P1_H];
    static conv2_t image4[C2 * P1_H * P1_H];
    static pool2_t image5[C2 * P2_H * P2_H];
    static conv3_t image6[C3 * P2_H * P2_H];
    static pool3_t image7[C3 * P3_H * P3_H];

    //=== 1ST CONV ===//                                  24x24x3 -> 24x24x64
    convolution_feature<IN_C, IN_H, IN_WD, C1, KS, ACC1_W, ACC1_I>(image, ker1, bia1, image2);
    relu<C1 * IN_H * IN_WD>(image2);

    //=== 1ST MAX POOL ===//                              -> 12x12x64
    max_pool<C1, IN_H, IN_WD>(image2, image3);


    //=== 2ND CONV ===//                                  -> 12x12x32
    convolution_feature<C1, P1_H, P1_H, C2, KS, ACC2_W, ACC2_I>(image3, ker2, bia2, image4);
    relu<C2 * P1_H * P1_H>(image4);

    //=== 2ND MAX POOL ===//                              -> 6x6x32
    max_pool<C2, P1_H, P1_H>(image4, image5);


    //=== 3RD CONV ===//                                  -> 6x6x20
    convolution_feature<C2, P2_H, P2_H, C3, KS, ACC3_W, ACC3_I>(image5, ker3, bia3, image6);
    relu<C3 * P2_H * P2_H>(image6);

    //=== 3RD MAX POOL ===//                              -> 3x3x20
    max_pool<C3, P2_H, P2_H>(image6, image7);


    //=== PERCEPTRON ===//                                180 -> 10, entrée lue dans l'ordre HWC
    m_acc_hwc<C3, P3_H, P3_H, N_CLASSES, ACCFC_W, ACCFC_I>(image7, fck, fcb, scores);
}
