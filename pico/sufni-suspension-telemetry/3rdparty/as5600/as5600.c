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

#include "as5600.h"
#include <stdint.h>

#define LOW_BYTE(x) (x & 0xff)
#define HIGH_BYTE(x) ((x >> 8) & 0xff)

static const uint8_t AS5600_ADDRESS = 0x36;

// ----------------------------------------------------------------------------
// Register addresses

// Configuration registers
static const uint8_t ADDRESS_ZMCO          = 0x00;
static const uint8_t ADDRESS_ZPOS_U        = 0x01; // 0x02 is low byte
static const uint8_t ADDRESS_MPOS_U        = 0x03; // 0x04 is low byte
static const uint8_t ADDRESS_MANG_U        = 0x05; // 0x06 is low byte

static const uint8_t ADDRESS_CONF_U        = 0x07; // Low and high address provided separately,
static const uint8_t ADDRESS_CONF_L        = 0x08; // because they are not always accessed together.

// Output registers
static const uint8_t ADDRESS_RAW_ANGLE_U   = 0x0c; // 0x0d is low byte
static const uint8_t ADDRESS_ANGLE_U       = 0x0e; // 0x0f is low byte

// Status registers
static const uint8_t ADDRESS_MAGNET_STATUS = 0x0b;
static const uint8_t ADDRESS_AGC           = 0x1a;
static const uint8_t ADDRESS_MAGNITUDE_U   = 0x1b; // 0x1c is low byte

// Burn commands
static const uint8_t ADDRESS_BURN          = 0xff;

// ----------------------------------------------------------------------------
// Helper functions

uint8_t _read_byte(i2c_inst_t *i2c, uint8_t addr) {
    uint8_t r;
    i2c_write_blocking(i2c, AS5600_ADDRESS, &addr, 1, false);
    i2c_read_blocking(i2c, AS5600_ADDRESS, &r, 1, false);
    return r;
}

uint16_t _read_word(i2c_inst_t *i2c, uint8_t addr) {
    uint8_t bh = _read_byte(i2c, addr);
    uint8_t bl = _read_byte(i2c, addr + 1);
    return (bh << 8) | bl;
}

uint16_t _read_word_auto_inc(i2c_inst_t *i2c, uint8_t addr) {
    if (!(addr == ADDRESS_RAW_ANGLE_U || addr == ADDRESS_ANGLE_U || addr == ADDRESS_MAGNITUDE_U)) {
        return 0xffff;
    }

    i2c_write_blocking(i2c, AS5600_ADDRESS, &addr, 1, false);
    uint8_t d[2];
    i2c_read_blocking(i2c, AS5600_ADDRESS, d, 2, false);
    return (d[0] << 8) | d[1];
}

void _write_byte(i2c_inst_t *i2c, uint8_t addr, uint8_t data) {
    uint8_t d[2] = {addr, data};
    i2c_write_blocking(i2c, AS5600_ADDRESS, d, 2, false);
}

void _write_word(i2c_inst_t *i2c, uint8_t addr, uint16_t data) {
    _write_byte(i2c, addr, HIGH_BYTE(data));
    sleep_ms(2);
    _write_byte(i2c, addr + 1, LOW_BYTE(data));
    sleep_ms(2);
}

bool as5600_connected(i2c_inst_t *i2c) {
    uint8_t dummy;
    return !(i2c_read_blocking(i2c, AS5600_ADDRESS, &dummy, 1, false) < 0);
}

// ----------------------------------------------------------------------------
// Get/set angles

uint16_t as5600_set_max_angle(i2c_inst_t *i2c, uint16_t angle) {
    if (angle == 0xffff) {
        angle = as5600_get_raw_angle(i2c);
    }

    _write_word(i2c, ADDRESS_MANG_U, angle);

    return as5600_get_max_angle(i2c);
}

uint16_t as5600_get_max_angle(i2c_inst_t *i2c) {
    return _read_word(i2c, ADDRESS_MANG_U);
}

uint16_t as5600_set_start_position(i2c_inst_t *i2c, uint16_t angle) {
    if (angle == 0xffff) {
        angle = as5600_get_raw_angle(i2c);
    }

    _write_word(i2c, ADDRESS_ZPOS_U, angle);

    return as5600_get_start_position(i2c);
}

