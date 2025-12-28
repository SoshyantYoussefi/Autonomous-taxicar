#include "servo.h"
#include <stdbool.h>
#define F_CPU 16000000UL

volatile uint8_t g_last_out = 0;

uint16_t TURN_LEFT = 2000;
uint16_t TURN_RIGHT = 4000;
uint16_t TURN_NEUTRAL = 3000;


static volatile uint32_t _ms = 0;



void servo_init(void) {
	TCCR1A = (1 << COM1B1) | (1 << WGM11);
	TCCR1B = (1 << WGM13) | (1 << WGM12);

	ICR1 = 39999; 	 // Set PWM period (50 Hz)
	
	OCR1B = TURN_NEUTRAL;
	DDRD |= (1 << PD4);

	TCCR1B |= (1 << CS11); // Prescaler = 8
}

void set_servo_value(uint8_t percent) {
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
	static int32_t accumulated_error = 0;
	static int8_t previous = 0;

	int16_t d_error = error_angle - previous;
	accumulated_error += error_angle;

	int32_t servo_val = 50 + PID_P * error_angle + PID_D * d_error + PID_I * accumulated_error;
	if (servo_val > 100) servo_val = 100;
	if (servo_val < 0) servo_val = 0;
	set_servo_value((uint8_t)servo_val);

	previous = error_angle;
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