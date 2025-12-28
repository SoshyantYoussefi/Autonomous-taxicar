/*
 * ultrasonic.h
 *
 * Created: 2025-11-11 13:30:35
 *  Author: oskna605
 */ 



#ifndef ULTRASONIC_H
#define ULTRASONIC_H

#include <stdint.h>

// Ultrasonic sensor pins
#define PD5_TRIG PD5
#define ECHO_PD6 PD6

// Global variables for ultrasonic measurement
extern volatile uint16_t icr_start;
extern volatile uint16_t icr_end;
extern volatile uint8_t echo_done;

// Initialize Input Capture for ultrasonic echo
void echo_icp_init(void);

// Start ultrasonic sensor measurement
void start_sens(void);

// UART initialization and communication
//void uart_init(unsigned long baud);
//void uart_send_char(char c);

#endif // ULTRASONIC_H
