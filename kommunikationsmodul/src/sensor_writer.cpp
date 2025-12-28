#include "sensor_writer.hpp"
#include <unistd.h>
#include <termios.h>
#include <cstdio>
#include <opcodes.h>
#include <log.hpp>

SensorWriter::SensorWriter(Fd& sens_fd, SharedState& s)
    : sensor_(sens_fd), st_(s) {}

void SensorWriter::start() {
    //creates a background thread that will handle sending data to the AVR
    thr_ = std::thread(&SensorWriter::run, this);
}

void SensorWriter::stop() {
    {
        std::lock_guard<std::mutex> lk(mx_);
        stop_ = true;
        dirty_ = true;
    }
    cv_.notify_one();
    if (thr_.joinable())
        thr_.join();
}

void SensorWriter::enqueue_ultra_distance(uint8_t new_dist) {
    {
        // queues a new value
        std::lock_guard<std::mutex> lk(mx_);
        queue_.push_back(new_dist);
        dirty_ = true;
    }
    cv_.notify_one();
}

void SensorWriter::run() {
    // thread sleeps until new data arrives
    std::unique_lock<std::mutex> lk(mx_);

    while (!stop_) {
        cv_.wait(lk, [&]{ return dirty_ || stop_; });
        if (stop_) break;

        dirty_ = false;

        std::deque<uint8_t> local;
        local.swap(queue_);

        lk.unlock();

        for (uint8_t dist : local) {
            uint8_t frame[2] = {
                static_cast<uint8_t>(Opcode::OPCODE_SET_ULTRA_DIST),
                dist
            };
            LOG_INFO("Sending ultradistance");

            ssize_t wr = ::write(sensor_.get(), frame, 2);
            if (wr != 2) perror("UART write");
            tcdrain(sensor_.get());
        }

        lk.lock();
    }
}
