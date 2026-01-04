#include "imu_sensor.h"
#include <math.h>
#include <pico/stdlib.h>
#include <stdlib.h>
#include <string.h>

bool imu_sensor_init(struct imu_sensor *imu) {
    if (imu->init) {
        imu->init(imu);
    }
    return imu->available;
}

bool imu_sensor_available(struct imu_sensor *imu) {
    if (imu->check_availability) {
        return imu->check_availability(imu);
    }
    return false;
}

void imu_sensor_read_raw(struct imu_sensor *imu, int16_t *ax, int16_t *ay, int16_t *az, int16_t *gx, int16_t *gy,
                         int16_t *gz) {
    int16_t raw[6];
    if (imu->read_raw) {
        imu->read_raw(imu, raw);
        *ax = raw[0];
        *ay = raw[1];
        *az = raw[2];
        *gx = raw[3];
        *gy = raw[4];
        *gz = raw[5];
    } else {
        *ax = *ay = *az = *gx = *gy = *gz = 0;
    }
}

void imu_sensor_read(struct imu_sensor *imu, int16_t *ax, int16_t *ay, int16_t *az, int16_t *gx, int16_t *gy,
                     int16_t *gz) {
    // Read raw values
    int16_t raw[6];
    if (imu->read_raw) {
        imu->read_raw(imu, raw);
    } else {
        memset(raw, 0, sizeof(raw));
    }

    // Calculate temperature difference from calibration point if supported
    float temp_diff = 0.0f;
    if (imu->read_temperature && imu->temp_scale > 0.0f) {
        int16_t current_temp = imu->read_temperature(imu);
        temp_diff = (float)(current_temp - imu->calibration.cal_temperature) / imu->temp_scale;
    }

    // Apply temperature-compensated bias
    float a[3], g[3];
    for (int i = 0; i < 3; i++) {
        a[i] = raw[i] - imu->calibration.accel_bias[i] - imu->accel_temp_coeff * temp_diff;
        g[i] = raw[3 + i] - imu->calibration.gyro_bias[i] - imu->gyro_temp_coeff * temp_diff;
    }

    // Apply rotation matrix: bike = R x sensor
    float (*R)[3] = imu->calibration.rotation.matrix;

    *ax = (int16_t)(R[0][0] * a[0] + R[0][1] * a[1] + R[0][2] * a[2]);
    *ay = (int16_t)(R[1][0] * a[0] + R[1][1] * a[1] + R[1][2] * a[2]);
    *az = (int16_t)(R[2][0] * a[0] + R[2][1] * a[1] + R[2][2] * a[2]);

    *gx = (int16_t)(R[0][0] * g[0] + R[0][1] * g[1] + R[0][2] * g[2]);
    *gy = (int16_t)(R[1][0] * g[0] + R[1][1] * g[1] + R[1][2] * g[2]);
    *gz = (int16_t)(R[2][0] * g[0] + R[2][1] * g[1] + R[2][2] * g[2]);
}

float imu_sensor_get_temperature_celsius(struct imu_sensor *imu) {
    if (imu->temperature_celsius) {
        return imu->temperature_celsius(imu);
    }
    if (imu->read_temperature && imu->temp_scale > 0.0f) {
        int16_t raw = imu->read_temperature(imu);
        return imu->temp_offset + (float)raw / imu->temp_scale;
    }
    return 0.0f;
}

// Calibration

static void normalize(float *v, float *out) {
    float mag = sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    if (mag > 0.0001f) {
        out[0] = v[0] / mag;
        out[1] = v[1] / mag;
        out[2] = v[2] / mag;
    } else {
        out[0] = 0;
        out[1] = 0;
        out[2] = 0;
    }
}

