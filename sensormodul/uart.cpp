
#include <avr/io.h>
#include "uart.h"


void uart_init(unsigned long baud) {
	UCSR0A |= (1 << U2X0);                      // Double speed
	uint16_t ubrr = (F_CPU / 8 / baud) - 1;
	UBRR0H = (uint8_t)(ubrr >> 8);
	UBRR0L = (uint8_t)ubrr;
	UCSR0B |= (1 << RXEN0) | (1 << TXEN0);      // Enable transmitter & reciever
	UCSR0C |= (1 << UCSZ01) | (1 << UCSZ00);    // 8-bit, no parity, 1 stop
}

void uart_send_char(uint8_t c) {
	while (!(UCSR0A & (1 << UDRE0)));           // Wait for empty buffer
	UDR0 = c;
}

uint8_t uart_available() {
    return (UCSR0A & (1 << RXC0));
}

uint8_t uart_read() {
    return UDR0;
}

void uart_sender(uint8_t descriptor, uint8_t data) {
	uart_send_char(descriptor);
	uart_send_char(data);
}