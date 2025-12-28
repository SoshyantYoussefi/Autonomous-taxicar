#pragma once
#include <cstdint>

enum class Bit : uint8_t {
    Fram=0xC0,
    Stop=0xA0,
    Vanster=0x90,
    Hoger=0x88,
    Bakat=0x84,
};

//Behövs detta? ja
inline uint8_t bit(Bit b) {
    return static_cast<uint8_t>(b);
}