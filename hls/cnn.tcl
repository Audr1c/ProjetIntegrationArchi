# ==========================================================================
#  Synthese HLS du CNN CIFAR-10 avec Catapult - voir hls/AUDIT_HLS.md (C-02, C-03)
#  Modele : hls/Demo_FIR/demo_sim.tcl et hls/demoFir.tcl
#
#  Usage (machine de l'ecole) :
#      source hls/bash_mentor_24               # environnement Catapult / Questa / Precision
#      mkdir -p hls/work && cd hls/work        # dossier de travail (ignore par git : work/)
#      catapult -shell -file ../cnn.tcl        # ou, dans la GUI : File > Run Script... > hls/cnn.tcl
#
#  Cloner le depot dans un chemin SANS ESPACE : les Makefiles generes par SCVerify ne les
#  supportent pas de facon fiable (le chemin local " S9 SEI " en contient une).
#
#  Le script s'arrete apres la generation du RTL et la verification SCVerify. Les directives
#  d'architecture (pipeline, unroll, memoires : partie D de l'audit) viennent ensuite.
#
#  Durees constatees (2026-11-24, Catapult 2024.2) : go analyze ~ 17 min avec les ROM en ac_fixed
#  initialises par des double, tout le reste ~ 2 min. Depuis, les ROM de synthese sont des entiers deja
#  quantifies (cpp/coeffs_k*_raw.hpp, ~12x plus rapide a compiler avec g++) : a remesurer.
#  APRES TOUT CHANGEMENT DE FORMATS dans cpp/config.hpp : make coeffs (sinon #error a go analyze).
#  Le projet est SAUVE apres go extract : pour essayer d'autres directives, ne pas relancer ce script
#  mais brancher une solution (voir fin de fichier) ; un changement de code ou de formats impose go analyze.
#
#  Resultats sans GUI : a la fin, hls/catapult_report.py copie les rapports dans hls/rapports/ (versionne)
#  et ecrit un resume (latence, surface, memoires, boucles, verdict SCVerify) : voir hls/cnn_report.tcl.
# ==========================================================================

# ---------------- Parametres ----------------
set ROOT [file normalize [file join [file dirname [info script]] ..]]   ;# racine du depot
set CPP  [file join $ROOT cpp]
set HLS  [file join $ROOT hls]

set KS 5                    ;# taille des noyaux (3 ou 5) -> coeffs_k$KS.hpp, hls/ref/scores_k$KS.txt
set TB_IMAGES 1             ;# images simulees par SCVerify (RTL v1 : 46 M cycles par image)
# Simulation RTL (Questa) : des heures pour 46 M cycles (la demo FIR, avec traces, simule ~1 300 cycles/s).
# 0 = generer seulement les Makefiles et la lancer a part depuis un shell (commande affichee a la fin :
#     hls/sim_rtl.sh). Dans les deux cas, compteur de cycles dans le log : [sim] cycle ... (hls/sim_progress.tcl).
set RUN_RTL_SIM 0
set CLOCK_NS 10.0           ;# 100 MHz
# ROM de coefficients : "" = entiers quantifies (cpp/coeffs_k*_raw.hpp, defaut) ;
# "-DCNN_ROM_DOUBLE" = ancienne methode (ac_fixed initialises par des double, ~17 min a go analyze),
# a utiliser seulement si Catapult refuse les ROM de RomWord.
set ROM_FLAGS ""

