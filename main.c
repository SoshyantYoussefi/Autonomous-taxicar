/*
 * sensormodul.c
 *
 * Created: 2025-12-05 15:12:19
 * Author : oskar
 */ 

#define F_CPU 16000000UL
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdint.h>
#include <util/delay.h>
#include <stdio.h>

//----------OPCODES---------------
#define OPCODE_SET_ULTRA_DIST 0x04
#define OPCODE_HALL_DIST 0x03
#define OPCODE_HALL_SPEED 0x30

uint16_t ultrasonic_limit = 2500;       // Default value

// Global variables for hall sensors
volatile uint32_t pulses_left = 0;
volatile uint32_t pulses_right = 0;
volatile uint32_t milliseconds = 0;

volatile uint32_t last_pulses_left = 0;
volatile uint32_t last_pulses_right = 0;
volatile uint32_t last_time_ms = 0;

volatile uint32_t last_left_ms = 0;
volatile uint32_t last_right_ms = 0;

// Wheel and encoder constants
#define PULSES_PER_ROTATION 10
#define WHEEL_DIAMETER_MM 83.0
#define WHEEL_CIRCUMFERENCE_MM (WHEEL_DIAMETER_MM * 3.14159)
#define WHEELBASE_MM 200.0

// Hall sensor pins
#define HALL_LEFT_PIN PD2   // INT0
#define HALL_RIGHT_PIN PD3  // INT1

// Debounce for hall sensors ( unsure if needed )
#define DEBOUNCE_MS 1

uint8_t uart_available();
uint8_t uart_read();

// Odometry data structure
typedef struct {
	float left_distance_mm;
	float right_distance_mm;
	float average_distance_mm;
	float left_speed_mm_s;
	float right_speed_mm_s;
	float average_speed_mm_s;
	float rotation_deg;      // Estimated rotation angle
	uint32_t left_pulses;
	uint32_t right_pulses;
} Odometry;


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

// -------------------- Globals --------------------
volatile uint16_t icr_start = 0;
volatile uint16_t icr_end = 0;
volatile uint8_t echo_done = 0;

// Ultrasonic sensor pins
#define PD5_TRIG PD5
#define ECHO_PD6 PD6

// Global variables for ultrasonic measurement
extern volatile uint16_t icr_start;
extern volatile uint16_t icr_end;
extern volatile uint8_t echo_done;

// -------------------- Ultrasonic functions --------------------
void echo_icp_init(void) {
	DDRD  &= ~(1 << DDD6);   // ECHO pin as input
	PORTD &= ~(1 << PORTD6); // No pull-up
	TCCR1A = 0;
	TCCR1B = (1 << CS11) | (1 << ICES1); // Prescaler 8, rising edge first
	TIFR1  |= (1 << ICF1) | (1 << TOV1); // Clear flags
	TIMSK1 |= (1 << ICIE1);              // Enable Input Capture Interrupt
}

void start_sens(void) {
	DDRD |= (1 << PD5_TRIG);   // TRIG pin as output
	PORTD |= (1 << PD5_TRIG);
	_delay_us(20);             // 20s pulse
	PORTD &= ~(1 << PD5_TRIG);
}

// -------------------- ISR --------------------
ISR(TIMER1_CAPT_vect) {
	uint16_t cap = ICR1;
	if (TCCR1B & (1 << ICES1)) { // Rising edge
		icr_start = cap;
		TCCR1B &= ~(1 << ICES1); // Switch to falling edge
		} else {                     // Falling edge
		icr_end = cap;
		echo_done = 1;
		TCCR1B |= (1 << ICES1);  // Switch back to rising edge
	}
}

// -----------------------UART--------------------//

void uart_init(unsigned long baud) {
	UCSR0A |= (1 << U2X0);                      // Double speed
	uint16_t ubrr = (F_CPU / 8 / baud) - 1;
	UBRR0H = (uint8_t)(ubrr >> 8);
	UBRR0L = (uint8_t)ubrr;
	UCSR0B |= (1 << RXEN0) | (1 << TXEN0);      // Enable transmitter & reciever
	UCSR0C |= (1 << UCSZ01) | (1 << UCSZ00);    // 8-bit, no parity, 1 stop
}

void uart_send_data(uint8_t c) {
	while(!(UCSR0A & (1 << UDRE0)));
	UDR0 = c;
}

uint8_t uart_available() {
	return (UCSR0A & (1 << RXC0));
}

uint8_t uart_read() {
	return UDR0;
}

void uart_sender(uint8_t upcode, uint8_t data) {
	uart_send_data(upcode);
	uart_send_data(data);
}

int main(void)
{
	
	// Ultrasonic Sensor
	echo_icp_init();
	uart_init(115200);
	sei();
	DDRD |= (1 << PD5_TRIG) | (1 << PD1);
	PORTD &= ~(1 << PD5_TRIG);
	PORTD &= ~(1 << PD1);
	uint8_t obstacle_present = 0;
	uint8_t has_sent_obstacle = 0;
	
	// Hall sensors
 	timer0_init();
 	hall_left_init();
 	hall_right_init();
 	
 	Odometry odom = {0};
 	reset_odometry();
 	sei();
	
	while (1)
	{
		
		// -----------------------UART Recieve----------------------
		if (uart_available()) {
			uint8_t opcode = uart_read();
			
 			while (!uart_available()) {}
 			uint8_t data = uart_read();

			if (opcode == OPCODE_SET_ULTRA_DIST) {
				ultrasonic_limit = (uint16_t)data * 80;  //some scaling?
				//uart_sender(0xFF, 0x01);
			}
		}
		
		//--------------------Hall Sensor-------------------------------
		update_odometry(&odom);
		
 		volatile int puls = odom.right_pulses;
 		volatile int distance = (int)(puls *1.25);
 		
 		if (distance >= 10) {
 			uart_sender(0x03, 0x01);
 			pulses_right = 0;
 			odom.right_pulses = 0;
 			puls = 0;
 			distance = 0;
 		} else {
 			//uart_sender(0x03, 0x00);
 		}
		
		//---------------- Ultrasonic Sensor---------------------
		echo_done = 0;
		start_sens();

		uint16_t timeout = 60000;
		while(!echo_done && timeout--){}

		if (echo_done) {
			uint16_t start = icr_start;
			uint16_t end = icr_end;
			
			uint16_t length = (end >= start) ? (end - start) : (end + 0x10000 - start);
			
			if (length < ultrasonic_limit) {
				obstacle_present = 1;
				} 
			else {
				obstacle_present = 0;
			}
		}
		if (obstacle_present && !has_sent_obstacle) {
			uart_sender(0x40, 0x01);
			has_sent_obstacle = 1;
			} 
		else if(!obstacle_present && has_sent_obstacle) {
			uart_sender(0x40, 0x00);
			has_sent_obstacle = 0;
		}
		_delay_ms(30);
	}
}