uint16_t as5600_get_start_position(i2c_inst_t *i2c) {
    return _read_word(i2c, ADDRESS_ZPOS_U);
}

uint16_t as5600_set_end_position(i2c_inst_t *i2c, uint16_t angle) {
    if (angle == 0xffff) {
        angle = as5600_get_raw_angle(i2c);
    }

    _write_word(i2c, ADDRESS_MPOS_U, angle);

    return as5600_get_end_position(i2c);
}

uint16_t as5600_get_end_position(i2c_inst_t *i2c) {
    return _read_word(i2c, ADDRESS_MPOS_U);
}

// ----------------------------------------------------------------------------
// Measurements

uint16_t as5600_get_raw_angle(i2c_inst_t *i2c) {
    return _read_word_auto_inc(i2c, ADDRESS_RAW_ANGLE_U);
}

uint16_t as5600_get_scaled_angle(i2c_inst_t *i2c) {
    return _read_word_auto_inc(i2c, ADDRESS_ANGLE_U);
}

// ----------------------------------------------------------------------------
// Magnet detection

bool as5600_detect_magnet(i2c_inst_t *i2c) {
    return as5600_get_magnet_strength(i2c) == MAGNET_OK;
}

enum as5600_magnet_strength as5600_get_magnet_strength(i2c_inst_t *i2c) {
    enum as5600_magnet_strength r = MAGNET_MISSING;
    uint8_t status = _read_byte(i2c, ADDRESS_MAGNET_STATUS);
    if (status & 0x08) {
        r = MAGNET_TOO_STRONG;
    } else if (status & 0x10) {
        r = MAGNET_WEAK;
    } else if (status & 0x20) {
        r = MAGNET_OK;
    }
    return r;
}

int as5600_get_agc(i2c_inst_t *i2c) {
    return _read_byte(i2c, ADDRESS_AGC);
}

uint16_t as5600_get_magnitude(i2c_inst_t *i2c) {
    return _read_word_auto_inc(i2c, ADDRESS_MAGNITUDE_U);
}

// ----------------------------------------------------------------------------
// Configuration

//TODO: Should provide functions to extract values from an uint16_t value. This
//      would allow getting multiple values with one CONF read.

uint16_t as5600_get_conf(i2c_inst_t *i2c) {
    return _read_word(i2c, ADDRESS_CONF_U);
}

void as5600_set_conf(i2c_inst_t *i2c, uint16_t conf) {
    _write_word(i2c, ADDRESS_CONF_U, conf);
}

enum as5600_power_mode as5600_conf_get_power_mode(i2c_inst_t *i2c) {
    uint8_t conf_l = _read_byte(i2c, ADDRESS_CONF_L);
    return conf_l & 0b11;
}

void as5600_conf_set_power_mode(i2c_inst_t *i2c, enum as5600_power_mode val) {
    uint8_t conf_l = _read_byte(i2c, ADDRESS_CONF_L);
    conf_l &= 0b11111100;
    conf_l |= val;
    _write_byte(i2c, ADDRESS_CONF_L, conf_l);
}

enum as5600_hysteresis as5600_conf_get_hysteresis(i2c_inst_t *i2c) {
    uint8_t conf_l = _read_byte(i2c, ADDRESS_CONF_L);
    return (conf_l >> 2) & 0b11;
}

void as5600_conf_set_hysteresis(i2c_inst_t *i2c, enum as5600_hysteresis val) {
    uint8_t conf_l = _read_byte(i2c, ADDRESS_CONF_L);
    conf_l &= 0b11110011;
    conf_l |= (val << 2);
    _write_byte(i2c, ADDRESS_CONF_L, conf_l);
}

enum as5600_output as5600_conf_get_output(i2c_inst_t *i2c) {
    uint8_t conf_l = _read_byte(i2c, ADDRESS_CONF_L);
    return (conf_l >> 4) & 0b11;
}

