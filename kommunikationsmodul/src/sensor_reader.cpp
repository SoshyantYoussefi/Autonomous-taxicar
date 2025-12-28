#include "sensor_reader.hpp"
#include "log.hpp"
#include <unistd.h>
#include <cerrno>
#include <vector>
#include <opcodes.h>
using namespace std;

SensorReader::SensorReader(Fd &sensor_fd, SharedState &st, StyrWriter &sw)
    : sensor_(sensor_fd), st_(st), styrw_(sw) {}

void SensorReader::start() { thr_ = std::thread(&SensorReader::run, this); }
void SensorReader::join()
{
    if (thr_.joinable())
        thr_.join();
}

void SensorReader::run()
{
    std::vector<uint8_t> buf(128);
    bool have_prev = false;
    uint8_t prev = 0;
    auto last_pulse_time = std::chrono::steady_clock::now();
    constexpr double SPEED_TIMEOUT_SEC = 0.5; // if no pulse in 0.5s, speed = 0

    while (!st_.global_stop.load())
    {
        // Check if we should reset speed to 0 (car is still)
        auto now = std::chrono::steady_clock::now();
        double time_since_pulse = std::chrono::duration<double>(now - last_pulse_time).count();
        if (time_since_pulse > SPEED_TIMEOUT_SEC && st_.speed_mps.load() > 0.0)
        {
            st_.speed_mps.store(0.0);
        }

        if (!sensor_)
        {
            std::this_thread::sleep_for(std::chrono::seconds(1));
            continue;
        }

        ssize_t r = ::read(sensor_.get(), buf.data(), buf.size()); // blocking

        // för att ta emot opcode från sensorn
        if (r >= 2)
        {
            uint8_t opCode = buf[0];
            uint8_t data = buf[1];
            // LOG_INFO("Received sensor data over UART: opcode=0x"
            //          << std::hex << int(opCode)
            //          << " data=0x" << int(data));

            if (opCode == Opcode::OPCODE_ULTRASONIC)
            {
                LOG_INFO("Received ULTRA over UART: opcode=0x"
                         << std::hex << int(opCode)
                         << " data=0x" << int(data));

                if (!have_prev || data != prev)
                {
                    prev = data;
                    have_prev = true;

                    if (data == 1)
                    {
                        st_.obstacle_stop.store(1);
                        // for obstacle stop
                        styrw_.enqueue_sw_message(static_cast<uint8_t>(Opcode::OPCODE_OBSTACLE_STOP), 0x01);
                    }
                    else if (data == 0)
                    {
                        st_.obstacle_stop.store(0);
                        styrw_.enqueue_sw_message(static_cast<uint8_t>(Opcode::OPCODE_OBSTACLE_STOP), 0x00);
                    }
                    else
                    {
                        // ignore other bytes
                        continue;
                    }
                    styrw_.request_send_now(); // trigger exactly once per change
                }
            }
            else if (opCode == Opcode::OPCODE_HALL)
            {
                static auto last_time = std::chrono::steady_clock::now();
                static unsigned long total_pulses = 0;

                auto now = std::chrono::steady_clock::now();
                double dt = std::chrono::duration<double>(now - last_time).count();
                last_time = now;
                last_pulse_time = now; // update for speed timeout tracking

                if(st_.reset_distance.load()) {
                    total_pulses = 0;
                    st_.reset_distance.store(false);
                }
                else{
                    total_pulses++;
                }
                // inte solklar
                constexpr double WHEEL_CIRCUMFERENCE = 0.24;

                double distance = total_pulses * WHEEL_CIRCUMFERENCE;
                double speed = (dt > 0.0) ? (WHEEL_CIRCUMFERENCE / dt) : 0.0;

                st_.distance_m.store(distance);
                st_.speed_mps.store(speed);

                LOG_INFO("HALL: pulses=" << total_pulses
                                          << " dist=" << distance << " m"
                                          << " speed=" << speed << " m/s");
            }
            else if (opCode == Opcode::OPCODE_HALL_SPEED)
            {
                double speed = static_cast<double>(data) / 100.0; // AVR sends speed*100
                st_.speed_mps.store(speed);
                LOG_INFO("Received HALL_SPEED: " << speed << " m/s");
            }
        }
        else if (r == 0)
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        else
        {
            if (errno == EINTR)
                continue;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }
}
