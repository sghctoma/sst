#ifndef _SST_H
#define _SST_H

#include "tusb.h"
#include "as5600.h"
#include "ssd1306.h"
#include "../net/tcpclient.h"
#include "../ui/pushbutton.h"

enum state {
    IDLE,
    SLEEP,
    WAKING,
    REC_START,
    RECORD,
    REC_STOP,
    SYNC_DATA,
    SERVE_TCP,
    MSC,
};
#define STATES_COUNT 9

struct header {
    char magic[3];
    uint8_t version;
    uint16_t sample_rate;
    time_t timestamp;
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

#define BUFFER_SIZE 2048
#define FILENAME_LENGTH 10 // filename is always in 00000.SST format,
                           // so length is always 10.
#endif /* _SST_H */
