#pragma once
#include "fd.hpp"
#include <string>

Fd open_uart(const char* dev, int baud);
void set_nodelay(int fd);
int make_server(const std::string& host, int port);