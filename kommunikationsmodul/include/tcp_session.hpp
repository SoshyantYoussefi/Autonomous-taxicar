#pragma once
#include "shared_state.hpp"
#include "styr_writer.hpp"
#include "sensor_writer.hpp"
#include "bitmask.hpp"
#include <atomic>
#include <mutex>
#include <string>

class TcpSession {
public:
    TcpSession(int fd, SharedState& st, StyrWriter& uw, SensorWriter& sw);
    void run();

private:
    void rx_loop();
    void tx_loop();
    bool handle_command(const uint8_t& cmd);

    int fd_;
    SharedState& st_;
    StyrWriter& styrw_;
    SensorWriter& sensorw_;
    std::atomic<bool> stop_{false};
    std::mutex send_mx_;
};
