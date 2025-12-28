
#ifndef UART_H
#define UART_H

#include <stdint.h>

void uart_init(unsigned long baud);
void uart_send_char(uint8_t c);
uint8_t uart_available();
uint8_t uart_read();
void uart_sender(uint8_t descriptor, uint8_t data);

#endif