# ---------------- Architecture sans pipeline ni deroulage (AUDIT_HLS E-01 a E-03) ----------------
# Hierarchie : un bloc Catapult par couche (#pragma hls_design dans cpp/cnn.cpp), top en premier.
# Chaque bloc a son propre multiplieur : plus de multiplexeurs de partage sur le chemin critique.
set BLOCKS {cnn layer1 layer2 layer3 dense}
# Tableaux de MOINS de REG_ARRAY_MAX elements -> registres au lieu d'une RAM/ROM (MEM_MAP_THRESHOLD) :
# biais bia1 (64), bia2 (32), bia3 (20), fcb (10), pool3_chan (180), accumulateurs du perceptron.
# Restent en memoire : image (1728), image2 (36864), pool1_chan (9216), image4 (4608), pool2_chan (1152),
# image6 (720), ker1/ker2/ker3, fck (1800). Doit rester < REGISTER_THRESHOLD (256 par defaut).
set REG_ARRAY_MAX 256
# 1 = feature maps en RAM double port Xilinx (BLOCK_DPRAM_RBW : 2 acces par cycle, meme nombre de BRAM),
# 0 = RAM 1R1W par defaut. Sans pipeline, la latence ne change presque pas : prepare II=1 / deroulage x2.
set DUAL_PORT 1
set DP_RAM Xilinx_RAMS.BLOCK_DPRAM_RBW
# Canaux entre blocs (pool1_chan, pool2_chan) : 2 = ping-pong (une couche traite l'image n+1 pendant que
# la suivante traite l'image n ; memoire doublee), 1 = memoire unique (pas de recouvrement).
set CHAN_STAGES 2
# Directives choisies par l'exploration (ExplorationHLS) : chemin d'un best_directives.tcl, relatif a la
# racine du depot (ex. ExplorationHLS/runs/<run>/best_directives.tcl). Non vide : il REMPLACE les
# directives memoire ci-dessus (DUAL_PORT, CHAN_STAGES) et ajoute pipeline / deroulage.
set DIRECTIVES_FILE ""

# Cible FPGA : notre carte est un Zybo Z7-20 = XC7Z020-1CLG400C (lu sur la boite le 2026-11-25) :
# 280 RAMB18, 220 DSP, 53 200 LUT. (Z7-10 = xc7z010clg400-1, non utilise.)
# Nom de bibliotheque valide le 2026-11-24 ($MGC_HOME/pkgs/ccs_xilinx/mgc_Xilinx-ZYNQ-1_beh.lib).
# Les avertissements LIB-82/LIB-83 (" library created with a newer version ") sont sans consequence.
set FPGA_LIB  mgc_Xilinx-ZYNQ-1_beh
set FPGA_OPTS {-rtlsyntool Precision -manufacturer Xilinx -family ZYNQ -speed -1 -part xc7z020clg400-1}

# Testbench : chemins des donnees et nombre d'images (lus par hls/tb_hls.cpp, C-08).
# Les processus lances par Catapult (make SCVerify, simulateur) heritent de ces variables.
set ::env(CNN_ROOT) $ROOT
set ::env(CNN_TB_N) $TB_IMAGES

# ---------------- Projet et options ----------------
project new
solution new -state initial
solution options defaults
solution options set /Input/TargetPlatform x86_64
solution options set /Input/CppStandard c++11
# Pas de -I vers hls/include : Catapult doit utiliser SES AC datatypes (AUDIT C-04).
# Pas de -I vers cpp/ non plus : tous les includes du projet sont relatifs ("../cpp/...").
solution options set /Input/SearchPath /usr/include/x86_64-linux-gnu/
# Au niveau de la SOLUTION : " options set Input/CompilerFlags " ne regle que la valeur globale par defaut,
# non reportee sur la solution deja creee (-DKS absent de la ligne " Front End called with arguments ")
solution options set /Input/CompilerFlags "-DKS=$KS $ROM_FLAGS"
solution options set /Output/OutputVerilog false      ;# RTL en VHDL, comme la demo
flow package require /SCVerify

# ---------------- Fichiers (C-02) ----------------
# Design : synthetise
solution file add [file join $CPP cnn.cpp]            -type C++
solution file add [file join $CPP cnn.hpp]            -type CHEADER
solution file add [file join $CPP config.hpp]         -type CHEADER
solution file add [file join $CPP utils.hpp]          -type CHEADER
solution file add [file join $CPP utils.cpp]          -type CHEADER   ;# templates, inclus par utils.hpp
# coeffs_k$KS.hpp et coeffs_k${KS}_raw.hpp NE SONT PAS ajoutes : Catapult compile chaque fichier du
# projet separement, et les ROM n'ont de sens qu'incluses dans le corps de cnn() (#include dans cnn.cpp).
# Testbench : exclu de la synthese, compile par SCVerify
solution file add [file join $HLS tb_hls.cpp]         -type C++     -exclude true
solution file add [file join $CPP read_image.cpp]     -type C++     -exclude true
solution file add [file join $CPP read_image.hpp]     -type CHEADER -exclude true
solution file add [file join $CPP tb_common.hpp]      -type CHEADER -exclude true

