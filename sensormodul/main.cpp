/*
 * sensormodul_remake.cpp
 *
 * Created: 2025-11-25 10:42:56
 * Author : oskna605
 */

#define F_CPU 16000000UL

#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdint.h>
#include <util/delay.h>
#include <stdio.h>
#include "odometry.h"
#include "ultrasonic.h"
#include "uart.h"

uint16_t ultrasonic_limit = 2500; // Default value
#define OPCODE_SET_ULTRA_DIST 0x04

// -------------------- ISR --------------------
ISR(TIMER1_CAPT_vect)
{
	uint16_t cap = ICR1;
	if (TCCR1B & (1 << ICES1))
	{ // Rising edge
		icr_start = cap;
		TCCR1B &= ~(1 << ICES1); // Switch to falling edge
	}
	else
	{ // Falling edge
		icr_end = cap;
		echo_done = 1;
		TCCR1B |= (1 << ICES1); // Switch back to rising edge
	}
}

int main(void)
{
	// ------- Init -------
	echo_icp_init();
	uart_init(115200);

	DDRD |= (1 << PD5_TRIG) | (1 << PD1);
	PORTD &= ~(1 << PD5_TRIG);
	PORTD &= ~(1 << PD1);
	uint8_t obstacle_present = 0;
	uint8_t has_sent_obstacle = 0;

	// Hall Sensor
	/*
	timer0_init();
	hall_left_init();
	hall_right_init();

	Odometry odom = {0};
	reset_odometry(); */
	sei();

	while (1)
	{
		// -----------------------UART Recieve----------------------
		if (uart_available())
		{
			uint8_t opcode = uart_read();

			while (!uart_available())
			{
			}
			uint8_t data = uart_read();

			if (opcode == OPCODE_SET_ULTRA_DIST)
			{
				ultrasonic_limit = (uint16_t)data * 80; // some scaling?
				uart_sender(OPCODE_SET_ULTRA_DIST, data);
			}
		}

		// Hall sensor
		//_delay_ms(1000);
		//	update_odometry(&odom);

		// Send odometry data, beginning with just distance travelled
		// int distance_cm = (int)((odom.average_distance_mm / 10.0) + 0.5); // convert mm to cm
		// int speed_cm_s = (int)((odom.average_speed_mm_s / 10.0) + 0.5);   // convert mm/s to cm/s

		// volatile int puls = odom.right_pulses;
		// uart_send_char((char)puls);

		// volatile int distance = (int)(puls *1.25);

		// if (distance >= 100) {
		//	uart_send_char('1');
		// }

		// --------------------Ultrasonic Sensor Measuring----------------------------
		echo_done = 0;
		start_sens();

		uint16_t timeout = 60000;
		while (!echo_done && timeout--)
		{
		}

		if (echo_done)
		{
			uint16_t start = icr_start;
			uint16_t end = icr_end;

			uint16_t length = (end >= start) ? (end - start) : (end + 0x10000 - start);

			if (length < ultrasonic_limit)
			{
				obstacle_present = 1;
			}
			else
			{
				obstacle_present = 0;
			}
		}
		if (obstacle_present && !has_sent_obstacle)
		{
			uart_sender(0x40, 0x01);
			has_sent_obstacle = 1;
		}
		else if (!obstacle_present && has_sent_obstacle)
		{
			uart_sender(0x40, 0x00);
			has_sent_obstacle = 0;
		}
		_delay_ms(20);
	}
}
