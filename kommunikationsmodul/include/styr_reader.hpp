#pragma once
#include "fd.hpp"
#include "shared_state.hpp"
#include "styr_writer.hpp"
#include <thread>

class StyrReader {
public:
    StyrReader(Fd& styr_fd, SharedState& st, StyrWriter& sw);
    void start();
    void join();

private:
    void run();

    Fd& styr_;
    SharedState& st_;
    StyrWriter& styrw_;
    std::thread thr_;
};
