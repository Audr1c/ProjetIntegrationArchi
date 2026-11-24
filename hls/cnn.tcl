# ==========================================================================
#  Synthèse HLS du CNN CIFAR-10 avec Catapult — voir hls/AUDIT_HLS.md (C-02, C-03)
#  Modèle : hls/Demo_FIR/demo_sim.tcl et hls/demoFir.tcl
#
#  Usage (machine de l'école) :
#      source hls/bash_mentor_24               # environnement Catapult / Questa / Precision
#      mkdir -p hls/work && cd hls/work        # dossier de travail (ignoré par git : work/)
#      catapult -shell -file ../cnn.tcl        # ou, dans la GUI : File > Run Script… > hls/cnn.tcl
#
#  Cloner le dépôt dans un chemin SANS ESPACE : les Makefiles générés par SCVerify ne les
#  supportent pas de façon fiable (le chemin local « S9 SEI » en contient une).
#
#  Le script s'arrête après la génération du RTL et la vérification SCVerify. Les directives
#  d'architecture (pipeline, unroll, mémoires : partie D de l'audit) viennent ensuite.
# ==========================================================================

# ---------------- Paramètres ----------------
set ROOT [file normalize [file join [file dirname [info script]] ..]]   ;# racine du dépôt
set CPP  [file join $ROOT cpp]
set HLS  [file join $ROOT hls]

set KS 5                    ;# taille des noyaux (3 ou 5) -> coeffs_k$KS.hpp, hls/ref/scores_k$KS.txt
set TB_IMAGES 2             ;# images simulées par SCVerify (~10,7 M MAC par image en RTL : rester petit)
set CLOCK_NS 10.0           ;# 100 MHz

# Cible FPGA : Zybo Z7 = Zynq-7000. Z7-10 : xc7z010clg400-1 ; Z7-20 : xc7z020clg400-1.
# !!! NOM DE BIBLIOTHÈQUE À VÉRIFIER : il n'apparaît dans aucune source locale. La démo utilise
# !!! mgc_Xilinx-ARTIX-7-2_beh ; pour le Zynq, choisir la famille dans Task Bar > Libraries et
# !!! recopier ici la commande « solution library add » écrite dans le log.
set FPGA_LIB  mgc_Xilinx-ZYNQ-1_beh
set FPGA_OPTS {-rtlsyntool Precision -manufacturer Xilinx -family ZYNQ -speed -1 -part xc7z020clg400-1}

# Testbench : chemins des données et nombre d'images (lus par hls/tb_hls.cpp, C-08).
# Les processus lancés par Catapult (make SCVerify, simulateur) héritent de ces variables.
set ::env(CNN_ROOT) $ROOT
set ::env(CNN_TB_N) $TB_IMAGES

# ---------------- Projet et options ----------------
project new
solution new -state initial
solution options defaults
solution options set /Input/TargetPlatform x86_64
solution options set /Input/CppStandard c++11
# Pas de -I vers hls/include : Catapult doit utiliser SES AC datatypes (AUDIT C-04).
# Pas de -I vers cpp/ non plus : tous les includes du projet sont relatifs ("../cpp/…").
solution options set /Input/SearchPath /usr/include/x86_64-linux-gnu/
# Au niveau de la SOLUTION : « options set Input/CompilerFlags » ne règle que la valeur globale par défaut,
# non reportée sur la solution déjà créée (-DKS absent de la ligne « Front End called with arguments »)
solution options set /Input/CompilerFlags "-DKS=$KS"
solution options set /Output/OutputVerilog false      ;# RTL en VHDL, comme la démo
flow package require /SCVerify

