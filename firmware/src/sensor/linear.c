#include "hardware/adc.h"

#include "../fw/hardware_config.h"
#include "sensor.h"
#include <stdint.h>

static void linear_sensor_init(struct sensor *sensor) { adc_gpio_init(sensor->comm.adc.gpio); }

static bool linear_sensor_check_availability(struct sensor *sensor) {
    sensor->available = true;
    return true; // XXX: AFAIK there is no way to check this for the ADC.
}

static bool linear_sensor_start(struct sensor *sensor, uint16_t baseline, bool inverted) { return true; }

static uint16_t linear_sensor_measure(struct sensor *sensor) {
    adc_select_input(sensor->comm.adc.adc_num);
    return adc_read() - sensor->baseline;
}

static void linear_sensor_calibrate_expanded(struct sensor *sensor) {
    adc_select_input(sensor->comm.adc.adc_num);
    sensor->baseline = adc_read();
}

static void linear_sensor_calibrate_compressed(struct sensor *sensor) { sensor->inverted = false; }

#ifdef FORK_LINEAR
struct sensor fork_sensor = {
    .comm.adc = {FORK_ADC, FORK_PIN_ADC},
    .init = linear_sensor_init,
    .check_availability = linear_sensor_check_availability,
    .start = linear_sensor_start,
    .calibrate_expanded = linear_sensor_calibrate_expanded,
    .calibrate_compressed = linear_sensor_calibrate_compressed,
    .measure = linear_sensor_measure,
};
#endif

#ifdef SHOCK_LINEAR
struct sensor shock_sensor = {
    .comm.adc = {SHOCK_ADC, SHOCK_PIN_ADC},
    .init = linear_sensor_init,
    .check_availability = linear_sensor_check_availability,
    .start = linear_sensor_start,
    .calibrate_expanded = linear_sensor_calibrate_expanded,
    .calibrate_compressed = linear_sensor_calibrate_compressed,
    .measure = linear_sensor_measure,
};
#endif
