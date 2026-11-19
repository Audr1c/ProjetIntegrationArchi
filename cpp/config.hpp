#ifndef CONFIG_HPP
#define CONFIG_HPP

/*
 * Formats virgule fixe du CNN : ac_fixed<W, I, S>
 *     W : nombre total de bits
 *     I : bits de partie entière (signe compris si signé) -> |x| < 2^(I-1) en signé, < 2^I en non signé
 *
 * Toutes les valeurs se modifient ici, ou à la compilation sans toucher au code :
 *     cmake -DCMAKE_CXX_FLAGS="-DCONV1_W=12 -DCONV1_I=6" ..
 *
 * Dynamiques mesurées en Python : voir Results/amplitude_*.md
 */

#include "../hls/include/ac_fixed.h"

// ---------------- Image d'entrée (normalisée, max mesuré 3.5) ----------------
#ifndef IN_W
#define IN_W 16
#endif
#ifndef IN_I
#define IN_I 4
#endif

// ---------------- Couche 1 : conv 3 -> 64 ----------------
#ifndef K1_W                // poids (max mesuré 2.6)
#define K1_W 16
#endif
#ifndef K1_I
#define K1_I 3
#endif
#ifndef B1_W                // biais (max mesuré 3.5)
#define B1_W 16
#endif
#ifndef B1_I
#define B1_I 4
#endif
#ifndef CONV1_W             // sortie conv + relu (max mesuré 15)
#define CONV1_W 16
#endif
#ifndef CONV1_I
#define CONV1_I 8
#endif
#ifndef POOL1_W             // sortie max-pool, non signée (>= 0 après relu)
#define POOL1_W 16
#endif
#ifndef POOL1_I
#define POOL1_I 8
#endif

// ---------------- Couche 2 : conv 64 -> 32 ----------------
#ifndef K2_W                // poids (max mesuré 0.89)
#define K2_W 16
#endif
#ifndef K2_I
#define K2_I 3
#endif
#ifndef B2_W
#define B2_W 16
#endif
#ifndef B2_I
#define B2_I 4
#endif
#ifndef CONV2_W             // (max mesuré 113)
#define CONV2_W 16
#endif
#ifndef CONV2_I
#define CONV2_I 8
#endif
#ifndef POOL2_W
#define POOL2_W 16
#endif
#ifndef POOL2_I
#define POOL2_I 8
#endif

// ---------------- Couche 3 : conv 32 -> 20 ----------------
#ifndef K3_W                // poids (max mesuré 1.08)
#define K3_W 16
#endif
#ifndef K3_I
#define K3_I 3
#endif
#ifndef B3_W
#define B3_W 16
#endif
#ifndef B3_I
#define B3_I 4
#endif
#ifndef CONV3_W
#define CONV3_W 16
#endif
#ifndef CONV3_I
#define CONV3_I 8
#endif
#ifndef POOL3_W
#define POOL3_W 16
#endif
#ifndef POOL3_I
#define POOL3_I 8
#endif

// ---------------- Perceptron : 180 -> 10 ----------------
#ifndef FCK_W               // poids (max mesuré 0.18)
#define FCK_W 16
#endif
#ifndef FCK_I
#define FCK_I 1
#endif
#ifndef FCB_W               // biais (max mesuré 2.7)
#define FCB_W 16
#endif
#ifndef FCB_I
#define FCB_I 3
#endif
#ifndef OUT_W               // scores des 10 classes
#define OUT_W 16
#endif
#ifndef OUT_I
#define OUT_I 8
#endif


// ============================================================
// Types utilisés par le reste du code
// ============================================================
typedef ac_fixed<IN_W,    IN_I,    true>  input_t;

typedef ac_fixed<K1_W,    K1_I,    true>  ker1_t;
typedef ac_fixed<B1_W,    B1_I,    true>  bias1_t;
typedef ac_fixed<CONV1_W, CONV1_I, true>  conv1_t;
typedef ac_fixed<POOL1_W, POOL1_I, false> pool1_t;

typedef ac_fixed<K2_W,    K2_I,    true>  ker2_t;
typedef ac_fixed<B2_W,    B2_I,    true>  bias2_t;
typedef ac_fixed<CONV2_W, CONV2_I, true>  conv2_t;
typedef ac_fixed<POOL2_W, POOL2_I, false> pool2_t;

typedef ac_fixed<K3_W,    K3_I,    true>  ker3_t;
typedef ac_fixed<B3_W,    B3_I,    true>  bias3_t;
typedef ac_fixed<CONV3_W, CONV3_I, true>  conv3_t;
typedef ac_fixed<POOL3_W, POOL3_I, false> pool3_t;

typedef ac_fixed<FCK_W,   FCK_I,   true>  fck_t;
typedef ac_fixed<FCB_W,   FCB_I,   true>  fcb_t;
typedef ac_fixed<OUT_W,   OUT_I,   true>  out_t;

#endif // CONFIG_HPP
