# ==========================================================================
#  Compteur de cycles pendant la simulation RTL SCVerify sous Questa (vsim), en mode batch.
#  ASCII seulement : vsim et Catapult affichent mal les accents.
#
#  Source par le script vsim de SCVerify (scverify_msim_wave.tcl) AVANT do_simulation_run, grace a
#  la variable make QuestaSIM_MSIM_DOFILE (voir cnn_sim_cmd dans hls/cnn_report.tcl). La simulation
#  avance par tranches de CNN_SIM_STEP cycles ; apres chaque tranche une ligne :
#    [sim] cycle 1200000 / 46123242 (2.6 %) | image 1/1 | 0:01:05 | 18461 cycles/s | reste ~ 0:40:31
#  Fin : quand le temps simule n'avance plus (sc_stop du testbench), on rend la main a SCVerify
#  (do_simulation_run : run -all immediat, verdict PASSED/FAILED, quit).
#
#  Variables d'environnement (posees par cnn_sim_cmd) :
#    CNN_CLOCK_NS     periode d'horloge en ns (defaut 10)
#    CNN_SIM_CYCLES   cycles attendus au total (latence x images, lue dans rtl.rpt) : %, image, temps restant
#    CNN_SIM_LATENCY  cycles par image (latence du design)
#    CNN_SIM_STEP     cycles par tranche (defaut 100000 : une ligne toutes les ~10 s a 1 min)
# ==========================================================================

if {[info exists ::cnn_progress_done]} { return }   ;# deja execute (source deux fois)
set ::cnn_progress_done 1
onbreak {resume}

proc cnn_env {name default} {
    if {[info exists ::env($name)] && $::env($name) ne ""} { return $::env($name) }
    return $default
}

# Temps simule courant en ns ($now : nombre dans l'unite de resolution, -t ps, ou "nombre unite")
proc cnn_now_ns {} {
    set t [string trim $::now]
    if {![regexp {^([0-9.eE+]+)\s*([a-z]*)$} $t -> v u]} { return -1 }
    switch -- $u {
        fs  { return [expr {$v / 1.0e6}] }
        ""  -
        ps  { return [expr {$v / 1.0e3}] }
        ns  { return [expr {double($v)}] }
        us  { return [expr {$v * 1.0e3}] }
        ms  { return [expr {$v * 1.0e6}] }
        sec -
        s   { return [expr {$v * 1.0e9}] }
    }
    return -1
}

proc cnn_hms {s} {
    if {$s < 0} { return "?" }
    set s [expr {int($s)}]
    return [format "%d:%02d:%02d" [expr {$s / 3600}] [expr {($s % 3600) / 60}] [expr {$s % 60}]]
}

proc cnn_run_with_progress {} {
    set clk     [cnn_env CNN_CLOCK_NS 10.0]
    set total   [cnn_env CNN_SIM_CYCLES 0]
    set lat     [cnn_env CNN_SIM_LATENCY 0]
    set step    [cnn_env CNN_SIM_STEP 100000]
    # garde-fou : si le testbench ne s'arrete pas, on s'arrete a 1,5 x le total attendu
    set max_cycles [expr {$total > 0 ? max(1.5 * $total, $total + 2 * $step) : 0}]
    set step_ns [expr {$step * $clk}]
    set t0      [clock seconds]

    echo [format "\[sim\] debut : horloge %s ns, %s cycles attendus, une ligne tous les %s cycles" \
              $clk [expr {$total > 0 ? $total : "?"}] $step]
    set prev [cnn_now_ns]
    while {1} {
        run $step_ns ns
        set now_ns [cnn_now_ns]
        set cyc    [expr {wide($now_ns / $clk)}]
        set wall   [expr {[clock seconds] - $t0}]
        set speed  [expr {$wall > 0 ? $cyc / double($wall) : 0}]
        set line   [format "\[sim\] cycle %d" $cyc]
        if {$total > 0} {
            append line [format " / %d (%.1f %%)" [expr {wide($total)}] [expr {100.0 * $cyc / $total}]]
        }
        if {$lat > 0 && $total > 0} {
            set n_img [expr {max(1, int(round(double($total) / $lat)))}]
            set img   [expr {min($n_img, int($cyc / $lat) + 1)}]
            append line " | image $img/$n_img"
        }
        append line " | [cnn_hms $wall] | [format %.0f $speed] cycles/s"
        if {$total > 0 && $speed > 0 && $cyc < $total} {
            append line " | reste ~ [cnn_hms [expr {($total - $cyc) / $speed}]]"
        }
        if {$now_ns <= $prev} {
            echo "\[sim\] fin : le temps simule n'avance plus (testbench termine) apres [cnn_hms $wall]"
            break
        }
        echo $line
        set prev $now_ns
        if {$max_cycles > 0 && $cyc > $max_cycles} {
            echo "\[sim\] ARRET : $cyc cycles > 1,5 x le total attendu ($total) ; DUT bloque ?"
            break
        }
    }
}

cnn_run_with_progress
