#ifndef _NTP_H
#define _NTP_H

#include <time.h>
#include "pico/cyw43_arch.h"

#define NTP_MSG_LEN 48
#define NTP_PORT 123
#define NTP_DELTA 2208988800 // seconds between 1 Jan 1900 and 1 Jan 1970
#define NTP_RESEND_TIME (1 * 1000)
#define NTP_TIMEOUT_TIME (5 * 1000)

struct ntp {
    ip_addr_t server_address;
    bool done;
    bool dns_request_sent;
    struct udp_pcb *pcb;
    absolute_time_t timeout_time;
    alarm_id_t resend_alarm;
};

bool sync_rtc_to_ntp();

#endif /* _NTP_H */
