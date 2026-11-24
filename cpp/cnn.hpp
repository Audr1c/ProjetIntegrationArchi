#ifndef CNN_HPP
#define CNN_HPP

#include "config.hpp"
#include "utils.hpp"

/*
 * CNN CIFAR-10 complet (voir python/cnn.py)
 *     24x24x3 -conv1+relu-> 24x24x64 -pool 3x3/2-> 12x12x64
 *             -conv2+relu-> 12x12x32 -pool 3x3/2-> 6x6x32
 *             -conv3+relu-> 6x6x20   -pool 3x3/2-> 3x3x20
 *             -flatten(HWC)-> 180 -perceptron-> 10
 *
 * Formats virgule fixe : config.hpp. Dimensions : ici (config.hpp est regénéré par Exploration/).
 */

// Taille des noyaux de convolution, fixée à la compilation : -DKS=3 pour le réseau 3x3
#ifndef KS
#define KS 5
#endif
#if KS != 3 && KS != 5
#error "KS doit valoir 3 ou 5"
#endif

// Dimensions du réseau
#define IN_C      3         // canaux de l'image d'entrée (RGB)
#define IN_H      24        // image rognée 24x24
#define IN_WD     24
#define C1        64        // canaux de sortie de conv1
#define C2        32
#define C3        20
#define P1_H      (IN_H / 2)    // 12 : sortie du pool 1
#define P2_H      (P1_H / 2)    // 6
#define P3_H      (P2_H / 2)    // 3
#define FC_IN     (C3 * P3_H * P3_H)   // 180
#define N_CLASSES 10

#define IN_SIZE   (IN_C * IN_H * IN_WD)   // 1728 valeurs en entrée
#define K1_SIZE   (C1 * IN_C * KS * KS)
#define K2_SIZE   (C2 * C1 * KS * KS)
#define K3_SIZE   (C3 * C2 * KS * KS)
#define FCK_SIZE  (FC_IN * N_CLASSES)

/*
 * Fonction synthétisée par Catapult (top).
 *     image  : image rognée et normalisée, rangée [C][H][W]
 *     ker*   : noyaux [C_out][C_in][KS][KS] ; bia* : biais
 *     fck    : poids du perceptron (180 x 10, ligne par ligne, entrées dans l'ordre HWC) ; fcb : biais
 *     scores : scores des 10 classes (sortie)
 */
void cnn(
    const input_t image[IN_SIZE],
    const ker1_t  ker1[K1_SIZE],  const bias1_t bia1[C1],
    const ker2_t  ker2[K2_SIZE],  const bias2_t bia2[C2],
    const ker3_t  ker3[K3_SIZE],  const bias3_t bia3[C3],
    const fck_t   fck[FCK_SIZE],  const fcb_t   fcb[N_CLASSES],
    out_t         scores[N_CLASSES]
);

#endif // CNN_HPP
