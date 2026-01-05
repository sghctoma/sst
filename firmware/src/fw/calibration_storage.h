#ifndef CALIBRATION_STORAGE_H
#define CALIBRATION_STORAGE_H

#include <stdbool.h>
#include <stdint.h>

// Identifiers for calibration file sections
#define TRAVEL_MAGIC    'T'
#define IMU_FRAME_MAGIC 'I'
#define IMU_FORK_MAGIC  'F'
#define IMU_REAR_MAGIC  'R'

// Data structures for calibration storage

struct travel_cal_data {
    uint16_t fork_baseline;
    uint8_t fork_inverted;
    uint16_t shock_baseline;
    uint8_t shock_inverted;
};

struct imu_cal_data {
    bool present;
    int16_t gyro_bias[3];
    int16_t accel_bias[3];
    float rotation[3][3];
    int16_t cal_temperature;
};

struct calibration_data {
    struct travel_cal_data travel;
    struct imu_cal_data imu_frame;
    struct imu_cal_data imu_fork;
    struct imu_cal_data imu_rear;
};

// Check if CALIBRATION file exists
bool calibration_file_exists(void);

// Load all calibration data from file
// Returns true on success, false if file missing or invalid
bool calibration_load(struct calibration_data *data);

// Create file with travel calibration data (overwrites existing)
// The travel calibration data is mandatory for a valid calibration file
bool calibration_create_with_travel(const struct travel_cal_data *travel);

// Append IMU calibration data to the end of an existing file
// Magic identifies which IMU is appended
// Doesn't validate the file or verify if no data exists for the given magic
bool calibration_append_imu(char magic, const struct imu_cal_data *imu);

#endif // CALIBRATION_STORAGE_H
