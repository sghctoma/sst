#ifndef _NTP_H
#define _NTP_H

#include <time.h>

#include "pico/stdlib.h"

#define NTP_TIMEOUT_TIME 2000

// Needs to be called when the Pico's RTC has a sensible value, so
// that get_system_time_us gives a sensible value even when time
// hasn't been synced yet.
void setup_ntp(const char* server);

time_t rtc_timestamp();
uint64_t get_system_time_us();
bool sync_rtc_to_ntp();

#endif /* _NTP_H */
