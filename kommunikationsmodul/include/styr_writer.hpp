#pragma once
#include "fd.hpp"
#include "shared_state.hpp"
#include <condition_variable>
#include <mutex>
#include <thread>
#include <deque>

class StyrWriter {
public:
    StyrWriter(Fd& styr_fd, SharedState& s);
    void start();
    void stop();
    void request_send_now();
    void notify_new_offset();
    void enqueue_sw_message(uint8_t opcode, uint8_t data);

private:
    void run();
    void update_offset_angle(uint8_t new_offset);

    Fd& styr_;
    SharedState& st_;
    std::thread thr_;
    std::condition_variable cv_;
    std::mutex mx_;
    bool dirty_ = false;
    bool stop_  = false;
    uint8_t last_offset_angle_ = 0;

    std::deque<std::pair<uint8_t,uint8_t>> queue_;

    // For stop
    std::chrono::steady_clock::time_point resume_time_;
    std::atomic<bool> resume_pending_{false};
};
