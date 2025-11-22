#include "ds3231.h"

static inline uint8_t from_bcd(uint8_t bcd) { return ((bcd / 16) * 10) + (bcd % 16); }

static inline uint8_t to_bcd(uint8_t val) { return ((val / 10) * 16) + (val % 10); }

void ds3231_init(struct ds3231 *d, PIO pio, uint sm, int (*i2c_write)(PIO, uint, uint8_t, const uint8_t *, uint),
                 int (*i2c_read)(PIO, uint, uint8_t, uint8_t *, uint)) {
    d->pio = pio;
    d->sm = sm;
    d->i2c_write = i2c_write, d->i2c_read = i2c_read;
}

void ds3231_get_datetime(struct ds3231 *d, datetime_t *dt) {
    uint8_t dt_buf[7];
    uint8_t reg = 0;
    (*d->i2c_write)(d->pio, d->sm, 0x68, &reg, 1);
    (*d->i2c_read)(d->pio, d->sm, 0x68, dt_buf, sizeof(dt_buf));

    dt->sec = from_bcd(dt_buf[0]);
    dt->min = from_bcd(dt_buf[1]);
    dt->hour = from_bcd(dt_buf[2]);
    dt->dotw = from_bcd(dt_buf[3]) - 1;
    dt->day = from_bcd(dt_buf[4]);
    dt->month = from_bcd(dt_buf[5] & 0x1F);
    dt->year = from_bcd(dt_buf[6]) + 2000;
}

void ds3231_set_datetime(struct ds3231 *d, datetime_t *dt) {
    uint8_t buf[8];
    buf[0] = 0; // register
    buf[1] = to_bcd(dt->sec);
    buf[2] = to_bcd(dt->min);
    buf[3] = to_bcd(dt->hour);
    buf[4] = to_bcd(dt->dotw + 1);
    buf[5] = to_bcd(dt->day);
    buf[6] = to_bcd(dt->month);
    buf[7] = to_bcd(dt->year - 2000);

    (*d->i2c_write)(d->pio, d->sm, 0x68, buf, sizeof(buf));
}
