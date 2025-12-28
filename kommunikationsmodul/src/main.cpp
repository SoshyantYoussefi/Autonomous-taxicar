#include "config.hpp"
#include "uart.hpp"
#include "log.hpp"
#include "shared_state.hpp"
#include "styr_writer.hpp"
#include "sensor_reader.hpp"
#include "tcp_session.hpp"
#include "cam_offset_rx.hpp"
#include "styr_reader.hpp"
#include "CppToPyArrayTx.hpp"
#include "sensor_writer.hpp"

#include <arpa/inet.h>
#include <cerrno>
#include <string>
#include <functional>

int main(int argc, char** argv) {
    Config cfg;
    if (argc > 1) cfg.host       = argv[1];
    if (argc > 2) cfg.port       = std::stoi(argv[2]);
    if (argc > 3) cfg.styr_dev   = argv[3];
    if (argc > 4) cfg.styr_baud  = std::stoi(argv[4]);
    if (argc > 5) cfg.sensor_dev = argv[5];
    if (argc > 6) cfg.sensor_baud= std::stoi(argv[6]);

    Fd styr   = open_uart(cfg.styr_dev.c_str(),   cfg.styr_baud);
    Fd sensor = open_uart(cfg.sensor_dev.c_str(), cfg.sensor_baud);

    if (!styr) { 
        LOG_ERROR("Kunde inte öppna styr-UART " << cfg.styr_dev); 
    } else { 
        LOG_INFO("styr UART open: " << cfg.styr_dev << " @" << cfg.styr_baud); 
    } if (!sensor) {
        LOG_ERROR("Kunde inte öppna sensor-UART " << cfg.sensor_dev); 
    } else {
        LOG_INFO("sensor UART open: " << cfg.sensor_dev << " @" << cfg.sensor_baud); 
    }

    SharedState st;

    StyrWriter styrw(styr, st);
    styrw.start();

    SensorWriter sensorw(sensor, st);
    sensorw.start();
    
    SensorReader sens(sensor, st, styrw);
    sens.start();

    StyrReader sty(styr, st, styrw);
    sty.start(); 

    CamOffsetRx cam_rx(st,[&]{styrw.notify_new_offset();});
     // <-- väcker writer-tråden när offset kommit
    cam_rx.start();

    //CppToPyArrayTx array_tx("/tmp/cpp_to_py.sock");

    int srv = make_server(cfg.host, cfg.port);
    if (srv < 0) {
        st.global_stop.store(true);
        sens.join();
        sty.join();
        styrw.stop();
        return 1;
    }
    LOG_INFO("Lyssnar på " << cfg.host << ":" << cfg.port);

    for (;;) {
        sockaddr_in cli{}; socklen_t cl = sizeof(cli);
        int fd = ::accept(srv, (sockaddr*)&cli, &cl);
        if (fd < 0) { if (errno == EINTR) continue; perror("accept"); continue; }
        TcpSession(fd, st, styrw, sensorw).run();
    }

    // (om du vill ha kontrollerad shutdown senare:)
    // st.global_stop.store(true);
    // sens.join();
    // uartw.stop();
    return 0;
}