# ---------------- Fichiers (C-02) ----------------
# Design : synthétisé
solution file add [file join $CPP cnn.cpp]            -type C++
solution file add [file join $CPP cnn.hpp]            -type CHEADER
solution file add [file join $CPP config.hpp]         -type CHEADER
solution file add [file join $CPP utils.hpp]          -type CHEADER
solution file add [file join $CPP utils.cpp]          -type CHEADER   ;# templates, inclus par utils.hpp
# coeffs_k$KS.hpp N'EST PAS ajouté : Catapult compile chaque fichier du projet séparément, et les ROM
# n'ont de sens qu'incluses dans le corps de cnn() (#include dans cnn.cpp, trouvé par Catapult).
# Testbench : exclu de la synthèse, compilé par SCVerify
solution file add [file join $HLS tb_hls.cpp]         -type C++     -exclude true
solution file add [file join $CPP read_image.cpp]     -type C++     -exclude true
solution file add [file join $CPP read_image.hpp]     -type CHEADER -exclude true
solution file add [file join $CPP tb_common.hpp]      -type CHEADER -exclude true

# ---------------- Directives générales (reprises de la démo) ----------------
directive set -DESIGN_GOAL area
directive set -SPECULATE true
directive set -MERGEABLE true
directive set -REGISTER_THRESHOLD 256
directive set -MEM_MAP_THRESHOLD 32     ;# tableaux > 32 mots -> mémoires (feature maps)
directive set -ROM_THRESHOLD 64         ;# tableaux constants > 64 mots -> ROM (coefficients)
directive set -UNROLL no
directive set -IO_MODE super
directive set -FSM_ENCODING none
directive set -NO_X_ASSIGNMENTS true
directive set -SAFE_FSM false
directive set -TRANSACTION_DONE_SIGNAL true
directive set -TRANSACTION_SYNC ready
directive set -CLOCK_OVERHEAD 20.000000
directive set -OPT_CONST_MULTS use_library
directive set -CHARACTERIZE_ROM false
directive set -PROTOTYPE_ROM true

# ---------------- Analyse et compilation C++ ----------------
go analyze
directive set -DESIGN_HIERARCHY cnn
go compile

# ---------------- Technologie (C-03) ----------------
if {[catch {solution library add $FPGA_LIB -- {*}$FPGA_OPTS} err]} {
    puts "\n*** Bibliothèque FPGA '$FPGA_LIB' introuvable : corriger FPGA_LIB / FPGA_OPTS dans cnn.tcl"
    puts "*** (Task Bar > Libraries dans la GUI, puis recopier la commande du log)\n$err"
    error $err
}
solution library add Xilinx_RAMS
solution library add Xilinx_ROMS
go libraries

directive set -CLOCKS [list clk [list -CLOCK_PERIOD $CLOCK_NS -CLOCK_EDGE rising -CLOCK_HIGH_TIME [expr {$CLOCK_NS / 2}] -CLOCK_OFFSET 0.000000 -CLOCK_UNCERTAINTY 0.0 -RESET_KIND sync -RESET_SYNC_NAME rst -RESET_SYNC_ACTIVE high -RESET_ASYNC_NAME arst_n -RESET_ASYNC_ACTIVE low -ENABLE_NAME {} -ENABLE_ACTIVE high]]
directive set /cnn -START_FLAG start
directive set /cnn -READY_FLAG ready
directive set /cnn -DONE_FLAG done

# ---------------- Architecture, ordonnancement, RTL ----------------
go assembly
# (directives de boucles / mémoires ici : partie D de l'audit)
go architect
go allocate
go extract

# ---------------- Vérification SCVerify ----------------
# 1) C++ seul, dans l'environnement SCVerify (rapide) ; 2) RTL VHDL sous Questa, comparé au C++
flow run /SCVerify
flow run /SCVerify/launch_make ./scverify/Verify_orig_cxx_osci.mk {} SIMTOOL=osci sim
flow run /SCVerify/launch_make ./scverify/Verify_rtl_vhdl_msim.mk {} SIMTOOL=msim build
flow run /SCVerify/launch_make ./scverify/Verify_rtl_vhdl_msim.mk {} SIMTOOL=msim sim
