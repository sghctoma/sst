#include "ntp.h"
#include "lwip/apps/sntp.h"
#include "pico/aon_timer.h"
#include "pico/time.h"

#include "../rtc/ds3231.h"
#include "../util/config.h"

extern struct ds3231 rtc;

static volatile uint64_t start_time_us = 0;
static volatile bool ntp_done = false;

time_t rtc_timestamp() {
    struct tm tm_now;
    if (!aon_timer_get_time_calendar(&tm_now)) {
        return 0;
    }

    // We want to store UTC values in record files, and we don't have timegm,
    // so we set UTC0 as timezone string here ...
    setenv("TZ", "UTC0", 1);
    tzset();

    time_t t = mktime(&tm_now);

    // ... and we restore the original one after we got the timestamp.
    setenv("TZ", config.timezone, 1);
    tzset();

    return t;
}

bool sync_rtc_to_ntp() {
    ntp_done = false;
    sntp_init();

    absolute_time_t timeout_time = make_timeout_time_ms(NTP_TIMEOUT_TIME);
    while (!ntp_done && absolute_time_diff_us(get_absolute_time(), timeout_time) > 0) { tight_loop_contents(); }

    sntp_stop();

    return ntp_done;
}

void setup_ntp(const char *server) {
    sntp_setoperatingmode(SNTP_OPMODE_POLL);
    sntp_setservername(0, server);
    if (aon_timer_is_running()) {
        start_time_us = rtc_timestamp() * 1000000;
    } else {
        start_time_us = 0;
    }
}

uint64_t get_system_time_us() {
    uint64_t t = start_time_us + time_us_64();
    return start_time_us + time_us_64();
}

void set_system_time_us(uint32_t sec, uint32_t us) {
    time_t epoch = sec;
    struct tm *tm_utc = gmtime(&epoch);

    aon_timer_set_time_calendar(tm_utc);
    ds3231_set_datetime(&rtc, tm_utc);
    start_time_us = (epoch * 1000000 + us) - time_us_64();
    ntp_done = true;
}
