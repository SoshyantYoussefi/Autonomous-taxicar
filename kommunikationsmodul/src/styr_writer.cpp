//Borde heta styr writer 
#include "styr_writer.hpp"
#include "bitmask.hpp"
#include "log.hpp"
#include <sys/uio.h>
#include <termios.h>
#include <unistd.h>
#include <cstdio>
#include <opcodes.h>

StyrWriter::StyrWriter(Fd& styr_fd, SharedState& s)
    : styr_(styr_fd), st_(s), last_offset_angle_(0) {}

void StyrWriter::start() { thr_ = std::thread(&StyrWriter::run, this); }

void StyrWriter::stop() {
    {
        std::lock_guard<std::mutex> lk(mx_);
        stop_ = true;
        dirty_ = true;
    }
    cv_.notify_one();
    if (thr_.joinable()) thr_.join();
}

//Kan bytas ut mot enqueue_sw_message senare kanske men blir jobbigt
void StyrWriter::request_send_now() {
    //auto cur2 = st_.current_mask.load();
    st_.desired_mask.store(st_.current_mask.load());
    {
        std::lock_guard<std::mutex> lk(mx_);
        dirty_ = true;
    }
    cv_.notify_one();
}

void StyrWriter::enqueue_sw_message(uint8_t opcode, uint8_t data){
    {
    std::lock_guard<std::mutex> lk(mx_);
    queue_.push_back({opcode,data});
    dirty_ = true;
    }
    cv_.notify_one();
}

//sosh kod kan bytas ut mot enqueue_sw_message
void StyrWriter::notify_new_offset() {
    std::lock_guard<std::mutex> lk(mx_);
    dirty_ = true;
    cv_.notify_one();
}

void StyrWriter::run() {
    std::unique_lock<std::mutex> lk(mx_);
    while (!stop_) {
        cv_.wait(lk, [&]{ return dirty_ || stop_; });
        if (stop_) break;
        dirty_ = false;
        
        std::deque<std::pair<uint8_t,uint8_t>> local_queue;
        local_queue.swap(queue_);   // flytta allt till lokal kö

        lk.unlock();

        //Lallgi writer
        if (styr_){ 
            bool sentAnythingYet = false;

            // Kolla vilken typ av stop vi har
            bool big  = st_.big_stop_flag.exchange(false);
            bool small = !big && st_.stop_flag.exchange(false);  // kör bara small om inte big

            if (big || small) {
                uint8_t frame[2] = {
                    static_cast<uint8_t>(Opcode::OPCODE_CAM_STOP),
                    0x00
                };
                ::write(styr_.get(), frame, 2);
                tcdrain(styr_.get());

                if (big) {
                    LOG_INFO("CAMERA BIGSTOP sent to STYR");
                    // ingen auto-resume
                    st_.on_a_route.store(false);
                    resume_pending_.store(false);
                } else {
                    LOG_INFO("CAMERA SMALLSTOP sent to STYR");
                    // auto-resume efter 5s
                    resume_time_ = std::chrono::steady_clock::now() + std::chrono::seconds(5);
                    resume_pending_.store(true);
                }

                sentAnythingYet = true;
            }

            // Start after stop
            if (resume_pending_.load() &&
                std::chrono::steady_clock::now() >= resume_time_) {

                uint8_t frame[2] = {
                    static_cast<uint8_t>(Opcode::OPCODE_CAM_STOP),
                    0x01
                };
                ::write(styr_.get(), frame, 2);
                tcdrain(styr_.get());
                LOG_INFO("AUTOSTART after smallstop sent to STYR");
                
                // Reset offset angle to 0 after autostart
                uint8_t frame2[2] = {
                    static_cast<uint8_t>(Opcode::OFFSET_ANGLE),
                    0x3F
                };
                ::write(styr_.get(), frame2, 2);
                tcdrain(styr_.get());
                LOG_INFO("RESET OFFSET ANGLE to 0x35 after AUTOSTART");

                resume_pending_.store(false);
                sentAnythingYet = true;
            }

            if (sentAnythingYet) {
                lk.lock();
                continue;
            }

            for (auto &cmd : local_queue) {
                uint8_t opcode = cmd.first;
                uint8_t data   = cmd.second;

                uint8_t frame[2] = { opcode, data };
                
                ssize_t wr = ::write(styr_.get(), frame, 2);
                if (wr != 2) perror("UART write");
                tcdrain(styr_.get());
                LOG_INFO("Sent QUEUED CMD to STYR: opcode=0x"
                         << std::hex << int(opcode)
                         << " data=0x" << int(data));

                if (opcode == static_cast<uint8_t>(Opcode::OPCODE_CAM_STOP)) {
                    
                    uint8_t frame2[2] = {
                        static_cast<uint8_t>(Opcode::OFFSET_ANGLE),
                        0x3F
                    };
                    ::write(styr_.get(), frame2, 2);
                    tcdrain(styr_.get());
                    LOG_INFO("RESET OFFSET ANGLE to 0x35 after NORMALSTART");
                    sentAnythingYet = true;
                }
            }

            //write offset angle if new
            if (st_.offset_angle_needs_update.load(std::memory_order_relaxed)) {          

                uint8_t new_offset = st_.offset_angle.load(std::memory_order_relaxed);
                st_.offset_angle_needs_update.store(false, std::memory_order_relaxed);

                if (new_offset != last_offset_angle_) {
                    last_offset_angle_ = new_offset;

                    uint8_t frame[2] = {
                    static_cast<uint8_t>(Opcode::OFFSET_ANGLE),
                    new_offset
                    };

                    ssize_t wr = ::write(styr_.get(), frame, 2);
                    //if (wr != 2) perror("UART write offset");
                    tcdrain(styr_.get());
                    //LOG_INFO("Sent OFFSET ANGLE to STYR: 0x" << std::hex << int(new_offset));

                    //LOG_INFO("Sent OFFSET ANGLE to STYR: 0x"
                        //  << std::hex << int((Opcode::OFFSET_ANGLE))
                        //  << " data=0x" << int(new_offset));
                    sentAnythingYet = true;
                }
                sentAnythingYet = true;
            }
            //Write desired mask if manual command
            if(!sentAnythingYet) {
                //uint8_t out;
                uint8_t current = st_.desired_mask.load();

                if(st_.obstacle_stop.load()){
                    if(current & bit(Bit::Fram)){
                        current = bit(Bit::Stop);
                    }
                }
                
                uint8_t frame2[2] = {
                static_cast<uint8_t>(Opcode::MOVE_COMMAND),
                current
                };

                ssize_t wr = ::write(styr_.get(), frame2, 2);
                if (wr != 2) perror("UART write");
                tcdrain(styr_.get());
                LOG_INFO("Sent MOVE COMMAND to STYR: 0x" << std::hex << int(current));
            }    

        }

        lk.lock();
    }
}