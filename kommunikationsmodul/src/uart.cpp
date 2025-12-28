#include "uart.hpp"
#include "log.hpp"

#include <arpa/inet.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <termios.h>
#include <unistd.h>
#include <fcntl.h>
#include <cerrno>
#include <cstring>

static speed_t baud_to_speed(int baud) {
    switch (baud) {
        case 9600: return B9600;
        case 19200: return B19200;
        case 38400: return B38400;
        case 57600: return B57600;
        default: return B115200;
    }
}

Fd open_uart(const char* dev, int baud) {
    int fd = ::open(dev, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) { perror("open_uart"); return {}; }

    termios tio{};
    if (tcgetattr(fd, &tio) < 0) { perror("tcgetattr"); ::close(fd); return {}; }
    cfmakeraw(&tio);
    tio.c_cflag |= (CLOCAL | CREAD);
    tio.c_cflag &= ~PARENB;
    tio.c_cflag &= ~CSTOPB;
    tio.c_cflag &= ~CSIZE;
    tio.c_cflag |= CS8;
    speed_t spd = baud_to_speed(baud);
    cfsetispeed(&tio, spd);
    cfsetospeed(&tio, spd);
    if (tcsetattr(fd, TCSANOW, &tio) < 0) { perror("tcsetattr"); ::close(fd); return {}; }

    int flags = fcntl(fd, F_GETFL);
    fcntl(fd, F_SETFL, flags & ~O_NONBLOCK);  // blocking
    tcflush(fd, TCIOFLUSH);
    return Fd(fd);
}

void set_nodelay(int fd) {
    int one = 1; setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
}

int make_server(const std::string& host, int port) {
    int srv = ::socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) { perror("socket"); return -1; }
    int one = 1; setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    sockaddr_in addr{}; addr.sin_family = AF_INET; addr.sin_port = htons(port);
    addr.sin_addr.s_addr = inet_addr(host.c_str());
    if (bind(srv, (sockaddr*)&addr, sizeof(addr)) < 0) { perror("bind"); ::close(srv); return -1; }
    if (listen(srv, 1) < 0) { perror("listen"); ::close(srv); return -1; }
    return srv;
}
