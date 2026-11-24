#ifndef READ_IMAGE_HPP
#define READ_IMAGE_HPP

/*
 * Lecture des fichiers binaires CIFAR-10 (*.bin)
 * Équivalent C++ de python/read_image.py
 *
 * Un enregistrement fait 3073 octets :
 *     [1 octet : label 0..9][1024 octets R][1024 octets G][1024 octets B]
 * Chaque plan fait 32x32, rangé ligne par ligne.
 *
 * L'image est rognée au centre (24x24) puis normalisée :
 *     x' = (x - moyenne) / max(écart-type, 1/sqrt(24*24*3))
 * La sortie est rangée en [canal][ligne][colonne] (ordre des feature maps du modèle).
 */

#include <string>
#include <vector>
#include "../hls/include/ac_fixed.h"

using namespace std;

const int IMG_SIZE     = 32;
const int IMG_BYTES    = 3 * IMG_SIZE * IMG_SIZE;   // 3072
const int RECORD_BYTES = 1 + IMG_BYTES;             // 3073
const int CROP_SIZE    = 24;
const int CROP_OFFSET  = (IMG_SIZE - CROP_SIZE) / 2;  // 4

// Image lue en double (avant conversion en virgule fixe)
struct RawImage {
    vector<double> value;   // [3][24][24]
    int label;
};

// Lit l'image n du fichier, rognée, normalisée si demandé
RawImage load_image(const string& path, int n, bool apply_normalize = true);

// Nombre d'images contenues dans le fichier
int count_images(const string& path);

// Noms des 10 classes (batches.meta.txt)
vector<string> load_label_names(const string& path);

// Conversion vers le tableau ac_fixed d'entrée du modèle ([3][24][24])
template <int W, int I, bool S>
void to_image(const RawImage& raw, ac_fixed<W, I, S>* img) {
    for (size_t i = 0; i < raw.value.size(); i++)
        img[i] = ac_fixed<W, I, S>(raw.value[i]);
}

#endif // READ_IMAGE_HPP
