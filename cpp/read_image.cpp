#include "read_image.hpp"

#include <cmath>
#include <fstream>
#include <stdexcept>

RawImage load_image(const string& path, int n, bool apply_normalize) {
    ifstream f(path, ios::binary);
    if (!f) throw runtime_error("load_image : impossible d'ouvrir " + path);

    vector<unsigned char> record(RECORD_BYTES);
    f.seekg((streamoff)n * RECORD_BYTES);
    if (!f.read((char*)record.data(), RECORD_BYTES))
        throw runtime_error("load_image : image " + to_string(n) + " absente de " + path);

    RawImage raw;
    raw.label = record[0];
    raw.value.resize(3 * CROP_SIZE * CROP_SIZE);

    // Rognage au centre : lignes et colonnes [4, 28[
    for (int c = 0; c < 3; c++)
        for (int r = 0; r < CROP_SIZE; r++)
            for (int k = 0; k < CROP_SIZE; k++)
                raw.value[(c * CROP_SIZE + r) * CROP_SIZE + k] =
                    record[1 + c * IMG_SIZE * IMG_SIZE + (r + CROP_OFFSET) * IMG_SIZE + (k + CROP_OFFSET)];

    if (apply_normalize) {
        const double N = (double)raw.value.size();   // 24*24*3 = 1728
        double mu = 0;
        for (double v : raw.value) mu += v;
        mu /= N;
        double var = 0;
        for (double v : raw.value) var += (v - mu) * (v - mu);
        double sigma = sqrt(var / N);                 // écart-type en 1/N, comme numpy
        sigma = fmax(sigma, 1.0 / sqrt(N));
        for (double& v : raw.value) v = (v - mu) / sigma;
    }
    return raw;
}

int count_images(const string& path) {
    ifstream f(path, ios::binary | ios::ate);
    if (!f) throw runtime_error("count_images : impossible d'ouvrir " + path);
    return (int)(f.tellg() / RECORD_BYTES);
}

vector<string> load_label_names(const string& path) {
    ifstream f(path);
    if (!f) throw runtime_error("load_label_names : impossible d'ouvrir " + path);
    vector<string> names;
    string line;
    while (getline(f, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
        if (!line.empty()) names.push_back(line);
    }
    return names;
}
