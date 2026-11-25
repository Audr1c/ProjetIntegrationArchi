/*
 * Testbench SCVerify de la fonction top cnn() — voir hls/AUDIT_HLS.md C-01, C-06, C-07, C-08.
 * Exclu de la synthèse (hls/cnn.tcl : -exclude true), comme FIR_TESTBENCH.cpp dans hls/Demo_FIR/.
 *
 * Pour chaque image (indices 0..N-1 de hls/ref/images_200.bin = les 200 premières de data_batch_1,
 * versionnées : data/ est ignoré par git et absent d'un clone neuf, ex. sur les machines de l'école) :
 *   lecture + rognage + normalisation (read_image.cpp, en double) -> input_t image[1728]
 *   CCS_DESIGN(cnn)(image, scores)
 *   affichage des scores, de la classe prédite et du label ;
 *   comparaison exacte aux scores de référence hls/ref/scores_kK.txt (produits par cpp/build/main --dump)
 *   si ce fichier a été produit avec les mêmes formats (ligne de signature identique).
 *
 * Sous SCVerify, Catapult compare en plus automatiquement les sorties du RTL à celles du C++.
 *
 * Variables d'environnement :
 *   CNN_ROOT  racine du dépôt (obligatoire sous Catapult : SCVerify s'exécute dans le dossier du
 *             projet Catapult ; hls/cnn.tcl la positionne). Hors Catapult : PROJECT_ROOT (CMake).
 *   CNN_TB_N  nombre d'images (défaut 3) : la simulation RTL coûte ~10,7 M MAC par image.
 *             Un argument en ligne de commande est prioritaire.
 *
 * Code de retour : 0 si toutes les comparaisons à la référence passent, 1 sinon.
 */

#include <cstdlib>
#include <exception>
#include <iostream>
#include <iomanip>
#include <string>
#include <mc_scverify.h>      // Catapult ; hors Catapult : hls/stub/mc_scverify.h
#include "../cpp/config.hpp"      // chemins relatifs : aucun -I vers cpp/ nécessaire (hls/cnn.tcl)
#include "../cpp/cnn.hpp"
#include "../cpp/read_image.hpp"
#include "../cpp/tb_common.hpp"

using namespace std;


CCS_MAIN(int argc, char** argv) {

    // ---------- Paramètres ----------
    const char* env_root = getenv("CNN_ROOT");
#ifdef PROJECT_ROOT
    const string root = env_root ? env_root : PROJECT_ROOT;
#else
    if (!env_root) {
        cerr << "Erreur : definir CNN_ROOT (racine du depot), par exemple dans hls/cnn.tcl" << endl;
        CCS_RETURN(1);
    }
    const string root = env_root;
#endif
    const char* env_n = getenv("CNN_TB_N");
    const int n_images = argc > 1 ? atoi(argv[1]) : (env_n ? atoi(env_n) : 3);

    // 200 premières images de data_batch_1 (head -c 614600 data_batch_1.bin), mêmes que hls/ref/scores_k*.txt
    const string img_path = root + "/hls/ref/images_200.bin";
    const string ref_path = root + "/hls/ref/scores_k" + to_string(KS) + ".txt";

    cout << "=== TESTBENCH HLS cnn() ===" << endl;
    if (n_images < 1 || n_images > 200) {
        cerr << "Erreur : nombre d'images " << n_images << " hors de [1, 200] (" << img_path << ")" << endl;
        CCS_RETURN(1);
    }
    cout << "Noyau " << KS << "x" << KS << ", " << n_images << " image(s) de " << img_path << endl;

    // ---------- Référence ----------
    ScoreReference ref;
    bool use_ref = false;
    if (!load_reference(ref_path, ref))
        cout << "Pas de reference lisible (" << ref_path << ") : scores affiches sans comparaison" << endl;
    else if (ref.signature != format_signature())
        cout << "Reference " << ref_path << " produite avec d'autres formats : pas de comparaison\n"
             << "  reference : " << ref.signature << "\n  actuel    : " << format_signature() << endl;
    else {
        use_ref = true;
        cout << "Comparaison exacte a " << ref_path << endl;
    }

    // ---------- Images ----------
    int mismatches = 0, compared = 0, correct = 0;
    try {
        for (int i = 0; i < n_images; i++) {
            RawImage raw = load_image(img_path, i);
            input_t image[IN_SIZE];
            to_image(raw, image);

            out_t scores[N_CLASSES];
            CCS_DESIGN(cnn)(image, scores);

            int best = 0;
            for (int j = 1; j < N_CLASSES; j++)
                if (scores[j] > scores[best]) best = j;
            correct += (best == raw.label);

            cout << "image " << i << " : label " << raw.label << ", predit " << best << ", scores";
            for (int j = 0; j < N_CLASSES; j++)
                cout << " " << scores[j].to_double();

            if (use_ref && ref.scores.count(i)) {
                compared++;
                bool same = true;
                for (int j = 0; j < N_CLASSES; j++)
                    same = same && (scores[j].to_double() == ref.scores[i][j]);
                if (!same) mismatches++;
                cout << (same ? "  [= ref]" : "  [DIFFERENT de la reference]");
            }
            cout << endl;
        }
    }
    catch (const exception& e) {
        cerr << "Erreur : " << e.what() << endl;
        CCS_RETURN(1);
    }

    // ---------- Bilan ----------
    cout << "Bonnes classes : " << correct << "/" << n_images << endl;
    if (use_ref)
        cout << (mismatches ? "ECHEC" : "OK") << " : " << compared - mismatches << "/" << compared
             << " images identiques a la reference" << endl;
    CCS_RETURN(mismatches ? 1 : 0);
}