static float dot_product(float *a, float *b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

static void cross_product(float *a, float *b, float *out) {
    out[0] = a[1] * b[2] - a[2] * b[1];
    out[1] = a[2] * b[0] - a[0] * b[2];
    out[2] = a[0] * b[1] - a[1] * b[0];
}

static void build_rotation_matrix(float g_sensor[3], float f_sensor[3], struct imu_rotation *rot) {
    // g_sensor = gravity vector in sensor frame (points UP in bike frame)
    // f_sensor = forward acceleration in sensor frame (points FORWARD in bike frame)

    // Normalize gravity -> this is bike's Z axis in sensor coords
    float z[3];
    normalize(g_sensor, z);

    // Remove Z component from forward vector, normalize -> bike's X axis
    float x[3];
    float dot_fz = dot_product(f_sensor, z);
    for (int i = 0; i < 3; i++) { x[i] = f_sensor[i] - dot_fz * z[i]; }
    normalize(x, x);

    // Y = Z x X (cross product) -> bike's Y axis (left)
    float y[3];
    cross_product(z, x, y);
    // Already normalized since Z and X are orthonormal

    // Build rotation matrix (rows are basis vectors)
    // Row 0 = X (forward), Row 1 = Y (left), Row 2 = Z (up)
    for (int i = 0; i < 3; i++) {
        rot->matrix[0][i] = x[i];
        rot->matrix[1][i] = y[i];
        rot->matrix[2][i] = z[i];
    }
}

#define CALIBRATION_SAMPLES 100

void imu_sensor_calibrate_stationary(struct imu_sensor *imu) {
    int32_t gyro_sum[3] = {0};
    int32_t accel_sum[3] = {0};

    // Record temperature at start of calibration
    if (imu->read_temperature) {
        imu->calibration.cal_temperature = imu->read_temperature(imu);
    }

    for (int i = 0; i < CALIBRATION_SAMPLES; i++) {
        int16_t raw[6];
        if (imu->read_raw) {
            imu->read_raw(imu, raw);
        } else {
            memset(raw, 0, sizeof(raw));
        }
        accel_sum[0] += raw[0]; // ax
        accel_sum[1] += raw[1]; // ay
        accel_sum[2] += raw[2]; // az
        gyro_sum[0] += raw[3];  // gx
        gyro_sum[1] += raw[4];  // gy
        gyro_sum[2] += raw[5];  // gz
        sleep_ms(10);
    }

    imu->calibration.gyro_bias[0] = gyro_sum[0] / CALIBRATION_SAMPLES;
    imu->calibration.gyro_bias[1] = gyro_sum[1] / CALIBRATION_SAMPLES;
    imu->calibration.gyro_bias[2] = gyro_sum[2] / CALIBRATION_SAMPLES;

    // Store gravity vector (will be normalized later)
    imu->g_sensor[0] = accel_sum[0] / (float)CALIBRATION_SAMPLES;
    imu->g_sensor[1] = accel_sum[1] / (float)CALIBRATION_SAMPLES;
    imu->g_sensor[2] = accel_sum[2] / (float)CALIBRATION_SAMPLES;
}

void imu_sensor_calibrate_tilted(struct imu_sensor *imu) {
    // Sample gravity while bike is tilted front-up
    int32_t accel_sum[3] = {0};

    for (int i = 0; i < CALIBRATION_SAMPLES; i++) {
        int16_t raw[6];
        if (imu->read_raw) {
            imu->read_raw(imu, raw);
        } else {
            memset(raw, 0, sizeof(raw));
        }
        accel_sum[0] += raw[0];
        accel_sum[1] += raw[1];
        accel_sum[2] += raw[2];
        sleep_ms(10);
    }

    float g_tilted[3];
    g_tilted[0] = accel_sum[0] / (float)CALIBRATION_SAMPLES;
    g_tilted[1] = accel_sum[1] / (float)CALIBRATION_SAMPLES;
    g_tilted[2] = accel_sum[2] / (float)CALIBRATION_SAMPLES;

    // When front is up, accelerometer reaction tilts forward
    // Difference (tilted - level) points forward
    float f_sensor[3];
    f_sensor[0] = g_tilted[0] - imu->g_sensor[0];
    f_sensor[1] = g_tilted[1] - imu->g_sensor[1];
    f_sensor[2] = g_tilted[2] - imu->g_sensor[2];

    build_rotation_matrix(imu->g_sensor, f_sensor, &imu->calibration.rotation);
}

#define LEVEL_THRESHOLD_DEG      5.0f
#define STATIONARY_THRESHOLD_DPS 10.0f
#define ACCEL_THRESHOLD_G        0.05f
#define INTERPRET_SAMPLES        16

// Debug interpretation
// Samples a short number of samples
// Interpretation is valid for a static bike and falls apart when riding due to outside forces
// Helps to validate sensor implementation, orientation, sensitivity, etc.

void imu_sensor_interpret(struct imu_sensor *imu, struct imu_interpretation *result) {
    int32_t ax_sum = 0, ay_sum = 0, az_sum = 0;
    int32_t gx_sum = 0, gy_sum = 0, gz_sum = 0;

    for (int i = 0; i < INTERPRET_SAMPLES; i++) {
        int16_t ax, ay, az, gx, gy, gz;
        imu_sensor_read(imu, &ax, &ay, &az, &gx, &gy, &gz);
        ax_sum += ax;
        ay_sum += ay;
        az_sum += az;
        gx_sum += gx;
        gy_sum += gy;
        gz_sum += gz;
        sleep_ms(10);
    }

    float ax_avg = ax_sum / (float)INTERPRET_SAMPLES;
    float ay_avg = ay_sum / (float)INTERPRET_SAMPLES;
    float az_avg = az_sum / (float)INTERPRET_SAMPLES;
    float gx_avg = gx_sum / (float)INTERPRET_SAMPLES;
    float gy_avg = gy_sum / (float)INTERPRET_SAMPLES;
    float gz_avg = gz_sum / (float)INTERPRET_SAMPLES;

    // Convert acceleration to g units
    result->accel_forward_g = ax_avg / imu->accel_lsb_per_g;
    result->accel_left_g = ay_avg / imu->accel_lsb_per_g;
    result->accel_up_g = az_avg / imu->accel_lsb_per_g;

    // Calculate pitch and roll from accelerometer
    // pitch = atan2(ax, az) - positive = front up
    // roll = atan2(ay, az) - positive = tilted right
    float pitch_rad = atan2f(ax_avg, az_avg);
    float roll_rad = atan2f(ay_avg, az_avg);
    result->pitch_deg = pitch_rad * 180.0f / (float)M_PI;
    result->roll_deg = roll_rad * 180.0f / (float)M_PI;

    // Convert gyro to degrees per second
    result->roll_rate_dps = gx_avg / imu->gyro_lsb_per_dps;  // rotation around X (forward)
    result->pitch_rate_dps = gy_avg / imu->gyro_lsb_per_dps; // rotation around Y (left)
    result->yaw_rate_dps = gz_avg / imu->gyro_lsb_per_dps;   // rotation around Z (up)

    // Determine pitch state
    if (result->pitch_deg > LEVEL_THRESHOLD_DEG) {
        result->pitch_state = IMU_PITCH_FRONT_UP;
    } else if (result->pitch_deg < -LEVEL_THRESHOLD_DEG) {
        result->pitch_state = IMU_PITCH_FRONT_DOWN;
    } else {
        result->pitch_state = IMU_PITCH_LEVEL;
    }

    // Determine roll state
    if (result->roll_deg > LEVEL_THRESHOLD_DEG) {
        result->roll_state = IMU_ROLL_RIGHT;
    } else if (result->roll_deg < -LEVEL_THRESHOLD_DEG) {
        result->roll_state = IMU_ROLL_LEFT;
    } else {
        result->roll_state = IMU_ROLL_LEVEL;
    }

    // Detect rotation
    result->is_rotating = fabsf(result->roll_rate_dps) > STATIONARY_THRESHOLD_DPS ||
                          fabsf(result->pitch_rate_dps) > STATIONARY_THRESHOLD_DPS ||
                          fabsf(result->yaw_rate_dps) > STATIONARY_THRESHOLD_DPS;

    // Detect horizontal acceleration (movement)
    float horiz_accel =
        sqrtf(result->accel_forward_g * result->accel_forward_g + result->accel_left_g * result->accel_left_g);
    result->is_accelerating = horiz_accel > ACCEL_THRESHOLD_G;
}