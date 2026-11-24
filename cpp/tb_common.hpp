#ifndef TB_COMMON_HPP
#define TB_COMMON_HPP

/*
 * Outils communs aux testbenchs (main.cpp --dump, hls/tb_hls.cpp) — PAS synthétisable.
 *
 * Fichier de scores de référence (hls/ref/scores_kK.txt, voir hls/AUDIT_HLS.md C-06) :
 *     # formats KS=5 in=16,4 ker1=16,3 ...      <- signature : formats avec lesquels il a été produit
 *     <indice image> <score 0> ... <score 9>     <- une ligne par image, 17 chiffres (valeur exacte)
 * Les scores ne sont comparables qu'à formats identiques : la signature le vérifie.
 */

#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <vector>
#include "config.hpp"
#include "cnn.hpp"

// Formats de config.hpp + taille de noyau, sur une ligne
inline std::string format_signature() {
    std::ostringstream s;
    s << "# formats KS=" << KS;
    const struct { const char* name; int W, I; } f[] = {
        {"in",    IN_W,    IN_I},
        {"ker1",  K1_W,    K1_I},    {"bias1", B1_W, B1_I}, {"acc1", ACC1_W, ACC1_I},
        {"conv1", CONV1_W, CONV1_I}, {"pool1", POOL1_W, POOL1_I},
        {"ker2",  K2_W,    K2_I},    {"bias2", B2_W, B2_I}, {"acc2", ACC2_W, ACC2_I},
        {"conv2", CONV2_W, CONV2_I}, {"pool2", POOL2_W, POOL2_I},
        {"ker3",  K3_W,    K3_I},    {"bias3", B3_W, B3_I}, {"acc3", ACC3_W, ACC3_I},
        {"conv3", CONV3_W, CONV3_I}, {"pool3", POOL3_W, POOL3_I},
        {"fck",   FCK_W,   FCK_I},   {"fcb",   FCB_W, FCB_I}, {"accfc", ACCFC_W, ACCFC_I},
        {"out",   OUT_W,   OUT_I},
    };
    for (const auto& x : f)
        s << " " << x.name << "=" << x.W << "," << x.I;
    return s.str();
}

// Une ligne du fichier de référence
inline std::string score_line(int index, const out_t scores[N_CLASSES]) {
    std::ostringstream s;
    s << index;
    for (int j = 0; j < N_CLASSES; j++)
        s << " " << std::setprecision(17) << scores[j].to_double();
    return s.str();
}

// Fichier de référence lu : signature + {indice image -> 10 scores}
struct ScoreReference {
    std::string signature;
    std::map<int, std::vector<double>> scores;
};

// false si le fichier est absent ou mal formé
inline bool load_reference(const std::string& path, ScoreReference& ref) {
    std::ifstream f(path);
    if (!f || !std::getline(f, ref.signature))
        return false;
    std::string line;
    while (std::getline(f, line)) {
        std::istringstream s(line);
        int index;
        std::vector<double> v(N_CLASSES);
        if (!(s >> index))
            continue;
        for (int j = 0; j < N_CLASSES; j++)
            if (!(s >> v[j]))
                return false;
        ref.scores[index] = v;
    }
    return true;
}

#endif // TB_COMMON_HPP
