#ifndef IMU_SENSOR_H
#define IMU_SENSOR_H

#include <hardware/i2c.h>
#include <hardware/spi.h>
#include <stdbool.h>
#include <stdint.h>

enum imu_type {
    IMU_TYPE_LSM6DSO,
    IMU_TYPE_MPU6050,
};

enum imu_protocol {
    IMU_PROTOCOL_I2C,
    IMU_PROTOCOL_SPI,
};

struct imu_i2c_comm {
    i2c_inst_t *instance;
    uint8_t address;
    uint sda_gpio;
    uint scl_gpio;
};

struct imu_spi_comm {
    spi_inst_t *instance;
    uint cs_gpio;
    uint sck_gpio;
    uint mosi_gpio;
    uint miso_gpio;
};

union imu_comm {
    struct imu_i2c_comm i2c;
    struct imu_spi_comm spi;
};

// 3D Rotation Matrix
// transforms sensor frame to bike frame
struct imu_rotation {
    float matrix[3][3];
};

// Calibration Data
struct imu_calibration {
    // Gyroscope bias (raw sensor units, subtracted from readings)
    int16_t gyro_bias[3];

    // Accelerometer bias (raw sensor units, subtracted from readings)
    // Note: Currently set to 0 (gravity is kept in readings).
    int16_t accel_bias[3];

    // Rotation matrix: sensor frame -> bike frame
    // Adjusts the sensor readings so:
    //  - X going positive is bike forward
    //  - Y going positive is bike left (brake side)
    //  - Z going positive is bike up
    struct imu_rotation rotation;

    // Temperature at calibration (raw sensor units)
    int16_t cal_temperature;
};

// Default calibration (identity rotation, zero bias)
#define IMU_CALIBRATION_DEFAULT                                                                                        \
    {.gyro_bias = {0, 0, 0},                                                                                           \
     .accel_bias = {0, 0, 0},                                                                                          \
     .rotation = {.matrix = {{1, 0, 0}, {0, 1, 0}, {0, 0, 1}}},                                                        \
     .cal_temperature = 0}

// Main IMU Sensor Struct
struct imu_sensor {
    enum imu_type type;
    enum imu_protocol protocol;
    union imu_comm comm;

    volatile bool available;
    struct imu_calibration calibration;

    // Temperature compensation parameters
    float gyro_temp_coeff;  // LSB/degC
    float accel_temp_coeff; // LSB/degC
    float temp_scale;       // LSB/degC (for the temperature sensor itself)
    float temp_offset;      // degC at raw value 0

    // Scale factors (set by driver based on config)
    float accel_lsb_per_g;  // LSB per 1g (e.g., 4096 for ±8g)
    float gyro_lsb_per_dps; // LSB per 1 deg/s (e.g., 28.57 for 1000dps)

    // Function pointers (set by driver)
    void (*init)(struct imu_sensor *imu);
    bool (*check_availability)(struct imu_sensor *imu);
    void (*read_raw)(struct imu_sensor *imu, int16_t raw[6]); // ax,ay,az,gx,gy,gz
    int16_t (*read_temperature)(struct imu_sensor *imu);      // Raw sensor units
    float (*temperature_celsius)(struct imu_sensor *imu);     // Degrees Celsius

    // Internal calibration state
    float g_sensor[3];
};

// API Functions

// Initialize the IMU sensor
// Returns: true if successful
bool imu_sensor_init(struct imu_sensor *imu);

// Check if IMU is available/responding
bool imu_sensor_available(struct imu_sensor *imu);

// Phase 1 calibration: Call while bike is stationary and level
// - Determines gyro bias (averages samples)
// - Records gravity vector for orientation calibration
void imu_sensor_calibrate_stationary(struct imu_sensor *imu);

// Phase 2 calibration: Call while bike is tilted front-up (on rear tire)
// - Samples gravity while tilted
// - Computes forward direction from gravity shift
// - Builds rotation matrix
void imu_sensor_calibrate_tilted(struct imu_sensor *imu);

// Read calibrated values (bias subtracted, rotated to bike frame)
// Temperature compensated, if supported by sensor.
// Output: ax, ay, az in raw units, bike frame (X=forward, Y=left, Z=up)
//         gx, gy, gz in raw units, bike frame
void imu_sensor_read(struct imu_sensor *imu, int16_t *ax, int16_t *ay, int16_t *az, int16_t *gx, int16_t *gy,
                     int16_t *gz);

// Read raw values (no calibration applied, sensor frame)
void imu_sensor_read_raw(struct imu_sensor *imu, int16_t *ax, int16_t *ay, int16_t *az, int16_t *gx, int16_t *gy,
                         int16_t *gz);

// Get temperature in degrees Celsius
float imu_sensor_get_temperature_celsius(struct imu_sensor *imu);

// Interpretation state enums
enum imu_pitch_state {
    IMU_PITCH_LEVEL,
    IMU_PITCH_FRONT_UP,
    IMU_PITCH_FRONT_DOWN,
};

enum imu_roll_state {
    IMU_ROLL_LEVEL,
    IMU_ROLL_LEFT,
    IMU_ROLL_RIGHT,
};

// Interpretation API. Used mostly for debugging

struct imu_interpretation {
    // Acceleration in g units (bike frame)
    float accel_forward_g;
    float accel_left_g;
    float accel_up_g;

    // Tilt angles in degrees (accelerometer based, so no yaw)
    float pitch_deg;
    float roll_deg;

    // Rotation rates in degrees per second (gyro based)
    float yaw_rate_dps;
    float pitch_rate_dps;
    float roll_rate_dps;

    // State flags
    enum imu_pitch_state pitch_state;
    enum imu_roll_state roll_state;
    bool is_rotating;
    bool is_accelerating;
};
// Sample IMU and interpret orientation/motion state
// Fills the provided struct with readings and state flags
void imu_sensor_interpret(struct imu_sensor *imu, struct imu_interpretation *result);
#endif // IMU_SENSOR_H
