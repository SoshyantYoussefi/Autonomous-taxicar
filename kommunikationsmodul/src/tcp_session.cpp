#include "tcp_session.hpp"
#include "bitmask.hpp"
#include "uart.hpp"
#include "log.hpp"
#include <sys/socket.h>
#include <unistd.h>
#include <cstdio>
#include <opcodes.h>
#include "CppToPyArrayTx.hpp"
#include <vector>
#include "path_algoritm.cpp"
//#include <move_data.json>

TcpSession::TcpSession(int fd, SharedState& st, StyrWriter& sw, SensorWriter& sensw)
    : fd_(fd), st_(st), styrw_(sw), sensorw_(sensw) {}

void TcpSession::run() {
    set_nodelay(fd_);
    LOG_INFO("Klient ansluten");
    std::thread rx(&TcpSession::rx_loop, this);
    std::thread tx(&TcpSession::tx_loop, this);
    rx.join(); tx.join();
    ::close(fd_);
    LOG_INFO("Klient frånkopplad");
}

//helper
static bool recv_exact(int fd, uint8_t* buf, size_t len) {
    size_t off = 0;
    while (off < len) {
        ssize_t r = ::recv(fd, buf + off, len - off, 0);
        if (r <= 0) {
            return false;
        }
        off += (size_t)r;
    }
    return true;
}


//receive from gui loop
void TcpSession::rx_loop() {
    CppToPyArrayTx array_tx("/tmp/cpp_to_py.sock");
    
    uint8_t opcode_byte = 0;
    uint8_t data_byte   = 0;
    size_t bytes_read   = 0;   // how many bytes of the current 2-byte frame we have

    while (!stop_) {
        // Read one byte at a time into the frame
        ssize_t r = ::recv(fd_,(bytes_read == 0 ? &opcode_byte : &data_byte), 1, 0);

        if (r <= 0) {
            break; // error or disconnect
        }

        bytes_read += r;

        // If we don't yet have both bytes, continue receiving
        if (bytes_read < 2)
            continue;

        // Now we have a complete (opcode, data) pair
        Opcode op = static_cast<Opcode>(opcode_byte);
        uint8_t data = data_byte;

        // Reset for the next frame
        bytes_read = 0;

        if(op == Opcode::VAXLING){
            st_.on_a_route.store(false);
            st_.reset_distance.store(true);
        }

        // Handle opcode
        if (op == Opcode::MOVE_COMMAND) {
            LOG_INFO("Rörelse från GUI: " << int(data));
            handle_command(data);
        }
        //alg stop
        else if (op == 0x41){
            styrw_.enqueue_sw_message(0xFF, 0x00);
            st_.on_a_route.store(false);
        }
        //alg start
        else if (op == 0x40){
            uint8_t length = data;   // total number of bytes to receive
            if (length == 0 || length % 2 != 0) {
                LOG_INFO("Invalid payload length for string array");
                continue;
            }

            // --- receive the full payload ---
            std::vector<uint8_t> payload(length);
            if (!recv_exact(fd_, payload.data(), length)) {
                stop_ = true;
                break;
            }

            size_t count = length / 2;
            if (count > 10) count = 10;

            std::vector<std::string> elems;
            elems.reserve(count);

            for (size_t i = 0; i < count; i++) {
                char c1 = payload[2*i];
                char c2 = payload[2*i + 1];
                elems.emplace_back(std::string() + c1 + c2);
            }

            // Debug print
            // for (auto &s : elems) {
            //     LOG_INFO("Received 2-byte string: " << s);
            // }
            
            std::vector<string> turns = full_algo(elems);

            vector<uint8_t> byte_turns;
            byte_turns.reserve(turns.size());
            LOG_INFO("TURNS:")
            for (const auto& s : turns) {
                LOG_INFO(" " << s << " ")
                byte_turns.push_back((uint8_t)s[0]);
            }

            //LOG_INFO("SKCIAKAR ARRAY")
            st_.on_a_route.store(true);
            st_.reset_distance.store(true);
            styrw_.enqueue_sw_message(0xFF, 0x01);
            array_tx.send_array(byte_turns.data(), turns.size());
        }
        else if (op == Opcode::OPCODE_SET_ULTRA_DIST) {
            sensorw_.enqueue_ultra_distance(data);
        }
        else if (op != Opcode::MOVE_COMMAND) {
            //LOG_INFO("Växling från GUI: " << int(data));
            //styrw_.request_send_now(); 
            styrw_.enqueue_sw_message(op, data);
        }
        else{
            //LOG_WARN("Okänt opcode från GUI: " << static_cast<int>(op));
            stop_ = true;
            break;
        }
    }
    stop_ = true;
}


// Send to gui, ska nog ändras sen
void TcpSession::tx_loop() {
    int seq = 0;
    double distance_m = 0.0;
    int tick = 0;

    while (!stop_) {
        double speed_mps = st_.speed_mps.load();
        double current_dist = st_.distance_m.load();

        if (current_dist != distance_m) {
            distance_m = current_dist;
            tick = 0;              // rörelse -> börja om
        } else {
            if (tick < 20) {
                tick++;            // räkna upp tills vi nått 
            }
        }

        if (tick >= 20) {
            speed_mps = 0.0;       // efter 2 s utan rörelse -> visa 
        }

        char line[256];
        int n = std::snprintf(line, sizeof(line),
                              "{\"speed\":%.3f,\"ultrasound\":%d,\"distance\":%.3f}\n",
                              speed_mps,
                              st_.obstacle_stop.load(),
                              distance_m);

        std::lock_guard<std::mutex> lk(send_mx_);
        if (::send(fd_, line, n, 0) <= 0) { stop_ = true; break; }
        std::this_thread::sleep_for(std::chrono::milliseconds(50)); // 20 Hz
    }
}

bool TcpSession::handle_command(const uint8_t& cmd) {
    //LOG_INFO("CMD: " << cmd);
    //if (cmd == "quit") return false;

    auto set_bit = [&](Bit b) {        
        uint8_t m = st_.current_mask.load();
        m |= bit(b);
        st_.current_mask.store(m);
    };
    auto clear_bit = [&](Bit b) {
        uint8_t m = st_.current_mask.load();
        m &= ~bit(b);
        st_.current_mask.store(m);
    };
    auto request = [&] { styrw_.request_send_now(); };

    //från json fil måste fixa senare
    //stop down
    if (cmd == 9) { set_bit(Bit::Stop); request(); }
    //stop up 
    else if (cmd == 10) { clear_bit(Bit::Stop); request(); }
    //fram down
    else if (cmd == 1) {
        if (!(st_.current_mask.load() & bit(Bit::Fram))) { set_bit(Bit::Fram); request(); }
    //fram up
    } else if (cmd == 2) { clear_bit(Bit::Fram); request(); }
    //bakåt down
    else if (cmd == 3) {
        if (!(st_.current_mask.load() & bit(Bit::Fram))) { set_bit(Bit::Bakat); request(); }
    //bakåt up
    } else if (cmd == 4) { clear_bit(Bit::Bakat); request(); }
    

    //vänster down
    if (cmd == 5) {
        set_bit(Bit::Vanster); clear_bit(Bit::Hoger); request();
    //vänster up
    } else if (cmd == 6) { clear_bit(Bit::Vanster); request(); }
    //höger down
    else if (cmd == 7) {
        set_bit(Bit::Hoger); clear_bit(Bit::Vanster); request();
    //höger up
    } else if (cmd == 8) { clear_bit(Bit::Hoger); request(); }

    
    // okända kommandon ignoreras
    return true;
}
