#ifndef _SST_H
#define _SST_H

#include "../net/tcpclient.h"
#include "../ui/pushbutton.h"
#include "as5600.h"
#include "ssd1306.h"
#include "tusb.h"

enum state {
    IDLE,
    SLEEP,
    WAKING,
    REC_START,
    GPS_WAIT,
    RECORD,
    REC_STOP,
    SYNC_DATA,
    SERVE_TCP,
    MSC,
    CAL_IDLE_1,
    CAL_EXP,
    CAL_IDLE_2,
    CAL_COMP,
};
#define STATES_COUNT 14

#define CHUNK_TYPE_RATES     0x00
#define CHUNK_TYPE_TELEMETRY 0x01
#define CHUNK_TYPE_MARKER    0x02

#define CHUNK_TYPE_GPS 0x05

struct chunk_header {
    uint8_t type;
    uint16_t length;
} __attribute__((packed));

struct rate_entry {
    uint8_t type;
    uint16_t rate;
} __attribute__((packed));

struct header {
    char magic[3];
    uint8_t version;
    uint32_t padding;
    time_t timestamp;
};

struct record {
    uint16_t fork_angle;
    uint16_t shock_angle;
};

struct gps_record {
    uint32_t date;    // UTC date in YYYYMMDD format
    uint32_t time_ms; // UTC time of day in milliseconds

    double latitude;
    double longitude;
    float altitude;

    float speed;
    float heading;

    uint8_t fix_mode; // 0 = none, 1 = 2D, 2 = 3D
    uint8_t satellites;
    float epe_2d;
    float epe_3d;
} __attribute__((packed));

enum command { OPEN, DUMP, DUMP_GPS, FINISH, MARKER };

#define BUFFER_SIZE     2048
#define GPS_BUFFER_SIZE 30
#define FILENAME_LENGTH                                                                                                \
    10 // filename is always in 00000.SST format,
       // so length is always 10.
#endif /* _SST_H */
