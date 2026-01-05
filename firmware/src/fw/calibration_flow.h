#ifndef CALIBRATION_FLOW_H
#define CALIBRATION_FLOW_H

#include "../sensor/imu/imu_sensor.h"
#include "../sensor/travel/travel_sensor.h"
#include "ssd1306.h"
#include <stdbool.h>

// Context struct - holds all references needed for calibration
struct calibration_ctx {
    // Travel sensors
    struct travel_sensor *fork;
    struct travel_sensor *shock;

    // IMU sensors
    struct imu_sensor *imu_frame;
    struct imu_sensor *imu_fork;
    struct imu_sensor *imu_rear;

    // UI
    ssd1306_t *disp;
};

// Check if calibration is needed (file missing or button pressed)
// Returns true if calibration should be performed
bool calibration_check_needed(struct calibration_ctx *ctx);

// Run the full calibration sequence (blocking)
// Handles button polling and display updates internally
// Returns true on success, false after CAL_MAX_RETRIES failures
bool calibration_run(struct calibration_ctx *ctx);

// Load calibration from file and apply to sensors
// Call this before starting recording
// Returns true if at least one travel sensor is available
bool calibration_apply_to_sensors(struct calibration_ctx *ctx);

#endif // CALIBRATION_FLOW_H
