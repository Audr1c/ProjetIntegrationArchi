#include <iostream>
#include <iomanip>
#include <string>
#include <cstdlib>
#include <fstream>
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
 *     k_size    : noyau des convolutions, 3 ou 5, défaut 5
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

    if (k_size != 3 && k_size != 5) {
        cerr << "Erreur : k_size doit valoir 3 ou 5 (reçu " << k_size << ")" << endl;
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
        map<string, Tensor> tensors = parse_tensors(coef_path);

        CnnCoeffs coef;
        coef.ker1 = to_kernel<K1_W, K1_I, true>(get_tensor(tensors, "conv1/weights", 4));
        coef.bia1 = to_bias  <B1_W, B1_I, true>(get_tensor(tensors, "conv1/biases",  1));
        coef.ker2 = to_kernel<K2_W, K2_I, true>(get_tensor(tensors, "conv2/weights", 4));
        coef.bia2 = to_bias  <B2_W, B2_I, true>(get_tensor(tensors, "conv2/biases",  1));
        coef.ker3 = to_kernel<K3_W, K3_I, true>(get_tensor(tensors, "conv3/weights", 4));
        coef.bia3 = to_bias  <B3_W, B3_I, true>(get_tensor(tensors, "conv3/biases",  1));
        coef.fc_k = to_matrix<FCK_W, FCK_I, true>(get_tensor(tensors, "local3/weights", 2));
        coef.fc_b = to_vector<FCB_W, FCB_I, true>(get_tensor(tensors, "local3/biases",  1));

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
            imageT<IN_W, IN_I, true> image = to_image<IN_W, IN_I, true>(raw);

            vector<out_t> scores = cnn(image, coef);

            int best = 0;
            for (int j = 1; j < (int)scores.size(); j++)
                if (scores[j] > scores[best]) best = j;
            if (best == raw.label) works++;

            if (trace) {
                double other = -1e300;
                for (int j = 0; j < (int)scores.size(); j++)
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