void as5600_conf_set_output(i2c_inst_t *i2c, enum as5600_output val) {
    uint8_t conf_l = _read_byte(i2c, ADDRESS_CONF_L);
    conf_l &= 0b11001111;
    conf_l |= (val << 4);
    _write_byte(i2c, ADDRESS_CONF_L, conf_l);
}

enum as5600_pwm_frequency as5600_conf_get_pwm_frequency(i2c_inst_t *i2c) {
    uint8_t conf_l = _read_byte(i2c, ADDRESS_CONF_L);
    return (conf_l >> 6) & 0b11;
}

void as5600_conf_set_pwm_frequency(i2c_inst_t *i2c, enum as5600_pwm_frequency val) {
    uint8_t conf_l = _read_byte(i2c, ADDRESS_CONF_L);
    conf_l &= 0b00111111;
    conf_l |= (val << 6);
    _write_byte(i2c, ADDRESS_CONF_L, conf_l);
}

enum as5600_slow_filter as5600_conf_get_slow_filter(i2c_inst_t *i2c) {
    uint8_t conf_u = _read_byte(i2c, ADDRESS_CONF_U);
    return conf_u & 0b11;
}

void as5600_conf_set_slow_filter(i2c_inst_t *i2c, enum as5600_slow_filter val) {
    uint8_t conf_u = _read_byte(i2c, ADDRESS_CONF_U);
    conf_u &= 0b11111100;
    conf_u |= val;
    _write_byte(i2c, ADDRESS_CONF_U, conf_u);
}

enum as5600_fast_filter_threshold as5600_conf_get_fast_filter_threshold(i2c_inst_t *i2c)  {
    uint8_t conf_u = _read_byte(i2c, ADDRESS_CONF_U);
    return (conf_u >> 2) & 0b111;
}

void as5600_conf_set_fast_filter_threshold(i2c_inst_t *i2c, enum as5600_fast_filter_threshold val) {
    uint8_t conf_u = _read_byte(i2c, ADDRESS_CONF_U);
    conf_u &= 0b11100011;
    conf_u |= (val << 2);
    _write_byte(i2c, ADDRESS_CONF_U, conf_u);
}

bool as5600_conf_get_watchdog(i2c_inst_t *i2c)  {
    uint8_t conf_u = _read_byte(i2c, ADDRESS_CONF_U);
    return (conf_u >> 5) & 0b1;
}

void as5600_conf_set_watchdog(i2c_inst_t *i2c, bool enabled) {
    uint8_t conf_u = _read_byte(i2c, ADDRESS_CONF_U);
    conf_u &= 0b11011111;
    conf_u |= ((enabled ? 1 : 0) << 5);
    _write_byte(i2c, ADDRESS_CONF_U, conf_u);
}

// ----------------------------------------------------------------------------
// Permanent settings

uint8_t as5600_get_burn_count(i2c_inst_t *i2c) {
    return _read_byte(i2c, ADDRESS_ZMCO);
}

enum as5600_burn_result as5600_burn_angle(i2c_inst_t *i2c) {
    uint16_t zpos = as5600_get_start_position(i2c);
    uint16_t mpos = as5600_get_end_position(i2c);
    enum as5600_burn_result r;
    if (!as5600_detect_magnet(i2c)) {
        r = BURN_NO_MAGNET;
    } else if (as5600_get_burn_count(i2c) >= 3) {
        r = BURN_LIMIT;
    } else if (zpos == 0 || mpos == 0) {
        r = BURN_NO_ANGLES;
    } else {
        _write_byte(i2c, ADDRESS_BURN, 0x80);
        r = BURN_SUCCESS;
    }

    return r;
}

int as5600_burn_setting(i2c_inst_t *i2c) {
    uint16_t mang = as5600_get_max_angle(i2c);
    enum as5600_burn_result r;
    if (as5600_get_burn_count(i2c) > 0) {
        r = BURN_LIMIT;
    } else if (mang < 204) { /* 18 deg is minimum angle, and 204 = floor(18/360*4095) */
        r = BURN_ANGLE_LOW;
    } else {
        _write_byte(i2c, ADDRESS_BURN, 0x40);
        r = BURN_SUCCESS;
    }
    
    return r;
}
