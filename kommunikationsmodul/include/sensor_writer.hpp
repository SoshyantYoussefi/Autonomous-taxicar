#pragma once
#include <thread>
#include <mutex>
#include <condition_variable>
#include <deque>
#include <stdint.h>
#include "fd.hpp"
#include "shared_state.hpp"

class SensorWriter {
public:
    SensorWriter(Fd& sens_fd, SharedState& s);
    void start();
    void stop();

    // call this when GUI updates the distance
    void enqueue_ultra_distance(uint8_t new_dist);

private:
    void run();

    Fd& sensor_;
    SharedState& st_;

    std::thread thr_;
    std::mutex mx_;
    std::condition_variable cv_;
    bool stop_ = false;
    bool dirty_ = false;

    std::deque<uint8_t> queue_; // just distances
};
