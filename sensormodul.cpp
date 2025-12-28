/*
 * sensormodul.cpp
 *
 * Created: 2025-11-06 11:14:19
 * Author : tobul865
 */ 

#define F_CPU 16000000UL
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdint.h>
#include <util/delay.h>
#define PD5_TRIG PD5
#define ECHO_PD6 PD6

//#define PD2_LEFT PD2;
//
//volatile uint32_t pulses_left = 0;

//static void odometer_int0_init(void) {
    //DDRD  &= ~(1 << DDD2);
    //PORTD |=  (1 << PORTD2);
//
    //EICRA &= ~((1 << ISC00) | (1 << ISC10) | (1 << ISC11));
    //EICRA |=  (1 << ISC01);
//
    //EIFR  |=  (1 << INTF0);
    //EIMSK |=  (1 << INT0);
//
    //sei();	
//}
//
//ISR(INT0_vect) {
	//pulses_left++;
//}

volatile uint16_t icr_start, icr_end;
volatile uint8_t  echo_done;

void echo_icp_init(void){
	DDRD  &= ~(1<<DDD6);
	PORTD &= ~(1<<PORTD6);
	TCCR1A = 0;
	TCCR1B = (1<<CS11) | (1<<ICES1);
	TIFR1  |= (1<<ICF1) | (1<<TOV1);
	TIMSK1 |= (1<<ICIE1);
}

void uart_init(unsigned long baud) {
	UCSR0A |= (1 << U2X0);
	
	uint16_t ubrr = (F_CPU / 8 / baud) - 1;
	
	UBRR0H = (uint8_t)(ubrr >> 8);
	UBRR0L = (uint8_t)ubrr;
	
	UCSR0B |= (1 << TXEN0);
	
	UCSR0C |= (1 << UCSZ01) | (1 << UCSZ00);
}

void uart_send_char(char c) {
	while(!(UCSR0A & (1 << UDRE0)));
	UDR0 = c;
}

ISR(TIMER1_CAPT_vect){
	uint16_t cap = ICR1;
	if (TCCR1B & (1<<ICES1)) {
		icr_start = cap;
		TCCR1B &= ~(1<<ICES1);
		} else {
		icr_end = cap;
		echo_done = 1;
		TCCR1B |= (1<<ICES1);
	}
}

void start_sens(void) {
	PORTD |= (1 << PD5_TRIG);
	_delay_us(20);
	PORTD &= ~(1 << PD5_TRIG);
}

int main(void)
{
	echo_icp_init();
	uart_init(115200);
	sei();
	DDRD |= (1 << PD5_TRIG) | (1 << PD1);
	PORTD &= ~(1 << PD5_TRIG);
	PORTD &= ~(1 << PD1);
	uint8_t obstacle_present = 0;
	uint8_t has_sent_obstacle = 0;
	//odometer_int0_init();
    while (1) 
    {
		echo_done = 0;
		start_sens();
		
		uint16_t timeout = 60000;
		while(!echo_done && timeout--){}
			
		if (echo_done) {
			uint16_t start = icr_start;
			uint16_t end = icr_end;
			
			uint16_t length = (end >= start) ? (end - start) : (end + 0x10000 - start);
			
			if (length < 2500) {
				obstacle_present = 1;	
			} else {
				obstacle_present = 0;
			}
		}
		if (obstacle_present && !has_sent_obstacle) {
			uart_send_char('1');
			has_sent_obstacle = 1;
		} else if(!obstacle_present && has_sent_obstacle) {
			uart_send_char('0');
			has_sent_obstacle = 0;
		}
		_delay_ms(10);
    }
}