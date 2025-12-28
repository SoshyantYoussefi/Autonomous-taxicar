#pragma once
#include <unistd.h>

struct Fd {
    int fd = -1;
    Fd() = default;
    explicit Fd(int f) : fd(f) {}
    Fd(Fd && o) noexcept : fd(o.fd) { o.fd = -1; }
    Fd& operator=(Fd && o) noexcept {
        if (this != &o) {
            if (fd >= 0) ::close(fd);
            fd = o.fd;
            o.fd = -1;
        }
        return *this;
    }
    Fd(const Fd &) = delete;
    Fd& operator=(const Fd &) = delete;
    ~Fd() {close();}
    
    explicit operator bool() const { return fd >= 0; }
    int get() const { return fd; }
    void close() {
        if (fd >= 0) {
            ::close(fd);
            fd = -1;
        }
    }
};