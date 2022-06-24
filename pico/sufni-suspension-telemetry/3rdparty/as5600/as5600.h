/*
 * Copyright (c) 2022 Tamás Szakály (sghctoma)
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#ifndef _AS5600_H
#define _AS5600_H

#include "class/cdc/cdc.h"
#include <pico/stdlib.h>
#include <hardware/i2c.h>

#ifdef __cplusplus
extern "C" {
#endif

enum as5600_magnet_strength {
    MAGNET_OK         =  1,
    MAGNET_MISSING    = -1,
    MAGNET_WEAK       = -2,
    MAGNET_TOO_STRONG = -3
};

enum as5600_burn_result {
    BURN_SUCCESS   =  1,
    BURN_NO_MAGNET = -1,
    BURN_LIMIT     = -2,
    BURN_NO_ANGLES = -3,
    BURN_ANGLE_LOW = -4
};

enum as5600_power_mode {
    POWER_NOM  = 0,
    POWER_LPM1 = 1,
    POWER_LPM2 = 2,
    POWER_LPM3 = 3,
};

enum as5600_hysteresis {
    HYSTERESIS_OFF   = 0,
    HYSTERESIS_1_LSB = 1,
    HYSTERESIS_2_LSB = 1,
    HYSTERESIS_3_LSB = 1,
};

enum as5600_output { 
    OUTPUT_ANALOG_FULL    = 0, // full range from 0% to 100% between GND and VDD
    OUTPUT_ANALOG_REDUCED = 1, // reduced range from 10% to 90% between GND and VDD
    OUTPUT_PWM            = 2,
};

enum as5600_pwm_frequency {
    PWM_FREQUENCY_115Hz = 0,
    PWM_FREQUENCY_230Hz = 0,
    PWM_FREQUENCY_460Hz = 0,
    PWM_FREQUENCY_920Hz = 0,
};

enum as5600_slow_filter {
    SLOW_FILTER_16x = 0,
    SLOW_FILTER_8x  = 1,
    SLOW_FILTER_4x  = 2,
    SLOW_FILTER_2x  = 3,
};

enum as5600_fast_filter_threshold {
    FAST_FILTER_THRESHOLD_SLOW_ONLY = 0,
    FAST_FILTER_THRESHOLD_6_LSB     = 1,
    FAST_FILTER_THRESHOLD_7_LSB     = 2,
    FAST_FILTER_THRESHOLD_9_LSB     = 3,
    FAST_FILTER_THRESHOLD_18_LSB    = 4,
    FAST_FILTER_THRESHOLD_21_LSB    = 5,
    FAST_FILTER_THRESHOLD_24_LSB    = 6,
    FAST_FILTER_THRESHOLD_10_LSB    = 7,
};

bool as5600_connected(i2c_inst_t *i2c);

// ----------------------------------------------------------------------------
// Get/set angles
uint16_t as5600_set_max_angle(i2c_inst_t *i2c, uint16_t angle);
uint16_t as5600_get_max_angle(i2c_inst_t *i2c);

uint16_t as5600_set_start_position(i2c_inst_t *i2c, uint16_t angle);
uint16_t as5600_get_start_position(i2c_inst_t *i2c);

uint16_t as5600_set_end_position(i2c_inst_t *i2c, uint16_t angle);
uint16_t as5600_get_end_position(i2c_inst_t *i2c);

// ----------------------------------------------------------------------------
// Measurements
uint16_t as5600_get_raw_angle(i2c_inst_t *i2c);
uint16_t as5600_get_scaled_angle(i2c_inst_t *i2c);

// ----------------------------------------------------------------------------
// Magnet detection
bool as5600_detect_magnet(i2c_inst_t *i2c);
enum as5600_magnet_strength as5600_get_magnet_strength(i2c_inst_t *i2c);
int as5600_get_agc(i2c_inst_t *i2c);
uint16_t as5600_get_magnitude(i2c_inst_t *i2c);

// ----------------------------------------------------------------------------
// Configuration
uint16_t as5600_get_conf(i2c_inst_t *i2c);
void as5600_set_conf(i2c_inst_t *i2c, uint16_t conf);

enum as5600_power_mode as5600_conf_get_power_mode(i2c_inst_t *i2c);
void as5600_conf_set_power_mode(i2c_inst_t *i2c, enum as5600_power_mode val);

enum as5600_hysteresis as5600_conf_get_hysteresis(i2c_inst_t *i2c);
void as5600_conf_set_hysteresis(i2c_inst_t *i2c, enum as5600_hysteresis val);

enum as5600_output as5600_conf_get_output(i2c_inst_t *i2c);
void as5600_conf_set_output(i2c_inst_t *i2c, enum as5600_output val);

enum as5600_pwm_frequency as5600_conf_get_pwm_frequency(i2c_inst_t *i2c);
void as5600_conf_set_pwm_frequency(i2c_inst_t *i2c, enum as5600_pwm_frequency val);

enum as5600_slow_filter as5600_conf_get_slow_filter(i2c_inst_t *i2c);
void as5600_conf_set_slow_filter(i2c_inst_t *i2c, enum as5600_slow_filter val);

enum as5600_fast_filter_threshold as5600_conf_get_fast_filter_threshold(i2c_inst_t *i2c);
void as5600_conf_set_fast_filter_threshold(i2c_inst_t *i2c, enum as5600_fast_filter_threshold val);

bool as5600_conf_get_watchdog(i2c_inst_t *i2c);
void as5600_conf_set_watchdog(i2c_inst_t *i2c, bool enabled);

// ----------------------------------------------------------------------------
// Permanent settings
uint8_t as5600_get_burn_count(i2c_inst_t *i2c);
enum as5600_burn_result as5600_burn_angle(i2c_inst_t *i2c);
int as5600_burn_setting(i2c_inst_t *i2c);

#endif
