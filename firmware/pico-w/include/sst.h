#ifndef _SST_H
#define _SST_H

#include "hw_config.h"
#include "tusb.h"
#include "ssd1306_spi.h"
#include "as5600.h"
#include "ntp.h"
#include "tcpclient.h"
#include "pushbutton.h"

enum state {
    IDLE,
    SLEEP,
    WAKING,
    RECORD,
    CONNECT,
    SYNC_TIME,
    SYNC_DATA,
    MSC,
};

struct header {
    char magic[3];
    uint8_t version;
    uint16_t sample_rate;
};

struct record {
    uint16_t fork_angle;
    uint16_t shock_angle;
};

enum command {
    OPEN,
    DUMP,
    FINISH
};

#define BUFFER_SIZE 2048 // Not declared as a static const, because variable
                         // length arrays are not a thing in C.

#define FILENAME_LENGTH 10 // filename is always in 00000.SST format,
                           // so length is always 10.
#endif /* _SST_H */
