#ifndef MPU6050_H
#define MPU6050_H

#include <stdbool.h>
#include <stdint.h>

struct imu_sensor;

// Initialize hardware (I2C)
// Sets up GPIOs, resets sensor, checks WHO_AM_I, configures Ranges
// Sets imu->available = true on success, false on failure
void mpu6050_init(struct imu_sensor *imu);

// Check if sensor responds (WHO_AM_I check)
bool mpu6050_check_availability(struct imu_sensor *imu);

// Read raw 6-axis data: ax,ay,az,gx,gy,gz
void mpu6050_read_raw(struct imu_sensor *imu, int16_t raw[6]);

// Read temperature (raw 16-bit value)
int16_t mpu6050_read_temperature(struct imu_sensor *imu);

// Convert the raw value to degrees celsius
float mpu6050_temperature_celsius(struct imu_sensor *imu);

// Device specific constants
#define MPU6050_GYRO_TEMP_COEFF  0.0f   // Very different from unit to unit. You have to calculate yours
#define MPU6050_ACCEL_TEMP_COEFF 0.0f   // Very different from unit to unit. You have to calculate yours
#define MPU6050_TEMP_SCALE       340.0f // LSB/degC
#define MPU6050_TEMP_OFFSET      36.53f // degC at 0 LSB (based on formula T = R/340 + 36.53)

#endif // MPU6050_H
