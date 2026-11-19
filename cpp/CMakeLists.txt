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
add_executable(main ./main.cpp ./cnn.cpp ./extract_coeff.cpp ./read_image.cpp)

# Racine du dépôt, pour trouver data/ quel que soit le dossier de lancement
target_compile_definitions(main PRIVATE "PROJECT_ROOT=\"${CMAKE_SOURCE_DIR}/..\"")
