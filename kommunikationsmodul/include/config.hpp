#pragma     once
#include <string>

struct Config {
    std::string sensor_dev = "/dev/ttyS0";
    int         sensor_baud   = 115200;
    int         port    = 5000;
    std::string styr_dev = "/dev/ttyS0";
    int         styr_baud   = 115200;
    std::string host = "0.0.0.0";
};