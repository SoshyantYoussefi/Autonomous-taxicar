/*
 * GccApplication1.c
 *
 * Created: 2025-11-04 14:00:36
 * Author : tobul865 och ludde mannen!
 */ 

#define F_CPU 16000000UL

#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>
#include <stdint.h>
#include "servo.h"


#define PD2_DIR PD2
#define PD3_BRAKE PD3
#define PD6_PWM PD6
#define PD4_TRN PD4
#define BAUD 115200
#define MYUBRR (F_CPU/8/BAUD - 1)

typedef enum {

	/************ FROM GUI ************/
	MOVE_COMMAND   = 0x01,
	VAXLING        = 0x02,

	/************ FROM CAM ************/
	OFFSET_ANGLE   = 0x10,
	CAM_STOP       = 0xFF,

	/************ PID / CONTROL ************/
	OPCODE_SET_PID_P      = 0x11,
	OPCODE_SET_PID_I      = 0x12,
	OPCODE_SET_PID_D      = 0x20,
	OPCODE_REQUEST_PID_P  = 0x21,
	OPCODE_REQUEST_PID_I  = 0x13,
	OPCODE_REQUEST_PID_D  = 0x31,
	UPCODE_SPEED          = 0x50,

	/************ SENSOR ************/
	OPCODE_HALL           = 0x03,
	OPCODE_CALIB_HALL     = 0x30,
	OPCODE_ULTRASONIC     = 0x04,

	/*************** ***************/
	
} Opcode;


uint8_t MAX_COUNT = 127;
uint8_t SPEED = 60;
uint8_t STOP_SEQ = 0;
uint32_t stop_start_ms = 0;
uint8_t drive_mode = 0x00;
uint8_t auto_active = 0;

void clock_init(void);

// -------------------- UART functions --------------------
void uart_init(unsigned long baud) {
	UCSR0A |= (1 << U2X0); // Double speed
	uint16_t ubrr = (F_CPU / 8 / baud) - 1;
	UBRR0H = (uint8_t)(ubrr >> 8);
	UBRR0L = (uint8_t)ubrr;
	UCSR0B = (1 << RXEN0) | (1 << TXEN0);             // Enable transmitter
	UCSR0C |= (1 << UCSZ01) | (1 << UCSZ00); // 8-bit, no parity, 1 stop
}

void uart_send_char(uint8_t c) {
	while (!(UCSR0A & (1 << UDRE0))); // Wait for empty buffer
	UDR0 = c;
}

// YOLO FUNCTION
void uart_sender(uint8_t descriptor, uint8_t data) {
	uart_send_char(descriptor);
	uart_send_char(data);
}


void pwn_init(void) {
	// Fast PWM on Timer2, non-inverting mode on OC2B
	TCCR2A = (1 << WGM21) | (1 << WGM20) | (1 << COM2B1);

	// Fast PWM mode (WGM22) + prescaler 32 (CS21, CS20)
	TCCR2B = (1 << WGM22) | (1 << CS22);

	OCR2A = MAX_COUNT;
	OCR2B = 0;

	// Configure ports
	DDRD |= (1 << PD2_DIR) | (1 << PD3_BRAKE) | (1 << PD6_PWM);
}

void set_gas_percent(uint8_t percent, uint8_t dir) {
	if (percent < 40) percent = 0; // Min throttle to avoid stall

	PORTD &= ~(1 << PD3_BRAKE);
	
	if (dir == 0) {
		PORTD &= ~(1 << PD2_DIR);
	} else if (dir == 1) {
		PORTD |= (1 << PD2_DIR);
	}
	
	if (percent > 100) percent = 100;
	OCR2B = (uint16_t)percent*MAX_COUNT/100;
}

uint8_t uart_available() {
//PORTA=SPH;
//DDRA=SPL;
	return (UCSR0A & (1 << RXC0));
}

uint8_t uart_read() {
	return UDR0;
}

void stop() {
	PORTD |= (1 << PD3_BRAKE);
}

uint8_t gas_from_offset(int8_t offset) {
	if (offset < 5) {
		return 75;
	} else if (offset < 12) {
		return 75-(2*(offset-5));
	} else if (offset < 40) {
		return 65-(offset>>1);
	}
	
	return 0;
}

// MANUEL KÖRNING //

void manual_drive(uint8_t upcode, uint8_t data) {
	uint8_t forward = (data >> 6) & 0x01;
	uint8_t stopping = (data >> 5) & 0x01;
	uint8_t left = (data >> 4) & 0x01;
	uint8_t right = (data >> 3) & 0x01;
	uint8_t reverse = (data >> 2) & 0x01;
		
	if (stopping) {
		stop();
	}
	else if (forward) {
		set_gas_percent(SPEED, 0);
	}
	else if (reverse) {
		set_gas_percent(SPEED, 1);
	}
	else {
		set_gas_percent(0, 0);
	}

	if (left) {
		set_servo_value(0);
	}
	else if (right) {
		set_servo_value(100);
			
	}
	else {
		set_servo_value(50);
	}
}

