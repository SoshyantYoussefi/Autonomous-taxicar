#ifndef OPCODES_H
#define OPCODES_H

typedef enum
{

    /************ FROM GUI ************/
    MOVE_COMMAND = 0x01,
    VAXLING = 0x02,

    /************ FROM CAM ************/
    OFFSET_ANGLE = 0x10,

    /************ PID / CONTROL ************/
    OPCODE_SET_PID_P = 0x11,
    OPCODE_SET_PID_I = 0x12,
    OPCODE_SET_PID_D = 0x20,
    // OPCODE_REQUEST_PID_P  = 0x21,
    // OPCODE_REQUEST_PID_I  = 0x13,
    // OPCODE_REQUEST_PID_D  = 0x31,

    /************ SENSOR ************/
    OPCODE_HALL = 0x03,
    OPCODE_CALIB_HALL = 0x30,
    OPCODE_ULTRASONIC = 0x40,
    OPCODE_SET_ULTRA_DIST = 0x04,
    OPCODE_HALL_SPEED = 0x05,

    /*************** ***************/
    OPCODE_CAM_STOP = 0xFF,

    OPCODE_ALGO_STOP = 0x41,

    OPCODE_ALGO_START = 0x40,
    OPCODE_OBSTACLE_STOP = 0x07

    

} Opcode;

#endif