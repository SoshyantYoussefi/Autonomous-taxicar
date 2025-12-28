#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <cstring>
#include <array>
#include <cstdint>

class CppToPyArrayTx {
public:
    CppToPyArrayTx(const char* path = "/tmp/cpp_to_py.sock") {
        fd_ = ::socket(AF_UNIX, SOCK_DGRAM, 0);
        if (fd_ < 0) {
            perror("socket cpp_to_py");
            return;
        }
        std::memset(&addr_, 0, sizeof(addr_));
        addr_.sun_family = AF_UNIX;
        std::strncpy(addr_.sun_path, path, sizeof(addr_.sun_path) - 1);
    }

    ~CppToPyArrayTx() {
        if (fd_ >= 0) ::close(fd_);
    }

    // vals[0..count-1], count <= 10
    void send_array(const uint8_t* vals, uint8_t count) {
        if (fd_ < 0) return;

        uint8_t buf[1 + count];
        buf[0] = count;
        // kopiera int16 direkt efter count
        std::memcpy(buf + 1, vals, count * sizeof(uint8_t));

        ::sendto(fd_, buf, 1 + count * sizeof(uint8_t), 0,
                 reinterpret_cast<sockaddr*>(&addr_),
                 sizeof(addr_));
    }

private:
    int fd_{-1};
    sockaddr_un addr_{};
};
