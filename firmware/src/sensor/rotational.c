#include "hardware/i2c.h"

#include "sensor.h"
#include "as5600.h"
#include "../fw/hardware_config.h"
#include <stdint.h>

static uint16_t get_angle(i2c_inst_t *i2c, bool have_sensor, bool reversed) {
    static uint16_t value = 0xffff;
    if (have_sensor) {
        value = as5600_get_scaled_angle(i2c);
        if (reversed) {
            value = 4096 - value;
        }
    }

    return value;
}

static void rotational_sensor_init(struct sensor *sensor) {
    i2c_init(sensor->comm.i2c.instance, 1000000);
    gpio_set_function(sensor->comm.i2c.sda_gpio, GPIO_FUNC_I2C);
    gpio_set_function(sensor->comm.i2c.scl_gpio, GPIO_FUNC_I2C);
    gpio_pull_up(sensor->comm.i2c.sda_gpio);
    gpio_pull_up(sensor->comm.i2c.scl_gpio);        
}

static bool rotational_sensor_check_availabilityt(struct sensor *sensor) {
    sensor->available = as5600_connected(sensor->comm.i2c.instance) &&
                        as5600_detect_magnet(sensor->comm.i2c.instance);
    return sensor->available;
}

static bool rotational_sensor_start(struct sensor *sensor, uint16_t baseline, bool inverted) {
    if (!sensor->check_availability(sensor)) {
        return false;
    }

    sensor->inverted = inverted;
    
    as5600_set_start_position(sensor->comm.i2c.instance, baseline);
    // Power down tha DAC, we don't need it.
    as5600_conf_set_output(sensor->comm.i2c.instance, OUTPUT_PWM);
    // Helps with those 1-quanta-high rapid spikes.
    as5600_conf_set_hysteresis(sensor->comm.i2c.instance, HYSTERESIS_2_LSB);
    // 0.55 ms step response delay, 0.03 RMS output noise.
    as5600_conf_set_slow_filter(sensor->comm.i2c.instance, SLOW_FILTER_4x);
    // TODO: experiment with fast filter.
    as5600_conf_set_fast_filter_threshold(sensor->comm.i2c.instance, FAST_FILTER_THRESHOLD_6_LSB);
    return true;
}

static uint16_t rotational_sensor_measure(struct sensor *sensor) {
    static uint16_t value = 0xffff;
    if (sensor->available) {
        value = as5600_get_scaled_angle(sensor->comm.i2c.instance);
        if (sensor->inverted) {
            value = 4096 - value;
        }
    }

    return value;
}

static void rotational_sensor_calibrate_expanded(struct sensor *sensor) {
    sensor->baseline = 0xffff;
    if (sensor->check_availability(sensor)) {
        sensor->baseline = as5600_get_raw_angle(sensor->comm.i2c.instance);
        as5600_set_start_position(sensor->comm.i2c.instance, sensor->baseline);
    }
}

static void rotational_sensor_calibrate_compressed(struct sensor *sensor) {
    sensor->baseline = 0xffff;
    if (sensor->check_availability(sensor)) {
        // We check rotation direction by comparing the measured value in a compressed
        // state to 2048. This value means 180 degrees, which would be impossible in a
        // triangle, so we know direction is reversed.
        sensor->baseline = as5600_get_start_position(sensor->comm.i2c.instance);
        sensor->inverted = as5600_get_scaled_angle(sensor->comm.i2c.instance) > 2048;
    }   
}

#ifndef FORK_LINEAR
struct sensor fork_sensor = {
    .comm.i2c = {FORK_I2C, FORK_PIN_SCL, FORK_PIN_SDA},
    .init = rotational_sensor_init,
    .check_availability = rotational_sensor_check_availabilityt,
    .start = rotational_sensor_start,
    .calibrate_expanded = rotational_sensor_calibrate_expanded,
    .calibrate_compressed = rotational_sensor_calibrate_compressed,
    .measure = rotational_sensor_measure,
};
#endif

#ifndef SHOCK_LINEAR
struct sensor shock_sensor = {
    .comm.i2c = {SHOCK_I2C, SHOCK_PIN_SCL, SHOCK_PIN_SDA},
    .init = rotational_sensor_init,
    .check_availability = rotational_sensor_check_availabilityt,
    .start = rotational_sensor_start,
    .calibrate_expanded = rotational_sensor_calibrate_expanded,
    .calibrate_compressed = rotational_sensor_calibrate_compressed,
    .measure = rotational_sensor_measure,
};
#endif
