cmake_minimum_required(VERSION 3.10)

project(IntegArchi CXX)

# Release par défaut (le CNN est ~10x plus lent en Debug)
# Debug : cmake -DCMAKE_BUILD_TYPE=Debug ..
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

#set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Werror -Wconversion")

# Formats ac_fixed : cpp/config.hpp, ou à la compilation :
#   cmake -DCMAKE_CXX_FLAGS="-DCONV1_W=12 -DCONV1_I=6" ..

# utils.cpp ne contient que des templates : il est inclus par utils.hpp
# et n'est pas compilé à part.
# Coefficients : ROM compilées (coeffs_k5.hpp, ou coeffs_k3.hpp avec -DKS=3)
#   cmake -DCMAKE_CXX_FLAGS="-DKS=3" ..
# AC datatypes : #include <ac_fixed.h> -> copie hls/include/ (sous Catapult : celle de l'outil)
include_directories(${CMAKE_SOURCE_DIR}/../hls/include)
# ac_channel.h minimal (le vrai vient de Catapult) ; APRÈS hls/include, qui a priorité s'il contient le vrai
include_directories(${CMAKE_SOURCE_DIR}/../hls/stub)

add_executable(main ./main.cpp ./cnn.cpp ./read_image.cpp)

# Même programme avec les ROM de synthèse (coeffs_k*_raw.hpp, entiers quantifiés) : make nonreg vérifie
# qu'il donne les mêmes scores au bit près. Regénérer ces ROM après un changement de formats : make coeffs
add_executable(main_raw ./main.cpp ./cnn.cpp ./read_image.cpp)
target_compile_definitions(main_raw PRIVATE CNN_ROM_RAW)

# Testbench HLS (hls/tb_hls.cpp) compilé sans Catapult : hls/stub/ remplace mc_scverify.h
#   CNN_TB_N=5 cpp/build/tb_hls      (compare aux scores de hls/ref/)
add_executable(tb_hls ../hls/tb_hls.cpp ./cnn.cpp ./read_image.cpp)
target_include_directories(tb_hls PRIVATE ${CMAKE_SOURCE_DIR}/../hls/stub)

# Racine du dépôt, pour trouver data/ quel que soit le dossier de lancement
target_compile_definitions(main   PRIVATE "PROJECT_ROOT=\"${CMAKE_SOURCE_DIR}/..\"")
target_compile_definitions(main_raw PRIVATE "PROJECT_ROOT=\"${CMAKE_SOURCE_DIR}/..\"")
target_compile_definitions(tb_hls PRIVATE "PROJECT_ROOT=\"${CMAKE_SOURCE_DIR}/..\"")
