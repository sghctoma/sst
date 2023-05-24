#ifndef _NTP_H
#define _NTP_H

#include "pico/stdlib.h"

#define NTP_TIMEOUT_TIME 2000

uint64_t get_system_time_us();
void init_ntp(const char* server);
bool sync_rtc_to_ntp();

#endif /* _NTP_H */
