#ifndef MC_SCVERIFY_STUB_H
#define MC_SCVERIFY_STUB_H

/*
 * Remplacement MINIMAL de mc_scverify.h (fourni par Catapult dans $MGC_HOME/shared/include),
 * uniquement pour compiler et lancer hls/tb_hls.cpp sur un PC sans Catapult (cible CMake tb_hls).
 * Sous Catapult, ce dossier n'est PAS dans le chemin d'include : c'est le vrai fichier qui est utilisé.
 * Écrit pour ce projet (n'est pas une copie du fichier de Siemens).
 */

#define CCS_MAIN(...)   int main(__VA_ARGS__)
#define CCS_DESIGN(f)   f
#define CCS_RETURN(x)   return (x)

#endif // MC_SCVERIFY_STUB_H
