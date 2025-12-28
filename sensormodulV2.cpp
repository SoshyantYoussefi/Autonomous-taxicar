
/*
 * sensormodul.cpp
 *
 * Created: 2025-11-06 11:14:19
 * Author : tobul865, oskna605
 */ 

#define F_CPU 16000000UL
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdint.h>
#include <util/delay.h>
#include <stdio.h>

//---------------------------------------------------------------------------------------------------HALL SENSOR---------------------------------------------------------------------------------------------------
#define PULSES_PER_ROTATION 10 
#define WHEEL_DIAMETER_MM 83.0    
#define WHEEL_CIRCUMFERENCE_MM (WHEEL_DIAMETER_MM * 3.14159)
#define WHEELBASE_MM 200.0 

// Pin definitions
#define HALL_LEFT_PIN PD2           // INT0
#define HALL_RIGHT_PIN PD3          // INT1

volatile uint32_t pulses_left = 0;
volatile uint32_t pulses_right = 0;
volatile uint32_t milliseconds = 0; 

// For speed calculation
volatile uint32_t last_pulses_left = 0;
volatile uint32_t last_pulses_right = 0;
volatile uint32_t last_time_ms = 0;

// Initialize INT0 for left wheel sensor
static void hall_left_init(void) {
	
	DDRD &= ~(1 << DDD2);
	PORTD |= (1 << PORTD2);
	
	// Configure INT0 to trigger on RISING edge
	//EICRA |= (1 << ISC01) | (1 << ISC00);
	
	// Configure INT0 to trigger on FALLING edge
	EICRA |= (1 << ISC01);
	EICRA &= ~(1 << ISC00);
	
	
	EIFR |= (1 << INTF0);
	EIMSK |= (1 << INT0);
}

// Initialize INT1 for right wheel sensor
static void hall_right_init(void) {
	
	DDRD &= ~(1 << DDD3);
	PORTD |= (1 << PORTD3);
	
	// Configure INT1 to trigger on RISING edge
	//EICRA |= (1 << ISC11) | (1 << ISC10);
	
	// Configure INT1 to trigger on FALLING edge
	EICRA |= (1 << ISC11);
	EICRA &= ~(1 << ISC10);
	
	EIFR |= (1 << INTF1);
	EIMSK |= (1 << INT1);
}

// ISR(INT0_vect){pulses_left++;}  // Left wheel pulse
// ISR(INT1_vect){pulses_right++;} // Right wheel pulse


volatile uint32_t last_left_ms = 0;
volatile uint32_t last_right_ms = 0;
#define DEBOUNCE_MS 1  // 1 ms debounce
	
ISR(INT0_vect) {
	if ((milliseconds - last_left_ms) >= DEBOUNCE_MS) {
		pulses_left++;
		last_left_ms = milliseconds;
	}
}

ISR(INT1_vect) {
	if ((milliseconds - last_right_ms) >= DEBOUNCE_MS) {
		pulses_right++;
		last_right_ms = milliseconds;
	}
}
		

// Timer0 setup for 1ms tick
void timer0_init(void) {
	TCCR0A = (1 << WGM01);              // CTC mode
	TCCR0B = (1 << CS01) | (1 << CS00); // Prescaler 64
	OCR0A = 249;                        // 16MHz/64/250 = 1000Hz (1ms)
	TIMSK0 = (1 << OCIE0A);             // Enable compare match interrupt
}

ISR(TIMER0_COMPA_vect){milliseconds++;} // Timer increment

// Calculate distance for individual wheel in mm
float calculate_wheel_distance_mm(uint32_t pulses) {
	float revolutions = (float)pulses / PULSES_PER_ROTATION;
	return revolutions * WHEEL_CIRCUMFERENCE_MM;
}

// Calculate average distance traveled (center of vehicle)
float calculate_average_distance_mm(void) {
	cli();
	uint32_t left = pulses_left;
	uint32_t right = pulses_right;
	sei();
	
	float left_dist = calculate_wheel_distance_mm(left);
	float right_dist = calculate_wheel_distance_mm(right);
	
	return (left_dist + right_dist) / 2.0;
}

// Calculate speed for individual wheel in mm/s
float calculate_wheel_speed(uint32_t current_pulses, uint32_t last_pulses, uint32_t delta_time) {
	if (delta_time == 0) return 0.0;
	
	uint32_t delta_pulses = current_pulses - last_pulses;
	float revolutions = (float)delta_pulses / PULSES_PER_ROTATION;
	float distance_mm = revolutions * WHEEL_CIRCUMFERENCE_MM;
	
	return (distance_mm * 1000.0) / delta_time;
}

// Structure to hold odometry data
typedef struct {
	float left_distance_mm;
	float right_distance_mm;
	float average_distance_mm;
	float left_speed_mm_s;
	float right_speed_mm_s;
	float average_speed_mm_s;
	float rotation_deg;  // Estimated rotation angle
	uint32_t left_pulses;
	uint32_t right_pulses;
} Odometry;
	
// Update odometyr calculations
void update_odometry(Odometry* odom) {
	// Read values atomically
	cli();
	uint32_t current_left = pulses_left;
	uint32_t current_right = pulses_right;
	uint32_t current_time = milliseconds;
	sei();
	
	uint32_t delta_time = current_time - last_time_ms;
	
	// Store raw pulse counts
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
	
	// Calculate rotation (simplified - assumes differential drive)
	// Positive = clockwise rotation (right wheel moved more)
	float distance_diff = odom->right_distance_mm - odom->left_distance_mm;
	odom->rotation_deg = (distance_diff / WHEELBASE_MM) * (180.0 / 3.14159265359);
	
	// Update last values
	last_pulses_left = current_left;
	last_pulses_right = current_right;
	last_time_ms = current_time;
}

// Reset odometry counters
void reset_odometry(void) {
	cli();
	pulses_left = 0;
	pulses_right = 0;
	last_pulses_left = 0;
	last_pulses_right = 0;
	last_time_ms = milliseconds;
	sei();
}


//---------------------------------------------------------------------------------------------ULTRASONIC SENSOR----------------------------------------------------------------------------------------------------

#define PD5_TRIG PD5
#define ECHO_PD6 PD6

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



//-----------------------------------------------------------------------------------------------MAIN-LOOP-------------------------------------------------------------------------------------------------------
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
		// Hall sensor
		_delay_ms(10);
		update_odometry(&odom);

		// Hall sensor testing 
		/*
		uint32_t dist_mm = (uint32_t)(odom.average_distance_mm + 0.5); 
		uint32_t speed_mm_s = (uint32_t)(odom.average_speed_mm_s + 0.5);

		char buf[100]; 
		sprintf(buf, "L=%lu, R=%lu, Dist=%lumm, Speed=%lumm/s\n", 
				odom.left_pulses, 
				odom.right_pulses, 
				dist_mm,
				speed_mm_s); 
		for (char *p = buf; *p; p++) uart_send_char(*p); 
		*/
		
		// Send odometry data 
		int distance_cm = (int)((odom.average_distance_mm / 10.0) + 0.5); // convert mm to cm
		int speed_cm_s = (int)((odom.average_speed_mm_s / 10.0) + 0.5);   // convert mm/s to cm/s

		char buf[64]; 
		sprintf(buf, "PL=%d,PR=%d,D=%d,V=%d\n",
				odom.left_pulses,
				odom.right_pulses,
				distance_cm,
				speed_cm_s);

		for (char *p = buf; *p; p++) uart_send_char(*p);
		
		
		// Ultrasonic sensor
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


