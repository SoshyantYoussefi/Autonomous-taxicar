/*
 * pid.h
 *
 * Created: 2025-11-17 14:11:37
 *  Author: oskna605
 */ 

#ifndef PID_H
#define PID_H

#include <stdint.h>
#include "opcodes.h"

typedef struct {
	float PID_P;
	float PID_I;
	float PID_D;
} PID_t;

extern PID_t pid_current;

// Default PID constants
#define PID_P_DEFAULT 2.0
#define PID_I_DEFAULT 0.1
#define PID_D_DEFAULT 0.0

void send_current_pid(void);
void update_pid_p(void);
void update_pid_i(void);
void update_pid_d(void);

#endif