// AUTOMATIC DRIVE //

void automatic_drive(uint8_t upcode, uint8_t data) {
	int8_t data_signed = 0;
	if(data){
		data_signed = (int8_t)data - 63;
		int8_t offset = data_signed > 0 ? data_signed : -data_signed;
				
		uint8_t gas = gas_from_offset(offset);
		if (!STOP_SEQ && auto_active) set_gas_percent(SPEED, 0);
	}
			
	servo_tick_run(data_signed);
	//_delay_ms(10);
}

void process_packet(uint8_t upcode, uint8_t data) {
	if (upcode == VAXLING) {
		drive_mode = data;
		if (data == 0x00) {
			STOP_SEQ = 0;
		} else if (data == 0x01){
			STOP_SEQ = 1;
			auto_active = 0;
		}
		set_gas_percent(0, 0);
		stop();
	}
	else if (upcode == UPCODE_SPEED) {
		SPEED = data;
	}
	else if (upcode == CAM_STOP) {
		if (data == 0x00) {
			STOP_SEQ = 1;
			stop_start_ms = millis();	
		} else if (data == 0x01) {
			auto_active = 1;
			STOP_SEQ = 0;
		}
	}
	else if (upcode == MOVE_COMMAND) {
		if (drive_mode == 0x00 && !STOP_SEQ) {
			manual_drive(upcode, data);
		}
	}
	else if (upcode == OFFSET_ANGLE) {
		if (drive_mode == 0x01) {
			automatic_drive(upcode, data);
		}
	}
	else if (upcode == OPCODE_SET_PID_P) {
		runtime_PID_P = data / 50.0f;
	}
	else if (upcode == OPCODE_SET_PID_I) {
		runtime_PID_I = data / 50.0f;
	}
	else if (upcode == OPCODE_SET_PID_D) {
		runtime_PID_D = data / 50.0f;
		//uart_sender(OPCODE_SET_PID_P, (uint8_t)(runtime_PID_P * 50.0f));
		//_delay_ms(20);
		//uart_sender(OPCODE_SET_PID_I, (uint8_t)(runtime_PID_I * 50.0f));
		//_delay_ms(20);
		//uart_sender(OPCODE_SET_PID_D, (uint8_t)(runtime_PID_D * 50.0f));
	}
	else {
		uart_send_char(0xFF);
		uart_send_char(upcode);
	}
}

uint8_t reset_cause;


int main(void)
{
	
	uart_init(115200);
	// Send reset cause once at boot
	reset_cause = MCUSR;
	MCUSR = 0;
	
	// Use PortA as info between restarts
	//PORTA = 1;
	uart_send_char('R');
	uart_send_char(reset_cause);
	
	pwn_init();
	clock_init();       // startar Timer0 1 ms-tick (för ms_elapsed, millis)
	servo_init();
	sei();              // aktiverar globala avbrott
	
	set_gas_percent(10, 0);
	_delay_ms(800);
	stop();
	set_servo_value(100);
	_delay_ms(300);
	set_servo_value(0);
	_delay_ms(400);
	set_servo_value(50);	
	
	//uart_send_char('R');          // header
	//uart_send_char(reset_cause);  // raw flags
	
//PORTA = 2;
	while (1) {
//PORTA = 3;
		uint8_t inc_upcode;
		uint8_t data;
//PORTA=30;
		if (uart_available()) {
//PORTA = 31;
			inc_upcode = uart_read();
//PORTA = 32;
			while(!uart_available()) {
//PORTA = 33;
				
			}
//PORTA = 34;
			data = uart_read();
//PORTA = 35;
			process_packet(inc_upcode, data);
//PORTA = 36;
		}
//PORTA = 4;
		/*
		_delay_ms(1000);
		uint8_t test1 = 'd';
		uint8_t test2 = 67;
		uart_sender(test1, test2);
		_delay_ms(1000);
		*/
		
		uint16_t t1 = (uint32_t)500 - 24 * (SPEED-50);
		uint16_t t2 = (uint32_t)1200 - 60 * (SPEED-50);
		
		if (STOP_SEQ) {
			uint32_t dt = millis() - stop_start_ms;
			if (dt < t1) {
				set_gas_percent(50, 0);
				}else if(dt < t2) {
				set_gas_percent(30, 0);
				} else {
				set_gas_percent(0, 0);
			}
		}
//PORTA = 5;
		
		//if (drive_mode == 0x00 && inc_upcode == MOVE_COMMAND) {
			//set_gas_percent(50, 0);
			////manual_drive(inc_upcode, data);
		//} else if (drive_mode == 0x01 && inc_upcode == OFFSET_ANGLE) {
			//set_gas_percent(80, 0);
			////automatic_drive(inc_upcode, data);
		//}
	}
	//PORTC = 0; // borde aldrig komma hit.
}

//ISR(BADISR_vect) {
	//uart_send_char('R');
	//uart_send_char(0x11);
	//while(1);
//}