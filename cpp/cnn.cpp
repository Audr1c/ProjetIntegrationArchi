#include "cnn.hpp"
#include <ac_channel.h>   // PC : hls/stub/ac_channel.h ; Catapult : le sien


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

// En-tête des ROM, inclus dans chaque bloc avec CNN_ROM_LAYER = n : seules les ROM de la couche n
// y sont déclarées (encadrement généré par hls/gen_coeffs.py)
#if defined(CNN_ROM_RAW) && KS == 5
#define CNN_COEFFS "coeffs_k5_raw.hpp"
#elif defined(CNN_ROM_RAW)
#define CNN_COEFFS "coeffs_k3_raw.hpp"
#elif KS == 5
#define CNN_COEFFS "coeffs_k5.hpp"
#else
#define CNN_COEFFS "coeffs_k3.hpp"
#endif


/*
 * HIÉRARCHIE (AUDIT_HLS E-01) : 4 blocs Catapult (#pragma hls_design), un par couche :
 *     image -> layer1 -> pool1_chan -> layer2 -> pool2_chan -> layer3 -> pool3_chan -> dense -> scores
 * - Chaque bloc a son propre matériel : plus de multiplexeurs de partage entre conv1, conv2 et conv3
 *   (ils étaient sur le chemin critique de cnn.v1 : 12,6 ns pour 10 ns).
 * - Les blocs peuvent travailler en même temps sur des images successives (débit = couche la plus lente)
 *   si les canaux sont en ping-pong (STAGE_REPLICATION 2, hls/cnn.tcl).
 * Règles Catapult (manuel « Handling Hierarchy », §3.4-3.5) respectées ici :
 * - entre deux blocs, un tableau passe par un ac_channel d'une struct ne contenant QU'UN tableau
 *   (fm_chan) -> mémoire partagée ; chaque bloc lit / écrit son canal UNE fois, via une struct locale ;
 * - le top ne contient que des déclarations de canaux static et les appels des blocs ;
 * - chaque bloc est appelé une seule fois ; chaque argument du top ne va qu'à un seul bloc ;
 * - les ROM sont déclarées dans le bloc qui les lit (et non dans le top).
 * Calcul inchangé (mêmes fonctions de utils.cpp, même ordre) : bit-exact, vérifié par make nonreg.
 */

// Tableau transmis d'un bloc au suivant (struct à un seul tableau, exigée par Catapult)
template <class T, int N>
struct fm_chan {
    T data[N];
};
typedef fm_chan<pool1_t, C1 * P1_H * P1_H> pool1_chan_t;   // 12x12x64 = 9216
typedef fm_chan<pool2_t, C2 * P2_H * P2_H> pool2_chan_t;   // 6x6x32   = 1152
typedef fm_chan<pool3_t, FC_IN>            pool3_chan_t;   // 3x3x20   = 180

//=== 1ST CONV + MAX POOL ===//                        24x24x3 -> 24x24x64 -> 12x12x64
#pragma hls_design
void layer1(
    const input_t               image[IN_SIZE],
    ac_channel<pool1_chan_t>&   out
) {
#define CNN_ROM_LAYER 1
#include CNN_COEFFS
#undef CNN_ROM_LAYER
    // static : hors de la pile (36 864 valeurs), sans effet sur le matériel
    static conv1_t image2[C1 * IN_H * IN_WD];
    convolution_feature<IN_C, IN_H, IN_WD, C1, KS, ACC1_W, ACC1_I>(image, ker1, bia1, image2);
    relu<C1 * IN_H * IN_WD>(image2);
    pool1_chan_t pooled;
    max_pool<C1, IN_H, IN_WD>(image2, pooled.data);
    out.write(pooled);
}

//=== 2ND CONV + MAX POOL ===//                        -> 12x12x32 -> 6x6x32
#pragma hls_design
void layer2(
    ac_channel<pool1_chan_t>&   in,
    ac_channel<pool2_chan_t>&   out
) {
#define CNN_ROM_LAYER 2
#include CNN_COEFFS
#undef CNN_ROM_LAYER
    static conv2_t image4[C2 * P1_H * P1_H];
    pool1_chan_t x = in.read();
    convolution_feature<C1, P1_H, P1_H, C2, KS, ACC2_W, ACC2_I>(x.data, ker2, bia2, image4);
    relu<C2 * P1_H * P1_H>(image4);
    pool2_chan_t pooled;
    max_pool<C2, P1_H, P1_H>(image4, pooled.data);
    out.write(pooled);
}

//=== 3RD CONV + MAX POOL ===//                        -> 6x6x20 -> 3x3x20
#pragma hls_design
void layer3(
    ac_channel<pool2_chan_t>&   in,
    ac_channel<pool3_chan_t>&   out
) {
#define CNN_ROM_LAYER 3
#include CNN_COEFFS
#undef CNN_ROM_LAYER
    static conv3_t image6[C3 * P2_H * P2_H];
    pool2_chan_t x = in.read();
    convolution_feature<C2, P2_H, P2_H, C3, KS, ACC3_W, ACC3_I>(x.data, ker3, bia3, image6);
    relu<C3 * P2_H * P2_H>(image6);
    pool3_chan_t pooled;
    max_pool<C3, P2_H, P2_H>(image6, pooled.data);
    out.write(pooled);
}

//=== PERCEPTRON ===//                                 180 -> 10, entrée lue dans l'ordre HWC
#pragma hls_design
void dense(
    ac_channel<pool3_chan_t>&   in,
    out_t                       scores[N_CLASSES]
) {
#define CNN_ROM_LAYER 4
#include CNN_COEFFS
#undef CNN_ROM_LAYER
    pool3_chan_t x = in.read();
    m_acc_hwc<C3, P3_H, P3_H, N_CLASSES, ACCFC_W, ACCFC_I>(x.data, fck, fcb, scores);
}

#pragma hls_design top
void cnn(
    const input_t image[IN_SIZE],
    out_t         scores[N_CLASSES]
) {
    // Canaux entre blocs : static (exigé par Catapult). Sur PC, chaque appel de cnn() écrit puis relit
    // chaque canal une fois : ils sont vides en fin d'appel.
    static ac_channel<pool1_chan_t> pool1_chan;
    static ac_channel<pool2_chan_t> pool2_chan;
    static ac_channel<pool3_chan_t> pool3_chan;
    layer1(image, pool1_chan);
    layer2(pool1_chan, pool2_chan);
    layer3(pool2_chan, pool3_chan);
    dense(pool3_chan, scores);
}
