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

struct sensor {
    union comm comm;
    volatile bool available;
    uint16_t baseline;
    bool inverted;
    void (*init)(struct sensor *sensor);
    bool (*check_availability)(struct sensor *sensor);
    bool (*start)(struct sensor *sensor, uint16_t baseline, bool inverted);
    void (*calibrate_expanded)(struct sensor *sensor);
    void (*calibrate_compressed)(struct sensor *sensor);
    uint16_t (*measure)(struct sensor *sensor);
};
