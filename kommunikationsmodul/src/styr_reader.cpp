#include "styr_reader.hpp"
#include "log.hpp"
#include <unistd.h>
#include <cerrno>
#include <vector>
using namespace std;

StyrReader::StyrReader(Fd& styr_fd, SharedState& st, StyrWriter& sw)
    : styr_(styr_fd), st_(st), styrw_(sw) {}

void StyrReader::start() { thr_ = std::thread(&StyrReader::run, this); }
void StyrReader::join()  { if (thr_.joinable()) thr_.join(); }

void StyrReader::run() {
    std::vector<uint8_t> buf(128);

    while (!st_.global_stop.load()) {
        if (!styr_) { std::this_thread::sleep_for(std::chrono::seconds(1)); continue; }

       ssize_t r = ::read(styr_.get(), buf.data(), buf.size()); // blocking or non-blocking
        if (r >= 2) { // need at least 2 bytes for (identifier, value)
            uint8_t id  = buf[0];
            uint8_t val = buf[1];
            char cid = (char)id;
            //std::cout << "PID VALUES ---> ID: " << +cid << "  Value: " << +val << std::endl;
            LOG_INFO("Received FROM STYR: opcode=0x"
                     << std::hex << int(id)
                     << " data=0x" << int(val));
        } 
        else if (r > 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        } else {
            if (errno == EINTR) continue;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }
}
