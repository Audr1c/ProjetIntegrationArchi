#include "extract_coeff.hpp"

#include <cstdlib>
#include <fstream>
#include <sstream>

// Analyse le corps d'un tenseur ("[[1 2] [3 4]]") : valeurs + forme déduite des crochets
static Tensor parse_body(const string& body, const string& name) {
    Tensor t;
    vector<int> counts;     // nb d'éléments dans le conteneur courant, par niveau
    int depth = 0;

    const char* p   = body.c_str();
    const char* end = p + body.size();
    while (p < end) {
        if (*p == '[') {
            if (depth > 0) counts[depth - 1]++;
            depth++;
            if ((int)counts.size() < depth) {
                counts.push_back(0);
                t.shape.push_back(-1);
            }
            counts[depth - 1] = 0;
            p++;
        } else if (*p == ']') {
            if (depth == 0) throw runtime_error("parse_tensors : ']' en trop dans " + name);
            if (t.shape[depth - 1] < 0) t.shape[depth - 1] = counts[depth - 1];
            depth--;
            p++;
        } else if (*p == '-' || *p == '+' || *p == '.' || (*p >= '0' && *p <= '9')) {
            char* next;
            double v = strtod(p, &next);
            if (next == p) throw runtime_error("parse_tensors : nombre invalide dans " + name);
            t.value.push_back(v);
            if (depth > 0) counts[depth - 1]++;
            p = next;
        } else {
            p++;   // espaces, retours à la ligne
        }
    }

    // Vérification : le produit des dimensions doit valoir le nombre de valeurs
    size_t n = 1;
    for (int d : t.shape) n *= d;
    if (depth != 0 || n != t.value.size())
        throw runtime_error("parse_tensors : forme incohérente pour " + name);
    return t;
}

map<string, Tensor> parse_tensors(const string& path) {
    ifstream f(path);
    if (!f) throw runtime_error("parse_tensors : impossible d'ouvrir " + path);

    map<string, Tensor> tensors;
    const string tag = "tensor_name:";
    string line, name, body;

    auto flush = [&]() {
        if (!name.empty()) tensors[name] = parse_body(body, name);
        body.clear();
    };

    while (getline(f, line)) {
        if (line.compare(0, tag.size(), tag) == 0) {
            flush();
            stringstream ss(line.substr(tag.size()));
            ss >> name;
        } else {
            body += line;
            body += '\n';
        }
    }
    flush();
    return tensors;
}

const Tensor& get_tensor(const map<string, Tensor>& tensors, const string& name, int ndim) {
    auto it = tensors.find(name);
    if (it == tensors.end())
        throw runtime_error("tenseur absent du fichier : " + name);
    if ((int)it->second.shape.size() != ndim)
        throw runtime_error("tenseur " + name + " : " + to_string(ndim) + " dimensions attendues");
    return it->second;
}
