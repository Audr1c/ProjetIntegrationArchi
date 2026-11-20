#ifndef CONFIG_HPP
#define CONFIG_HPP

/*
 * Formats virgule fixe du CNN : ac_fixed<W, I, S>
 *     W : nombre total de bits
 *     I : bits de partie entière (signe compris si signé)
 *
 * Généré par Exploration/explore.py le 2026-11-20 05:07
 * exploration 20261120-041213_k5_t1_s5955 : 88.00 % sur 1000 images (référence 89.00 %, seuil 1.0 pt), noyau 5x5
 *
 * Toutes les valeurs se modifient ici, ou à la compilation sans toucher au code :
 *     cmake -DCMAKE_CXX_FLAGS="-DCONV1_W=12 -DCONV1_I=6" ..
 */

#include "../hls/include/ac_fixed.h"

// image normalisée
#ifndef IN_W
#define IN_W 13
#endif
#ifndef IN_I
#define IN_I 4
#endif

// poids conv1
#ifndef K1_W
#define K1_W 13
#endif
#ifndef K1_I
#define K1_I 3
#endif

// biais conv1
#ifndef B1_W
#define B1_W 12
#endif
#ifndef B1_I
#define B1_I 3
#endif

// accumulateur conv1 (somme des produits + biais)
#ifndef ACC1_W
#define ACC1_W 15
#endif
#ifndef ACC1_I
#define ACC1_I 6
#endif

// sortie conv1 + relu
#ifndef CONV1_W
#define CONV1_W 11
#endif
#ifndef CONV1_I
#define CONV1_I 6
#endif

// sortie max-pool 1
#ifndef POOL1_W
#define POOL1_W 9
#endif
#ifndef POOL1_I
#define POOL1_I 4
#endif

// poids conv2
#ifndef K2_W
#define K2_W 19
#endif
#ifndef K2_I
#define K2_I 1
#endif

// biais conv2
#ifndef B2_W
#define B2_W 13
#endif
#ifndef B2_I
#define B2_I 3
#endif

// accumulateur conv2
#ifndef ACC2_W
#define ACC2_W 19
#endif
#ifndef ACC2_I
#define ACC2_I 8
#endif

// sortie conv2 + relu
#ifndef CONV2_W
#define CONV2_W 8
#endif
#ifndef CONV2_I
#define CONV2_I 8
#endif

// sortie max-pool 2
#ifndef POOL2_W
#define POOL2_W 5
#endif
#ifndef POOL2_I
#define POOL2_I 5
#endif

// poids conv3
#ifndef K3_W
#define K3_W 15
#endif
#ifndef K3_I
#define K3_I 2
#endif

// biais conv3
#ifndef B3_W
#define B3_W 7
#endif
#ifndef B3_I
#define B3_I 2
#endif

// accumulateur conv3
#ifndef ACC3_W
#define ACC3_W 20
#endif
#ifndef ACC3_I
#define ACC3_I 8
#endif

// sortie conv3 + relu
#ifndef CONV3_W
#define CONV3_W 8
#endif
#ifndef CONV3_I
#define CONV3_I 8
#endif

// sortie max-pool 3
#ifndef POOL3_W
#define POOL3_W 6
#endif
#ifndef POOL3_I
#define POOL3_I 6
#endif

// poids perceptron
#ifndef FCK_W
#define FCK_W 5
#endif
#ifndef FCK_I
#define FCK_I -1
#endif

// biais perceptron
#ifndef FCB_W
#define FCB_W 6
#endif
#ifndef FCB_I
#define FCB_I 3
#endif

// accumulateur perceptron
#ifndef ACCFC_W
#define ACCFC_W 11
#endif
#ifndef ACCFC_I
#define ACCFC_I 6
#endif

// scores des 10 classes
#ifndef OUT_W
#define OUT_W 11
#endif
#ifndef OUT_I
#define OUT_I 6
#endif


// ============================================================
// Types utilisés par le reste du code
// ============================================================
typedef ac_fixed<IN_W, IN_I, true> input_t;
typedef ac_fixed<K1_W, K1_I, true> ker1_t;
typedef ac_fixed<B1_W, B1_I, true> bias1_t;
typedef ac_fixed<CONV1_W, CONV1_I, true> conv1_t;
typedef ac_fixed<POOL1_W, POOL1_I, false> pool1_t;
typedef ac_fixed<K2_W, K2_I, true> ker2_t;
typedef ac_fixed<B2_W, B2_I, true> bias2_t;
typedef ac_fixed<CONV2_W, CONV2_I, true> conv2_t;
typedef ac_fixed<POOL2_W, POOL2_I, false> pool2_t;
typedef ac_fixed<K3_W, K3_I, true> ker3_t;
typedef ac_fixed<B3_W, B3_I, true> bias3_t;
typedef ac_fixed<CONV3_W, CONV3_I, true> conv3_t;
typedef ac_fixed<POOL3_W, POOL3_I, false> pool3_t;
typedef ac_fixed<FCK_W, FCK_I, true> fck_t;
typedef ac_fixed<FCB_W, FCB_I, true> fcb_t;
typedef ac_fixed<OUT_W, OUT_I, true> out_t;

#endif // CONFIG_HPP
