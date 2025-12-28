/*
 * odometry.h
 *
 * Created: 2025-11-11 13:30:09
 *  Author: oskna605
 */ 

#ifndef ODOMETRY_H
#define ODOMETRY_H

#include <stdint.h>

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

// Hall sensor initialization
void hall_left_init(void);
void hall_right_init(void);

// Timer0 initialization (1ms tick)
void timer0_init(void);

// Odometry calculations
void update_odometry(Odometry* odom);
void reset_odometry(void);
float get_distance_meters(void);
float get_speed_m_s(Odometry* odom);

#endif // ODOMETRY_H
