#ifndef AC_CHANNEL_STUB_H
#define AC_CHANNEL_STUB_H

/*
 * Remplacement MINIMAL de ac_channel.h (fourni par Catapult dans $MGC_HOME/shared/include),
 * uniquement pour compiler le modèle C++ sur un PC sans Catapult (cibles CMake, Exploration/).
 * Sous Catapult, ce dossier n'est PAS dans le chemin d'include : c'est le vrai fichier qui est utilisé.
 * Écrit pour ce projet (n'est pas une copie du fichier de Siemens). Si hls/include/ contient un jour le
 * vrai ac_channel.h (copié depuis l'école), il passe avant celui-ci (ordre des -I).
 *
 * Sémantique reprise : FIFO non bornée ; read() sur un canal vide est une erreur fatale
 * (le vrai ac_channel lève une exception) ; un canal ne se copie pas.
 */

#include <deque>
#include <cstdio>
#include <cstdlib>

template <class T>
class ac_channel {
public:
    ac_channel() {}

    T read() {
        if (fifo.empty()) {
            std::fprintf(stderr, "ac_channel (stub) : lecture d'un canal vide\n");
            std::abort();
        }
        T t = fifo.front();
        fifo.pop_front();
        return t;
    }
    void read(T& t) { t = read(); }
    void write(const T& t) { fifo.push_back(t); }

    bool nb_read(T& t) {
        if (fifo.empty())
            return false;
        t = read();
        return true;
    }
    bool nb_write(const T& t) { write(t); return true; }

    unsigned int size() const { return (unsigned int)fifo.size(); }
    bool empty() const { return fifo.empty(); }
    bool available(unsigned int n) const { return fifo.size() >= n; }

private:
    ac_channel(const ac_channel&);              // non copiable, comme le vrai
    ac_channel& operator=(const ac_channel&);
    std::deque<T> fifo;
};

#endif // AC_CHANNEL_STUB_H
