#ifndef TRAVEL_SENSOR_H
#define TRAVEL_SENSOR_H

#include <hardware/i2c.h>
#include <stdbool.h>
#include <stdint.h>

union port {
    i2c_inst_t *i2c;
    uint gpio;
};

struct i2c_comm {
    i2c_inst_t *instance;
    uint scl_gpio;
    uint sda_gpio;
};

struct adc_comm {
    uint adc_num;
    uint gpio;
};

union comm {
    struct i2c_comm i2c;
    struct adc_comm adc;
};

struct travel_sensor {
    union comm comm;
    volatile bool available;
    uint16_t baseline;
    bool inverted;
    void (*init)(struct travel_sensor *sensor);
    bool (*check_availability)(struct travel_sensor *sensor);
    bool (*start)(struct travel_sensor *sensor, uint16_t baseline, bool inverted);
    void (*calibrate_expanded)(struct travel_sensor *sensor);
    void (*calibrate_compressed)(struct travel_sensor *sensor);
    uint16_t (*measure)(struct travel_sensor *sensor);
};

#endif // TRAVEL_SENSOR_H
