// g++ -O2 -std=c++17 -pthread -o pi_comm pi_comm.cpp
// Kör: ./pi_comm 0.0.0.0 5000 [/dev/serial/by-id/<styr> 115200 /dev/serial/by-id/<sensor> 115200]

#include <arpa/inet.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <cstring>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>
//#include <algorithm>  
#include <cerrno>     // errno/EINTR
#include <cstdio>     // std::snprintf

#include <condition_variable>

#include <fcntl.h>
#include <termios.h>

static int open_uart(const char* dev, int baud){
    int fd = ::open(dev, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if(fd < 0){ perror("open_uart"); return -1; }

    termios tio{};
    if(tcgetattr(fd, &tio) < 0){ perror("tcgetattr"); ::close(fd); return -1; }

    cfmakeraw(&tio);
    tio.c_cflag |= (CLOCAL | CREAD);
    tio.c_cflag &= ~PARENB;
    tio.c_cflag &= ~CSTOPB;
    tio.c_cflag &= ~CSIZE;
    tio.c_cflag |= CS8;

    speed_t spd = B115200;
    switch(baud){
        case 9600: spd=B9600; break;
        case 19200: spd=B19200; break;
        case 38400: spd=B38400; break;
        case 57600: spd=B57600; break;
        case 115200: default: spd=B115200; break;
    }
    cfsetispeed(&tio, spd);
    cfsetospeed(&tio, spd);

    if(tcsetattr(fd, TCSANOW, &tio) < 0){ perror("tcsetattr"); ::close(fd); return -1; }

    int flags = fcntl(fd, F_GETFL);
    fcntl(fd, F_SETFL, flags & ~O_NONBLOCK);  // blocking
    tcflush(fd, TCIOFLUSH);
    return fd;
}

static void set_nodelay(int fd){
    int one=1; setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
}

// --- Latest-sensor-byte only --- 
std::atomic<uint8_t> g_sensor_byte{0};     // latest byte seen from sensor UART
std::atomic<bool>    g_sensor_seen{false}; // have we received anything yet?
// Motor/sensor data
std::atomic<int> g_pulses_left{0};
std::atomic<int> g_pulses_right{0};
std::atomic<int> g_distance_cm{0};
std::atomic<int> g_speed_cm_s{0};


int main(int argc, char**argv){
    std::atomic<uint8_t> current_mask{0};  // bitmask to styr AVR
    
    // ---- Single-writer UART pipeline ----
    std::atomic<uint8_t> desired_mask{0};   // latest mask we want on styr UART
    std::mutex           tx_mx;
    std::condition_variable tx_cv;
    bool tx_dirty = false;
    bool tx_stop  = false;

    // Call from ANY thread to request a UART send of the current mask
    auto request_send_mask = [&](){
        desired_mask.store(current_mask.load(std::memory_order_relaxed),
                        std::memory_order_relaxed);
        {
            std::lock_guard<std::mutex> lk(tx_mx);
            tx_dirty = true;
        }
        tx_cv.notify_one();
    };

    constexpr uint8_t BIT_FRAM=0x80;
    constexpr uint8_t BIT_STOP=0x40;
    constexpr uint8_t BIT_VANSTER=0x20;
    constexpr uint8_t BIT_HOGER=0x10;
    constexpr uint8_t BIT_BAKAT=0x08;
                
    bool dirty = false;
    
    auto set_bit   = [&](uint8_t b){ current_mask = uint8_t(current_mask.load() |  b); dirty = true; };
    auto clear_bit = [&](uint8_t b){ current_mask = uint8_t(current_mask.load() & ~b); dirty = true; };

    const char* host = (argc>1)? argv[1] : "0.0.0.0";
    int port         = (argc>2)? std::stoi(argv[2]) : 5000;

    const char* styr_dev    = (argc>3)? argv[3] : "/dev/ttyUSB0";
    int         styr_baud   = (argc>4)? std::stoi(argv[4]) : 115200;

    const char* sensor_dev  = (argc>5)? argv[5] : "/dev/ttyUSB1";
    int         sensor_baud = (argc>6)? std::stoi(argv[6]) : 115200;

    int styr_fd   = open_uart(styr_dev,   styr_baud);
    int sensor_fd = open_uart(sensor_dev, sensor_baud);

    if(styr_fd   < 0) std::cerr << "WARN: couldn't open styr-UART   " << styr_dev   << "\n";
    else              std::cout << "styr UART   open: " << styr_dev   << " @" << styr_baud   << "\n";
    if(sensor_fd < 0) std::cerr << "WARN: couldn't open sensor-UART " << sensor_dev << "\n";
    else              std::cout << "sensor UART open: " << sensor_dev << " @" << sensor_baud << "\n";

    std::atomic<bool> global_stop{false};
    //std::atomic<bool>    g_obstacle{false};     // true when sensor says 0x01
    std::atomic<int> OBSTACLE_STOP = 0;      // true when sensor says 0x01
    //std::mutex           uart_mx; 

    // ---- Dedicated UART writer thread (single owner of styr_fd) ----
    std::thread t_uart([&](){
        std::unique_lock<std::mutex> lk(tx_mx);
        while (!tx_stop) {
            tx_cv.wait(lk, [&]{ return tx_dirty || tx_stop; });
            if (tx_stop) break;
            tx_dirty = false;    // consume the request
            lk.unlock();

            if (styr_fd >= 0) {
                int8_t m = desired_mask.load(std::memory_order_relaxed);
                if(OBSTACLE_STOP){
                    if(m & BIT_FRAM) {
                        m = 0x40;
                    }
                }

                ssize_t wr = ::write(styr_fd, &m, 1);
                if (wr != 1) perror("UART write");
                tcdrain(styr_fd);
                //std::cout << "UART TX mask=0x" << std::hex << int(m) << std::dec << "\n";
            }

            lk.lock();
        }
    });

    //--------------------------------------Sensor test-----------------------------------
    std::thread t_sensor([&](){
    std::string buffer;
    uint8_t tmp[128];

    while(!global_stop){
        if(sensor_fd < 0){ 
            std::this_thread::sleep_for(std::chrono::milliseconds(200)); 
            continue; 
        }

        ssize_t r = ::read(sensor_fd, tmp, sizeof(tmp));   // blocking
        if (r > 0){
            buffer.append((char*)tmp, r);

            // check for newline
            size_t pos;
            while ((pos = buffer.find('\n')) != std::string::npos) {
                std::string line = buffer.substr(0, pos);
                buffer.erase(0, pos + 1);

                std::cout << "[Sensor UART] Received line: " << line << "\n";

                // ---------- Existing ultrasonic sensor handling ----------
                if (line.size() == 1){
                    char last = line[0];
                    g_sensor_byte.store(last, std::memory_order_relaxed);
                    g_sensor_seen.store(true,  std::memory_order_relaxed);

                    if (last == '1') {
                        OBSTACLE_STOP = 1;
                        request_send_mask();
                    } else if (last == '0') {
                        OBSTACLE_STOP = 0;
                        request_send_mask();
                    }
                }

                // ---------- New sensor data parsing ----------
                else {
                    int pl=0, pr=0, d=0, v=0;
                    if (sscanf(line.c_str(), "PL=%d,PR=%d,D=%d,V=%d", &pl, &pr, &d, &v) == 4){
                        g_pulses_left.store(pl, std::memory_order_relaxed);
                        g_pulses_right.store(pr, std::memory_order_relaxed);
                        g_distance_cm.store(d, std::memory_order_relaxed);
                        g_speed_cm_s.store(v, std::memory_order_relaxed);
                    }
                }
            }

        } else if(r == 0){
            std::this_thread::sleep_for(std::chrono::milliseconds(50)); // unplug?
        } else {
            if(errno==EINTR) continue;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }
    });

/*
    std::thread t_sensor([&](){
        uint8_t tmp[128];
        while(!global_stop){
            if(sensor_fd < 0){ std::this_thread::sleep_for(std::chrono::milliseconds(200)); continue; }

            ssize_t r = ::read(sensor_fd, tmp, sizeof(tmp));   // blocking
            if (r > 0){
                uint8_t last = tmp[r-1];

                std::cout << "[Sensor UART] Received byte: 0x" << std::hex << int(last) << std::dec << "\n";

                // keep latest byte for GUI
                g_sensor_byte.store(last, std::memory_order_relaxed);
                g_sensor_seen.store(true,  std::memory_order_relaxed);

                // just set/clear the flag — DO NOT touch current_mask or write UART here
                if (last == '1') {
                    //g_obstacle.store(true, std::memory_order_relaxed);
                    //shutdown(fd, SHUT_RDWR);
                    OBSTACLE_STOP = 1;
                    //set_bit(BIT_STOP);
                    request_send_mask();

                } else if (last == '0') {
                    //g_obstacle.store(false, std::memory_order_relaxed);
                    OBSTACLE_STOP = 0;
                    //clear_bit(BIT_STOP);
                    request_send_mask();
                }
            } else if(r == 0){
                std::this_thread::sleep_for(std::chrono::milliseconds(50)); // unplug?
            } else {
                if(errno==EINTR) continue;
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }
        }
    });  */

    // --------------------------- TCP server ----------------------------------
    int srv = ::socket(AF_INET, SOCK_STREAM, 0);
    if(srv<0){ perror("socket"); global_stop=true; t_sensor.join(); return 1; }
    int one=1; setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));

    sockaddr_in addr{}; addr.sin_family=AF_INET; addr.sin_port=htons(port);
    addr.sin_addr.s_addr = inet_addr(host);
    if(bind(srv, (sockaddr*)&addr, sizeof(addr))<0){ perror("bind"); global_stop=true; t_sensor.join(); return 1; }
    if(listen(srv, 1)<0){ perror("listen"); global_stop=true; t_sensor.join(); return 1; }
    std::cout<<"Lyssnar på "<<host<<":"<<port<<"\n";

    for(;;){
        sockaddr_in cli{}; socklen_t cl=sizeof(cli);
        int fd = accept(srv,(sockaddr*)&cli,&cl);
        if(fd<0){ if(errno==EINTR) continue; perror("accept"); continue; }
        set_nodelay(fd);
        std::cout<<"Klient ansluten\n";

        dirty = false;
        std::atomic<bool> stop{false};
        std::mutex send_mx;

        // ---- RX from PC -> styr UART ----
        std::thread t_rx([&](){
            std::string buf;
            char tmp[1024];

            while(!stop){         
                ssize_t r = recv(fd, tmp, sizeof(tmp), 0);
                
                if(r<=0) break;
                buf.append(tmp, tmp+r);
                size_t pos;
                while((pos = buf.find('\n')) != std::string::npos){
                    //std::cout<<"fast\n";
                    std::string line = buf.substr(0,pos); buf.erase(0,pos+1);
                    if(!line.empty() && line.back()=='\r') line.pop_back();
                    std::cout << "CMD: " << line << "\n";
                    
                    if(line=="quit") { stop=true; break; }

                    if(line=="stop_down") set_bit(BIT_STOP);
                    else if(line=="stop_up") clear_bit(BIT_STOP);
                      
                    else if(line=="fram_down" && !(current_mask.load() & BIT_FRAM)) set_bit(BIT_FRAM);
                    else if(line=="fram_up") clear_bit(BIT_FRAM);
                    
                    else if(line=="bakåt_down" && !(current_mask.load() & BIT_FRAM)) set_bit(BIT_BAKAT);
                    else if(line=="bakåt_up") clear_bit(BIT_BAKAT);
                    
                    else if(line=="vänster_down"){ 
                        set_bit(BIT_VANSTER); 
                        clear_bit(BIT_HOGER); 
                    }
                    else if(line=="vänster_up") clear_bit(BIT_VANSTER);
                    
                    else if(line=="höger_down"){ 
                        set_bit(BIT_HOGER); 
                        clear_bit(BIT_VANSTER); 
                    }
                    else if(line=="höger_up") clear_bit(BIT_HOGER);

                    if (dirty && styr_fd >= 0) {
                        request_send_mask();
                        dirty = false;
                    }
                }
            }
            stop=true;
        });

        // ---- TX to PC (20 Hz). Sends latest sensor byte as hex ----
        std::thread t_tx([&](){
            int seq = 0;
            while (!stop) {
                double batt = 7.6;   // volts (placeholder)
                double speed = 0.0;  // placeholder

                char hex[3] = {0};  // "00" + NUL
                if (g_sensor_seen.load(std::memory_order_relaxed)) {
                    uint8_t b = g_sensor_byte.load(std::memory_order_relaxed);
                    std::snprintf(hex, sizeof(hex), "%02X", b);
                } else {
                    hex[0] = '\0'; // GUI shows "sensor: --"
                }

                char line[256];
                int n = std::snprintf(line, sizeof(line),
                    "{\"seq\":%d,\"batt_v\":%.2f,\"speed\":%.2f,\"sensor_raw\":\"%s\"}\n",
                    seq++, batt, speed, hex);

                std::lock_guard<std::mutex> lk(send_mx);
                if (send(fd, line, n, 0) <= 0) { stop = true; break; }
                std::this_thread::sleep_for(std::chrono::milliseconds(50)); // 20 Hz
            }
        });

        t_rx.join(); t_tx.join();
        close(fd);
        std::cout<<"Klient frånkopplad\n";
    }

    global_stop = true;
    if(t_sensor.joinable()) t_sensor.join();
    if(styr_fd   >= 0) ::close(styr_fd);
    if(sensor_fd >= 0) ::close(sensor_fd);
    return 0;
}
