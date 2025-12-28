#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdint.h>
#include <stdbool.h>


#define PID_P 1.5
#define PID_I 0.1
#define PID_D 1.0


void servo_init(void);
void set_servo_value(uint16_t percent);
void servo_pid(int8_t error_angle);

void clock_init(void);          // startar 1ms-tick
uint32_t millis(void);          // nuvarande ms-räknare
bool ms_elapsed(uint32_t *t, uint16_t period_ms); // "har period_ms passerat?


void servo_tick_run(int8_t current_error); // kör PID vid tidslucka

extern volatile float runtime_PID_P;
extern volatile float runtime_PID_I;
extern volatile float runtime_PID_D;
