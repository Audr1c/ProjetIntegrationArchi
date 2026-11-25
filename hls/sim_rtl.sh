#!/usr/bin/env bash
# ==========================================================================
#  Simulation RTL SCVerify (Questa) d'une solution Catapult, HORS de Catapult, avec compteur de cycles.
#  Messages en ASCII (Catapult / vsim affichent mal les accents).
#
#  Usage (machine de l'ecole, en tache de fond) :
#      nohup hls/sim_rtl.sh hls/work/Catapult_1/cnn.v1 [nb_images=1] [cycles_par_ligne=100000] \
#            > hls/work/Catapult_1/cnn.v1/sim_rtl.out 2>&1 &
#      tail -f hls/work/Catapult_1/cnn.v1/sim_rtl.out | grep --line-buffered -E "\[sim\]|PASSED|FAILED|Error|image "
#
#  - latence (cycles/image) et periode d'horloge lues dans <solution>/rtl.rpt -> %, image en cours, temps restant
#  - hls/sim_progress.tcl est passe a vsim par QuestaSIM_MSIM_DOFILE (fichier utilisateur de SCVerify) ;
#    secours : ajoute directement dans scverify_msim_wave.tcl s'il existe deja sans lui
#  - QuestaSIM_SUPPRESS_WAVEFORMS=true : pas de traces (vsim.wlf), simulation plus rapide
#  - a la fin : hls/catapult_report.py --save hls/rapports <solution> (verdict SCVerify dans resume.md)
# ==========================================================================
set -o pipefail

if [ $# -lt 1 ] || [ ! -f "$1/rtl.rpt" ]; then
    echo "Usage : $0 <dossier de solution Catapult contenant rtl.rpt> [nb_images=1] [cycles_par_ligne=100000]" >&2
    exit 2
fi
SOL=$(cd "$1" && pwd)
N=${2:-1}
STEP=${3:-100000}
HLS=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HLS")

if [ -z "$CATA_HOME" ]; then
    # shellcheck disable=SC1091
    source "$HLS/bash_mentor_24"
fi

# Latence : ligne "Design Total:  <ops> <latence> <debit> ..." ; horloge : "Clock period ... (clk): 10.0"
LAT=$(grep -m1 "Design Total:" "$SOL/rtl.rpt" | awk '{print $4}')
CLK=$(grep -m1 "Clock period or pin-to-reg delay constraint" "$SOL/rtl.rpt" | awk -F: '{gsub(/ /, "", $2); print $2}')
case "$LAT" in ''|*[!0-9]*) LAT=0 ;; esac
[ -n "$CLK" ] || CLK=10.0

export MGC_HOME="$CATA_HOME" CNN_ROOT="$ROOT" CNN_TB_N="$N"
export CNN_CLOCK_NS="$CLK" CNN_SIM_LATENCY="$LAT" CNN_SIM_CYCLES=$((LAT * N)) CNN_SIM_STEP="$STEP"
echo "[sim_rtl] solution $SOL : $N image(s), latence $LAT cycles, horloge $CLK ns -> $((LAT * N)) cycles attendus"

WAVE="$SOL/scverify/rtl_vhdl_msim/scverify_msim_wave.tcl"
if [ -f "$WAVE" ] && ! grep -q sim_progress "$WAVE"; then
    sed -i "/^# If not running in GUI mode/i source $HLS/sim_progress.tcl" "$WAVE"
fi

cd "$SOL" || exit 1
"$CATA_HOME/bin/make" -f ./scverify/Verify_rtl_vhdl_msim.mk SIMTOOL=msim \
    QuestaSIM_MSIM_DOFILE="$HLS/sim_progress.tcl" QuestaSIM_SUPPRESS_WAVEFORMS=true sim
rc=$?
echo "[sim_rtl] make termine (code $rc) ; verdict :"
grep -E "Simulation (PASSED|FAILED)|error count|images identiques" "$SOL/scverify/rtl_vhdl_msim/sim.log"
python3 "$HLS/catapult_report.py" --save "$HLS/rapports" "$SOL" > /dev/null
exit $rc
