cmake_minimum_required(VERSION 3.13)
project(kommunikationsmodul)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_compile_options(-O2 -Wall -Wextra -Wpedantic)

# Add include path for headers inside kommunikationsmodul/include
include_directories(${CMAKE_SOURCE_DIR}/include)

# Add include path for ../common so #include "opcodes.h" works
include_directories(${CMAKE_SOURCE_DIR}/../common)

add_executable(kommunikationsmodul
    src/main.cpp
    src/uart.cpp    
    src/styr_writer.cpp
    src/tcp_session.cpp
    src/sensor_reader.cpp
    src/styr_reader.cpp
    src/sensor_writer.cpp

    # Optional: list header so IDEs show it as part of the target (not required)
    ${CMAKE_SOURCE_DIR}/../common/opcodes.h
)

target_link_libraries(kommunikationsmodul
    pthread
)
