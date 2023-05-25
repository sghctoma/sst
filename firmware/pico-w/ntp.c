#include "ntp.h"
#include "lwip/apps/sntp.h"
#include "pico/time.h"
#include "hardware/rtc.h"
#include "include/ds3231.h"

extern struct ds3231 rtc;

static volatile uint64_t start_time_us = 0;
static volatile bool ntp_done = false;

time_t rtc_timestamp() {
    datetime_t rtc;
    rtc_get_datetime(&rtc);

    struct tm utc = {
        .tm_year = rtc.year - 1900,
        .tm_mon = rtc.month - 1,
        .tm_mday = rtc.day,
        .tm_hour = rtc.hour,
        .tm_min = rtc.min,
        .tm_sec = rtc.sec,
        .tm_isdst = -1,
        .tm_wday = 0,
        .tm_yday = 0,
    };

    time_t t = mktime(&utc);

    return t;
}

bool sync_rtc_to_ntp() {
    ntp_done = false;
    sntp_init();

    absolute_time_t timeout_time = make_timeout_time_ms(NTP_TIMEOUT_TIME);
    while (!ntp_done && absolute_time_diff_us(get_absolute_time(), timeout_time) > 0) {
        tight_loop_contents();
    }

    sntp_stop();

    return ntp_done;
}

void setup_ntp(const char* server) {
    sntp_setoperatingmode(SNTP_OPMODE_POLL);
    sntp_setservername(0, server);
    start_time_us = rtc_timestamp() * 1000000;
}

uint64_t get_system_time_us() {
    uint64_t t = start_time_us + time_us_64();
    return start_time_us + time_us_64();
}

void set_system_time_us(uint32_t sec, uint32_t us) {
    time_t epoch = sec;
    struct tm *time = gmtime(&epoch);
    datetime_t dt = {
        .year  = time->tm_year + 1900,
        .month = time->tm_mon + 1,
        .day   = time->tm_mday,
        .dotw  = 0,
        .hour  = time->tm_hour,
        .min   = time->tm_min,
        .sec   = time->tm_sec,
    };
    rtc_set_datetime(&dt);
    ds3231_set_datetime(&rtc, &dt);
    start_time_us = (mktime(time) * 1000000 + us) - time_us_64();
    ntp_done = true;
}
