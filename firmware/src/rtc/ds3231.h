#ifndef _DS3231_H
#define _DS3231_H

#include <time.h>
#include "../pio_i2c/pio_i2c.h"

#ifdef __cplusplus
extern "C" {
#endif

struct ds3231 {
    PIO pio;
    uint sm;
    int (*i2c_write)(PIO, uint, uint8_t, const uint8_t *, uint);
    int (*i2c_read)(PIO, uint, uint8_t, uint8_t *, uint);
};

void ds3231_init(struct ds3231 *d, PIO pio, uint sm, int (*i2c_write)(PIO, uint, uint8_t, const uint8_t *, uint),
                 int (*i2c_read)(PIO, uint, uint8_t, uint8_t *, uint));

void ds3231_get_datetime(struct ds3231 *d, struct tm *tm);

void ds3231_set_datetime(struct ds3231 *d, const struct tm *tm);

#endif // _DS3231_H
