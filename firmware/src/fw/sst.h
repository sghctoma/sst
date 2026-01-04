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
    RECORD,
    REC_STOP,
    SYNC_DATA,
    SERVE_TCP,
    MSC,
};
#define STATES_COUNT 9

#define CHUNK_TYPE_RATES    0x00
#define CHUNK_TYPE_TRAVEL   0x01
#define CHUNK_TYPE_MARKER   0x02
#define CHUNK_TYPE_IMU      0x03
#define CHUNK_TYPE_IMU_META 0x04

// Header for the entire SST file
struct sst_header {
    char magic[3]; // Always SST
    uint8_t version;
    uint32_t padding;
    time_t timestamp;
};

// Header for a single chunk
struct chunk_header {
    uint8_t type; // CHUNK_TYPE_*
    uint16_t length;
} __attribute__((packed));

// Samplerate for a given telemetry type.
// By convention there must be only one per type.
// All samplerate records must immediately follow the SST header.
struct samplerate_record {
    uint8_t type;  // CHUNK_TYPE_ TRAVEL/IMU
    uint16_t rate; // Hz
} __attribute__((packed));

// Travel telemetry record
struct travel_record {
    uint16_t fork_angle;
    uint16_t shock_angle;
};

// Meta for the IMU records.
// As IMU records are in raw device values which depend on hardware and/or configured sensitivity,
// how many units make 1 G/DPS is described in the meta.
// By convention there must be only one meta per sensor and they must precede all IMU records.
struct imu_meta_record {
    uint8_t location_id; // 0=Frame, 1=Fork, 2=Rear
    float accel_lsb_per_g;
    float gyro_lsb_per_dps;
} __attribute__((packed));

// IMU records do not encode which sensor are they from but they are read from hardware sequentially
// So it is assumed that the order of IMU records is the same as the order of meta records
// e.g. frame/fork/frame/fork/frame/fork....
struct imu_record {
    int16_t ax, ay, az;
    int16_t gx, gy, gz;
};

enum command { OPEN, DUMP_TRAVEL, DUMP_IMU, FINISH, MARKER };

#define BUFFER_SIZE 2048
#define FILENAME_LENGTH                                                                                                \
    10 // filename is always in 00000.SST format,
       // so length is always 10.
#endif /* _SST_H */