# ---------------- Directives generales (reprises de la demo) ----------------
directive set -DESIGN_GOAL area
directive set -SPECULATE true
directive set -MERGEABLE true
directive set -REGISTER_THRESHOLD 256
directive set -MEM_MAP_THRESHOLD $REG_ARRAY_MAX ;# tableaux plus petits -> registres (voir REG_ARRAY_MAX)
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

# Directive sur une ressource dont le chemin exact depend de la hierarchie (non verifie avant la 1re
# synthese hierarchique) : essaie les chemins candidats dans l'ordre et garde le premier accepte.
# Aucun accepte : message ATTENTION, le script continue (chercher le nom dans la GUI, Architectural
# constraints, ou dans messages.txt, puis corriger l'appel ici).
proc cnn_try {paths args} {
    foreach p $paths {
        if {![catch {directive set $p {*}$args}]} {
            puts "\[cnn\] directive OK : $p $args"
            return 1
        }
    }
    puts "\[cnn\] ATTENTION directive ignoree, chemin introuvable : $paths $args"
    return 0
}

# ---------------- Analyse et compilation C++ ----------------
go analyze
directive set -DESIGN_HIERARCHY $BLOCKS   ;# doit preceder go compile ; remplace les pragmas hls_design
go compile

# ---------------- Technologie (C-03) ----------------
if {[catch {solution library add $FPGA_LIB -- {*}$FPGA_OPTS} err]} {
    puts "\n*** Bibliotheque FPGA '$FPGA_LIB' introuvable : corriger FPGA_LIB / FPGA_OPTS dans cnn.tcl"
    puts "*** (Task Bar > Libraries dans la GUI, puis recopier la commande du log)\n$err"
    error $err
}
solution library add Xilinx_RAMS
solution library add Xilinx_ROMS
go libraries

directive set -CLOCKS [list clk [list -CLOCK_PERIOD $CLOCK_NS -CLOCK_EDGE rising -CLOCK_HIGH_TIME [expr {$CLOCK_NS / 2}] -CLOCK_OFFSET 0.000000 -CLOCK_UNCERTAINTY 0.0 -RESET_KIND sync -RESET_SYNC_NAME rst -RESET_SYNC_ACTIVE high -RESET_ASYNC_NAME arst_n -RESET_ASYNC_ACTIVE low -ENABLE_NAME {} -ENABLE_ACTIVE high]]
cnn_try {/cnn} -START_FLAG start
cnn_try {/cnn} -READY_FLAG ready
cnn_try {/cnn} -DONE_FLAG done

# ---------------- Architecture, ordonnancement, RTL ----------------
go assembly
# Arret ici pour l'exploration des directives (ExplorationHLS/) : elle source ce script avec
# CNN_STOP_AT = assembly, sauve le projet "neutre" (aucune directive de boucle ni de memoire) puis
# branche une solution par candidat (solution new -state assembly). Sans cette variable : rien ne change.
if {[info exists ::CNN_STOP_AT] && $::CNN_STOP_AT eq "assembly"} {
    puts "\[cnn\] CNN_STOP_AT = assembly : arret apres go assembly"
    return
}
if {$DIRECTIVES_FILE ne ""} {
    puts "\[cnn\] directives lues dans $DIRECTIVES_FILE"
    source [file join $ROOT $DIRECTIVES_FILE]
} else {
# Memoires (E-02, E-03). Chemins : bloc = /cnn/<bloc>/core/<tableau>:rsc ; canal du top = /cnn/<canal>:cns
# (variantes essayees par cnn_try). Directives de boucles (pipeline, deroulage) : ExplorationHLS.
if {$DUAL_PORT} {
    foreach {blk arr} {layer1 image2  layer2 image4  layer3 image6} {
        cnn_try [list /cnn/$blk/core/$arr:rsc /$blk/core/$arr:rsc /cnn/$blk/$arr:rsc] -MAP_TO_MODULE $DP_RAM
    }
}
foreach ch {pool1_chan pool2_chan} {
    cnn_try [list /cnn/$ch:cns /cnn/$ch:rsc] -STAGE_REPLICATION $CHAN_STAGES
    if {$DUAL_PORT} {
        cnn_try [list /cnn/$ch:cns /cnn/$ch:rsc] -MAP_TO_MODULE $DP_RAM
    }
}
}
go architect
go allocate
go extract
project save      ;# hls/work/Catapult_N.ccs : rechargeable par " project load " sans refaire go analyze

