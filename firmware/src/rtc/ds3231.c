#include "ds3231.h"

static inline uint8_t from_bcd(uint8_t bcd) { return ((bcd / 16) * 10) + (bcd % 16); }

static inline uint8_t to_bcd(uint8_t val) { return ((val / 10) * 16) + (val % 10); }

void ds3231_init(struct ds3231 *d, PIO pio, uint sm, int (*i2c_write)(PIO, uint, uint8_t, const uint8_t *, uint),
                 int (*i2c_read)(PIO, uint, uint8_t, uint8_t *, uint)) {
    d->pio = pio;
    d->sm = sm;
    d->i2c_write = i2c_write, d->i2c_read = i2c_read;
}

void ds3231_get_datetime(struct ds3231 *d, struct tm *tm) {
    uint8_t dt_buf[7];
    uint8_t reg = 0;
    (*d->i2c_write)(d->pio, d->sm, 0x68, &reg, 1);
    (*d->i2c_read)(d->pio, d->sm, 0x68, dt_buf, sizeof(dt_buf));

    tm->tm_sec = from_bcd(dt_buf[0]);
    tm->tm_min = from_bcd(dt_buf[1]);
    tm->tm_hour = from_bcd(dt_buf[2]);
    tm->tm_wday = from_bcd(dt_buf[3]) - 1;
    tm->tm_mday = from_bcd(dt_buf[4]);
    tm->tm_mon = from_bcd(dt_buf[5] & 0x1F) - 1;
    tm->tm_year = from_bcd(dt_buf[6]) + 100;  // years since 1900
    tm->tm_isdst = -1;
    tm->tm_yday = 0;
}

void ds3231_set_datetime(struct ds3231 *d, const struct tm *tm) {
    uint8_t buf[8];
    buf[0] = 0; // register
    buf[1] = to_bcd(tm->tm_sec);
    buf[2] = to_bcd(tm->tm_min);
    buf[3] = to_bcd(tm->tm_hour);
    buf[4] = to_bcd(tm->tm_wday + 1);
    buf[5] = to_bcd(tm->tm_mday);
    buf[6] = to_bcd(tm->tm_mon + 1);
    buf[7] = to_bcd((tm->tm_year + 1900) - 2000);

    (*d->i2c_write)(d->pio, d->sm, 0x68, buf, sizeof(buf));
}
