#include <iostream>
#include <iomanip>
#include <string>
#include <cstdlib>
#include <fstream>
#include <map>
#include "config.hpp"
#include "utils.hpp"
#include "cnn.hpp"
#include "extract_coeff.hpp"
#include "read_image.hpp"

using namespace std;

#ifndef PROJECT_ROOT
#define PROJECT_ROOT ".."      // racine du dépôt (définie par CMake)
#endif


// Affiche un format "nom  <W,I,S>"
static void print_format(const string& name, int W, int I, bool S) {
    cout << "  " << left << setw(10) << name << "ac_fixed<" << W << ", " << I << ", "
         << (S ? "true" : "false") << ">" << endl;
}


/*
 * Usage : ./main [nb_images] [k_size] [batch] [--order FICHIER] [--trace]
 *     nb_images : nombre d'images à classer (0 = tout le fichier), défaut 100
 *     k_size    : noyau des convolutions, 3 ou 5, défaut 5 ; doit valoir KS (fixé à la compilation, -DKS=3)
 *     batch     : fichier CIFAR-10, défaut data_batch_1.bin
 *     --order   : fichier d'indices d'images (séparés par des espaces), évaluées dans cet ordre
 *     --trace   : une ligne par image, pour Exploration/explore.py :
 *                 "T <rang> <indice> <label> <prédiction> <marge>"
 *                 marge = score(label) - meilleur score des autres classes (< 0 si erreur)
 *
 * Max-pool fixé à 3x3, pas de 2. Formats virgule fixe : config.hpp
 */