# ---------------- Verification SCVerify ----------------
# 1) C++ seul, dans l'environnement SCVerify (rapide) ; 2) RTL VHDL sous Questa, compare au C++
# NB : un echec de make n'interrompt PAS le script (simple " Error: " dans le log) : relire le log.
# Bandeau date avant chaque etape, pour savoir ou en est le script en lisant le log.
proc etape {msg} {
    puts "\n========== \[[clock format [clock seconds] -format %H:%M:%S]\] $msg =========="
    flush stdout
}

etape "SCVerify 1/3 : generation des Makefiles et du banc (scverify/)"
flow run /SCVerify
etape "SCVerify 2/3 : simulation du C++ seul (g++ + SystemC OSCI)"
flow run /SCVerify/launch_make ./scverify/Verify_orig_cxx_osci.mk {} SIMTOOL=osci sim
etape "SCVerify 3/3 : compilation du banc RTL VHDL pour Questa (build, sans simulation)"
flow run /SCVerify/launch_make ./scverify/Verify_rtl_vhdl_msim.mk {} SIMTOOL=msim build
source [file join $HLS cnn_report.tcl]     ;# cnn_report, cnn_sim_env, cnn_sim_cmd...
if {$RUN_RTL_SIM} {
    etape "SCVerify RTL : simulation Questa de $TB_IMAGES image(s) (long : ~46 M cycles par image)"
    # Compteur de cycles : lignes [sim] cycle ... / ... (%) | image | vitesse | reste (hls/sim_progress.tcl)
    cnn_sim_env $TB_IMAGES
    flow run /SCVerify/launch_make ./scverify/Verify_rtl_vhdl_msim.mk {} SIMTOOL=msim \
        QuestaSIM_MSIM_DOFILE=[file join $HLS sim_progress.tcl] QuestaSIM_SUPPRESS_WAVEFORMS=true sim
} else {
    etape "SCVerify RTL : simulation non lancee (RUN_RTL_SIM = 0), commande affichee plus bas"
}
etape "SCVerify termine : chercher 'Error' dans le log ci-dessus pour verifier"

# ---------------- Rapports (sans GUI) : hls/cnn_report.tcl ----------------
cnn_report                  ;# hls/rapports/<solution>_<date>/ : rapports bruts + resume.md
cnn_sim_cmd $TB_IMAGES      ;# commande shell de la simulation RTL

# ---------------- Exploration des directives (partie D) : a taper dans le shell Catapult ----------------
# Une nouvelle solution repart d'un etat de la solution active, SANS refaire go analyze (17 min) :
#     solution new -state assembly                ;# -> cnn.v2, branchee a l'etat assembly de cnn.v1
#     directive set /cnn/layer2/core/<boucle> -PIPELINE_INIT_INTERVAL 1   ;# boucles nommees : MAC_N, CONV_COL...
#     go extract
#     cnn_report                                  ;# rapports + resume.md dans hls/rapports/
#     cnn_summary                                 ;# tableau comparatif de toutes les solutions
# Noms exacts des boucles : colonne " Boucle " de resume.md, ou section " Loops " de cycle.rpt.
# Session fermee : catapult -shell (dans hls/work/), puis
#     project load Catapult_1.ccs ; source ../cnn_report.tcl ; solution select cnn.v1
