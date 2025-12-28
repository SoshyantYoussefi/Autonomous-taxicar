#include "servo.h"
#include <stdbool.h>
#define F_CPU 16000000UL

volatile uint8_t g_last_out = 0;

uint16_t TURN_LEFT = 2000;
uint16_t TURN_RIGHT = 4000;
uint16_t TURN_NEUTRAL = 3000;

static volatile uint32_t _ms = 0;

volatile float runtime_PID_P = PID_P;
volatile float runtime_PID_I = PID_I;
volatile float runtime_PID_D = PID_D;

void servo_init(void) {
	TCCR1A = (1 << COM1B1) | (1 << WGM11);
	TCCR1B = (1 << WGM13) | (1 << WGM12);

	ICR1 = 39999; 	 // Set PWM period (50 Hz)
	
	OCR1B = TURN_NEUTRAL;
	DDRD |= (1 << PD4);

	TCCR1B |= (1 << CS11); // Prescaler = 8
}

void set_servo_value(uint16_t percent) {
	if (percent < 100) {
		uint16_t turn_value = TURN_LEFT + 20 * percent;
		OCR1B = turn_value;
		g_last_out = percent;
		} else {
		OCR1B = TURN_RIGHT;
		g_last_out = 100;
	}
}

void servo_pid(int8_t error_angle) {
	static float i_term = 0.0f;
	static int8_t prev_error = 0;

	int16_t d_error = (int16_t)error_angle - (int16_t)prev_error;
	
	const float I_MIN = -150.0f;
	const float I_MAX =  150.0f;
	i_term += (float)error_angle;
	if (i_term > I_MAX) i_term = I_MAX;
	if (i_term < I_MIN) i_term = I_MIN;

	// PID sum
	float u = 50.0f
	+ runtime_PID_P * (float)error_angle
	+ runtime_PID_D * (float)d_error
	+ runtime_PID_I * i_term;

	// Output clamp (10..90 in your units)
	int32_t u_int = (int32_t)u;
	if (u_int > 90) u_int = 90;
	if (u_int < 10) u_int = 10;

	// Send the *clamped* value
	set_servo_value((uint8_t)u_int);

	prev_error = error_angle;
}



void clock_init(){
	// Timer0 CTC, prescaler 64 ? 16 MHz/64 = 250 kHz ? 1 ms = 250 counts ? OCR0=249
	TCCR0A = (1 << WGM01);        // CTC mode
	OCR0A  = 249;                 // 1 ms vid 16 MHz & /64
	TIMSK0 |= (1 << OCIE0A);       // enable compare match interrupt
	TCCR0B |= (1 << CS01) | (1 << CS00); // prescaler 64
}


ISR(TIMER0_COMPA_vect) { _ms++; }

uint32_t millis(void) {
	uint32_t m;
	uint8_t s = SREG;
	cli();
	m = _ms;
	SREG = s;
	return m;
}


bool ms_elapsed(uint32_t *t, uint16_t period_ms) {
	uint32_t now = millis();
	if ((uint32_t)(now - *t) >= period_ms) {
		*t = now;
		return true;
	}
	return false;
}

// Kör servo_pid() var 'period_ms' utan att blockera
void servo_tick_run(int8_t current_error) {
	static uint32_t t_servo = 0;
	const uint16_t period_ms = 10;  // 100 Hz PID (justera vid behov)

	if (ms_elapsed(&t_servo, period_ms)) {
		servo_pid(current_error);
	}
}