int main(int argc, char** argv) {

    cout << "=== MAIN CPP PROGRAM ===" << endl;

    vector<string> pos;
    string order_file;
    bool trace = false;
    for (int a = 1; a < argc; a++) {
        string s = argv[a];
        if (s == "--order" && a + 1 < argc) order_file = argv[++a];
        else if (s == "--trace")            trace = true;
        else                                pos.push_back(s);
    }

    int    max_count = pos.size() > 0 ? atoi(pos[0].c_str()) : 100;
    int    k_size    = pos.size() > 1 ? atoi(pos[1].c_str()) : 5;
    string batch     = pos.size() > 2 ? pos[2] : "data_batch_1.bin";

    if (k_size != KS) {
        cerr << "Erreur : ce binaire est compilé pour un noyau " << KS << "x" << KS << " (reçu k_size = "
             << k_size << ") : recompiler avec -DKS=" << k_size << endl;
        return 1;
    }

    const string root      = PROJECT_ROOT;
    const string data_dir  = root + "/data/cifar-10-batches-bin/";
    const string coef_path = root + "/data/coef/CNN_coeff_" + to_string(k_size) + "x" + to_string(k_size) + ".txt";
    const string img_path  = data_dir + batch;

    cout << "Formats :" << endl;
    print_format("input", IN_W,    IN_I,    true);
    print_format("ker1",  K1_W,    K1_I,    true);
    print_format("bias1", B1_W,    B1_I,    true);
    print_format("conv1", CONV1_W, CONV1_I, true);
    print_format("pool1", POOL1_W, POOL1_I, false);
    print_format("ker2",  K2_W,    K2_I,    true);
    print_format("bias2", B2_W,    B2_I,    true);
    print_format("conv2", CONV2_W, CONV2_I, true);
    print_format("pool2", POOL2_W, POOL2_I, false);
    print_format("ker3",  K3_W,    K3_I,    true);
    print_format("bias3", B3_W,    B3_I,    true);
    print_format("conv3", CONV3_W, CONV3_I, true);
    print_format("pool3", POOL3_W, POOL3_I, false);
    print_format("fc_k",  FCK_W,   FCK_I,   true);
    print_format("fc_b",  FCB_W,   FCB_I,   true);
    print_format("out",   OUT_W,   OUT_I,   true);
    auto print_acc = [](const string& name, int W, int I) {
        if (W > 0) print_format(name, W, I, true);
        else cout << "  " << left << setw(10) << name << "automatique (sans perte)" << endl;
    };
    print_acc("acc1",  ACC1_W,  ACC1_I);
    print_acc("acc2",  ACC2_W,  ACC2_I);
    print_acc("acc3",  ACC3_W,  ACC3_I);
    print_acc("accfc", ACCFC_W, ACCFC_I);

    try {
        //=== COEFFICIENTS ===//
        // static : 74 000 valeurs, hors de la pile
        static ker1_t  ker1[K1_SIZE];  static bias1_t bia1[C1];
        static ker2_t  ker2[K2_SIZE];  static bias2_t bia2[C2];
        static ker3_t  ker3[K3_SIZE];  static bias3_t bia3[C3];
        static fck_t   fck[FCK_SIZE];  static fcb_t   fcb[N_CLASSES];
        {
            map<string, Tensor> tensors = parse_tensors(coef_path);
            to_kernel(get_tensor(tensors, "conv1/weights", 4), C1, IN_C, KS, ker1);
            to_array (get_tensor(tensors, "conv1/biases",  1), C1, bia1);
            to_kernel(get_tensor(tensors, "conv2/weights", 4), C2, C1, KS, ker2);
            to_array (get_tensor(tensors, "conv2/biases",  1), C2, bia2);
            to_kernel(get_tensor(tensors, "conv3/weights", 4), C3, C2, KS, ker3);
            to_array (get_tensor(tensors, "conv3/biases",  1), C3, bia3);
            to_array (get_tensor(tensors, "local3/weights", 2), FCK_SIZE, fck);
            to_array (get_tensor(tensors, "local3/biases",  1), N_CLASSES, fcb);
        }

        //=== IMAGES ===//
        int n_images = count_images(img_path);

        // Ordre d'évaluation : 0, 1, 2... ou celui du fichier --order
        vector<int> order;
        if (!order_file.empty()) {
            ifstream f(order_file);
            if (!f) throw runtime_error("impossible d'ouvrir " + order_file);
            int idx;
            while (f >> idx) {
                if (idx < 0 || idx >= n_images) throw runtime_error("indice d'image invalide : " + to_string(idx));
                order.push_back(idx);
            }
        } else {
            for (int i = 0; i < n_images; i++) order.push_back(i);
        }
        if (max_count <= 0 || max_count > (int)order.size()) max_count = (int)order.size();

        cout << "Noyau " << k_size << "x" << k_size << ", max-pool 3x3, "
             << max_count << " images de " << batch << endl;

        int works = 0;
        for (int n = 0; n < max_count; n++) {
            RawImage raw = load_image(img_path, order[n]);
            input_t image[IN_SIZE];
            to_image(raw, image);

            out_t scores[N_CLASSES];
            cnn(image, ker1, bia1, ker2, bia2, ker3, bia3, fck, fcb, scores);

            int best = 0;
            for (int j = 1; j < N_CLASSES; j++)
                if (scores[j] > scores[best]) best = j;
            if (best == raw.label) works++;

            if (trace) {
                double other = -1e300;
                for (int j = 0; j < N_CLASSES; j++)
                    if (j != raw.label) other = max(other, scores[j].to_double());
                double margin = scores[raw.label].to_double() - other;
                cout << "T " << n + 1 << " " << order[n] << " " << raw.label << " " << best << " "
                     << setprecision(6) << margin << endl;      // endl : explore.py lit au fil de l'eau
            } else {
                cout << "\r  image " << right << setw(5) << n + 1 << "/" << max_count
                     << "  précision : " << fixed << setprecision(2) << 100.0 * works / (n + 1) << " %" << flush;
            }
        }
        cout << endl;

        cout << "##### finished ######" << endl;
        cout << "Got an accuracy of " << fixed << setprecision(2) << 100.0 * works / max_count
             << "% (" << works << "/" << max_count << ")" << endl;
    }
    catch (const exception& e) {
        cerr << "Erreur : " << e.what() << endl;
        return 1;
    }

    return 0;
}
