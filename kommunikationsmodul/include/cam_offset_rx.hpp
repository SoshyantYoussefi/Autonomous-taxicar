#pragma once
#include <thread>
#include <atomic>
#include <cstdint>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <cstring>
#include "shared_state.hpp"
#include "log.hpp"
#include <functional> 

class CamOffsetRx {
public:
    explicit CamOffsetRx(SharedState& st, std::function<void()> on_offset_cb = {})
    : st_(st), on_offset_cb_(std::move(on_offset_cb)) {}
    //explicit CamOffsetRx(SharedState& st) : st_(st) {}
    void start() { thr_ = std::thread(&CamOffsetRx::run, this); }

private:
    void run() {
        // 1) Skapa UNIX DGRAM-socket
        int fd = ::socket(AF_UNIX, SOCK_DGRAM, 0);
        if (fd < 0) { perror("socket"); return; }

        // 2) Adress + bind
        sockaddr_un addr{}; 
        addr.sun_family = AF_UNIX;
        std::strcpy(addr.sun_path, "/tmp/cam_offset.sock");
        ::unlink(addr.sun_path);  // ta bort ev. gammal
        if (::bind(fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
            perror("bind");
            ::close(fd);
            return;
        }

        LOG_INFO("CamOffsetRx: lyssnar på " << addr.sun_path);

        uint8_t angle; 
        while (true) {
            // 3) Blockerande read på 1 byte
            ssize_t n = ::recv(fd, &angle, sizeof(angle), 0);
            if (n == 1) {
                // smallSTOP condition (0xFF)
                if (angle == 0xFF) {
                    LOG_INFO("received SMALLSTOP from cam (FF)");

                    // Only trigger once per stop event
                    if (!st_.stop_flag.exchange(true)) {  
                        if (on_offset_cb_) on_offset_cb_();
                    }
                    continue;   // skip angle processing
                }
                // bigstop condition (0xFE)
                else if (angle == 0xFE) {
                    LOG_INFO("received BIGSTOP from cam (FE)");
                    
                    if (!st_.big_stop_flag.exchange(true)) {  
                        if (on_offset_cb_) on_offset_cb_();
                    }
                    continue;   // skip angle processing
                }

                //print if angle är FF
                uint8_t val7 = angle & 0x7F;

                st_.offset_angle.store(val7, std::memory_order_relaxed);
                st_.offset_angle_needs_update.store(true, std::memory_order_relaxed);
               //LOG_INFO("Mottog cam angle (7bit): " << int(val7));

               if (on_offset_cb_) on_offset_cb_();
            }
        }
        // (ingen clean shutdown här; processen avslutar ändå och /tmp-socket försvinner)
    }

    SharedState& st_;
    std::thread  thr_;
    std::function<void()> on_offset_cb_;
};
