# ==========================================================================
#  Procedures Tcl de recuperation des resultats Catapult SANS GUI (source par hls/cnn.tcl).
#  Apres " project load " dans une nouvelle session : source ../cnn_report.tcl  (depuis hls/work/)
#
#    cnn_report    copie rtl.rpt, cycle.rpt, messages.txt, directives.tcl, sim.log, catapult.log de la
#                  solution active dans hls/rapports/<solution>_<date>/ et y ecrit resume.md
#                  (hls/catapult_report.py : latence, surface, memoires, boucles, verdict SCVerify)
#    cnn_summary   resume de TOUTES les solutions du projet (tableau comparatif), sans rien copier
#    cnn_sim_cmd   affiche la commande shell de la simulation RTL en tache de fond (hls/sim_rtl.sh,
#                  avec compteur de cycles hls/sim_progress.tcl)
#    cnn_sim_env   pose les variables du compteur de cycles (pour une simulation lancee DANS Catapult)
# ==========================================================================

set CNN_HLS  [file normalize [file dirname [info script]]]     ;# dossier hls/ du depot
set CNN_ROOT [file dirname $CNN_HLS]

# Dossier de la solution active (ex. hls/work/Catapult_1/cnn.v2) ; repli : le plus recent.
proc cnn_solution_dir {} {
    if {![catch {utility path hard [solution get /SOLUTION_DIR]} d] && [file isdirectory $d]} {
        return [file normalize $d]
    }
    set best ""; set t 0
    foreach d [glob -nocomplain -type d [file join [pwd] Catapult* *.v*]] {
        if {[file mtime $d] > $t} { set t [file mtime $d]; set best $d }
    }
    return $best
}

# Dossier de solution, ou "" avec un message s'il n'y en a pas (sinon le script Python fouillerait le dossier courant)
proc cnn_require_solution {} {
    set sol [cnn_solution_dir]
    if {$sol eq "" || ![file exists [file join $sol rtl.rpt]]} {
        puts "*** Pas de solution Catapult avec rtl.rpt (go extract fait ?) dans [pwd]"
        return ""
    }
    return $sol
}

# 2>@1 : le message de progression du script (stderr) ne doit pas etre pris pour une erreur par exec
proc cnn_report {} {
    global CNN_HLS
    set sol [cnn_require_solution]
    if {$sol eq ""} { return }
    if {[catch {exec python3 [file join $CNN_HLS catapult_report.py] --save [file join $CNN_HLS rapports] $sol 2>@1} out]} {
        puts "*** catapult_report.py a echoue (python3 absent ?) :\n$out"
    } else {
        puts $out
    }
}

proc cnn_summary {} {
    global CNN_HLS
    set sol [cnn_require_solution]
    if {$sol eq ""} { return }
    if {[catch {exec python3 [file join $CNN_HLS catapult_report.py] [file dirname $sol] 2>@1} out]} {
        puts "*** catapult_report.py a echoue :\n$out"
    } else {
        puts $out
    }
}

# Variables lues par hls/sim_progress.tcl (compteur de cycles) : latence et horloge tirees de rtl.rpt
proc cnn_sim_env {{n_images 1} {step 100000}} {
    global CNN_ROOT
    set sol [cnn_require_solution]
    set lat 0; set clk 10.0
    if {![catch {open [file join $sol rtl.rpt]} f]} {
        set txt [read $f]; close $f
        regexp {Design Total:\s+\d+\s+(\d+)} $txt -> lat
        regexp {Clock period or pin-to-reg delay constraint \(\w+\)\s*:\s*([0-9.]+)} $txt -> clk
    }
    set ::env(CNN_ROOT)        $CNN_ROOT
    set ::env(CNN_TB_N)        $n_images
    set ::env(CNN_CLOCK_NS)    $clk
    set ::env(CNN_SIM_LATENCY) $lat
    set ::env(CNN_SIM_CYCLES)  [expr {wide($lat) * $n_images}]
    set ::env(CNN_SIM_STEP)    $step
    puts "cnn_sim_env : $n_images image(s), latence $lat cycles, horloge $clk ns"
}

proc cnn_sim_cmd {{n_images 1}} {
    global CNN_HLS
    set sol [cnn_require_solution]
    if {$sol eq ""} { return }
    puts "\n=== Simulation RTL avec compteur de cycles, a lancer depuis un shell (tache de fond) ==="
    puts "nohup $CNN_HLS/sim_rtl.sh $sol $n_images > $sol/sim_rtl.out 2>&1 &"
    puts "tail -f $sol/sim_rtl.out | grep --line-buffered -E '\\\[sim|PASSED|FAILED|Error|image '"
    puts "# a la fin, les rapports et resume.md sont copies dans $CNN_HLS/rapports/\n"
}
