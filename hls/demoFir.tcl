// This script launch the Demo FIR on catapult 

// Add files 
solution file add ./Demo_FIR/FIR_SIMPLE.cpp
solution file add ./Demo_FIR/FIR_TYPES.h
solution file add ./Demo_FIR/FIR_TESTBENCH.cpp -exclude true
solution file add ./Demo_FIR/COEFFS_DOUBLE.h
solution file add ./Demo_FIR/FIR_SIMPLE_REFERENCE.cpp

// Create Hierachy
go analyze
// verify the TOP level is right but that is all

// compile
go compile

// set techno 
solution library add mgc_Xilinx-ARTIX-7-2L_beh -- -rtlsyntool Precision -manufacturer Xilinx -family ARTIX-7 -speed -2L -part xc7a12tcsg325-2L
go libraries

// some configuration 
// colck 
directive set -CLOCKS {clk {-CLOCK_PERIOD 10 -CLOCK_EDGE rising -CLOCK_HIGH_TIME 5 -CLOCK_OFFSET 0.000000 -CLOCK_UNCERTAINTY 0.0 -RESET_KIND sync -RESET_SYNC_NAME rst -RESET_SYNC_ACTIVE high -RESET_ASYNC_NAME arst_n -RESET_ASYNC_ACTIVE low -ENABLE_NAME {} -ENABLE_ACTIVE high}}

directive set /FIR_HARDWARE -START_FLAG start
directive set /FIR_HARDWARE -READY_FLAG ready
directive set /FIR_HARDWARE -DONE_FLAG done


// Architecture 
go assembly

// set unroll on MAC for example 
directive set /FIR_HARDWARE/core/MAC -UNROLL yes
//directive set /FIR_HARDWARE/core/MAC -UNROLL 5
// set pipeline 
// directive set /FIR_HARDWARE/core/MAC -PIPELINE_INIT_INTERVAL 1
// directive set /FIR_HARDWARE/core/MAC -PIPELINE_STALL_MODE flush
// directive set /FIR_HARDWARE/core/MAC -PIPELINE_STALL_MODE bubble
// directive set /FIR_HARDWARE/core/MAC -PIPELINE_STALL_MODE stall
// directive set /FIR_HARDWARE/core/MAC -MERGEABLE false


// Ressources 
go architect

// schedule 
go allocate


// RTL 
go extract

// power repport 
go switching
flow run /PowerAnalysis/report_pre_pwropt_Verilog
flow run /PowerAnalysis/report_pre_pwropt_VHDL

// Power RTL
go power

// simulation 
go extract
// without the interface 
flow run /SCVerify/launch_make ./scverify/Verify_rtl_vhdl_msim.mk {} SIMTOOL=msim sim
// whit interface 
flow run /SCVerify/launch_make ./scverify/Verify_rtl_vhdl_msim.mk {} SIMTOOL=msim simgui
