/*
 * odometry.cpp
 *
 * Created: 2025-11-11 13:30:20
 *  Author: oskna605
 */ 

#include "odometry.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>

// Global variables for hall sensors
volatile uint32_t pulses_left = 0;
volatile uint32_t pulses_right = 0;
volatile uint32_t milliseconds = 0;

volatile uint32_t last_pulses_left = 0;
volatile uint32_t last_pulses_right = 0;
volatile uint32_t last_time_ms = 0;

volatile uint32_t last_left_ms = 0;
volatile uint32_t last_right_ms = 0;

// -------------------- ISRs --------------------

// INT0 ISR for left wheel
ISR(INT0_vect) {
	if ((milliseconds - last_left_ms) >= DEBOUNCE_MS) {
		pulses_left++;
		last_left_ms = milliseconds;
	}
}

// INT1 ISR for right wheel
ISR(INT1_vect) {
	if ((milliseconds - last_right_ms) >= DEBOUNCE_MS) {
		pulses_right++;
		last_right_ms = milliseconds;
	}
}

// Timer0 ISR for 1ms tick
ISR(TIMER0_COMPA_vect) {
	milliseconds++;
}

// -------------------- Initialization --------------------

void hall_left_init(void) {
	DDRD &= ~(1 << DDD2);   // Input
	PORTD |= (1 << PORTD2); // Pull-up
	EICRA |= (1 << ISC01); EICRA &= ~(1 << ISC00); // Falling edge
	EIFR |= (1 << INTF0);
	EIMSK |= (1 << INT0);
}

void hall_right_init(void) {
	DDRD &= ~(1 << DDD3);   // Input
	PORTD |= (1 << PORTD3); // Pull-up
	EICRA |= (1 << ISC11); EICRA &= ~(1 << ISC10); // Falling edge
	EIFR |= (1 << INTF1);
	EIMSK |= (1 << INT1);
}

void timer0_init(void) {
	TCCR0A = (1 << WGM01);               // CTC mode
	TCCR0B = (1 << CS01) | (1 << CS00);  // Prescaler 64
	OCR0A = 249;                         // 1 ms tick
	TIMSK0 = (1 << OCIE0A);              // Enable compare match interrupt
}

// -------------------- Odometry Calculations --------------------

static float calculate_wheel_distance_mm(uint32_t pulses) {
	float revolutions = (float)pulses / PULSES_PER_ROTATION;
	return revolutions * WHEEL_CIRCUMFERENCE_MM;
}

static float calculate_wheel_speed(uint32_t current, uint32_t last, uint32_t delta_time) {
	if (delta_time == 0) return 0.0;
	uint32_t delta_pulses = current - last;
	float distance_mm = ((float)delta_pulses / PULSES_PER_ROTATION) * WHEEL_CIRCUMFERENCE_MM;
	return (distance_mm * 1000.0) / delta_time;
}

void update_odometry(Odometry* odom) {
	// Read values atomically
	cli();
	uint32_t current_left = pulses_left;
	uint32_t current_right = pulses_right;
	uint32_t current_time = milliseconds;
	sei();

	uint32_t delta_time = current_time - last_time_ms;

	// Store pulse counts
	odom->left_pulses = current_left;
	odom->right_pulses = current_right;

	// Calculate distances
	odom->left_distance_mm = calculate_wheel_distance_mm(current_left);
	odom->right_distance_mm = calculate_wheel_distance_mm(current_right);
	odom->average_distance_mm = (odom->left_distance_mm + odom->right_distance_mm) / 2.0;

	// Calculate speeds
	odom->left_speed_mm_s = calculate_wheel_speed(current_left, last_pulses_left, delta_time);
	odom->right_speed_mm_s = calculate_wheel_speed(current_right, last_pulses_right, delta_time);
	odom->average_speed_mm_s = (odom->left_speed_mm_s + odom->right_speed_mm_s) / 2.0;

	// Calculate rotation (simplified differential drive)
	float distance_diff = odom->right_distance_mm - odom->left_distance_mm;
	odom->rotation_deg = (distance_diff / WHEELBASE_MM) * (180.0 / 3.14159265359);

	// Update last values
	last_pulses_left = current_left;
	last_pulses_right = current_right;
	last_time_ms = current_time;
}

void reset_odometry(void) {
	cli();
	pulses_left = 0;
	pulses_right = 0;
	last_pulses_left = 0;
	last_pulses_right = 0;
	last_time_ms = milliseconds;
	sei();
}


