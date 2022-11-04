/**
 * Copyright (c) 2022 Raspberry Pi (Trading) Ltd.
 *               2022 sghctoma
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include "pico/stdlib.h"
#include "pico/time.h"

#include "lwip/dns.h"
#include "lwip/pbuf.h"
#include "lwip/udp.h"

#include "ntp.h"

// Called with results of operation
static void ntp_result(struct ntp *ntp, int status, time_t *result) {
    if (status == 0 && result) {
        struct tm *utc = gmtime(result);
        ntp->success_cb(utc);
    }

    if (ntp->resend_alarm > 0) {
        cancel_alarm(ntp->resend_alarm);
        ntp->resend_alarm = 0;
    }

    ntp->dns_request_sent = false;
}

// Make an NTP request
static void ntp_request(struct ntp *ntp) {
    cyw43_arch_lwip_begin();
    struct pbuf *p = pbuf_alloc(PBUF_TRANSPORT, NTP_MSG_LEN, PBUF_RAM);
    uint8_t *req = (uint8_t *) p->payload;
    memset(req, 0, NTP_MSG_LEN);
    req[0] = 0x1b;
    udp_sendto(ntp->pcb, p, &ntp->server_address, NTP_PORT);
    pbuf_free(p);
    cyw43_arch_lwip_end();
}

static int64_t ntp_failed_handler(alarm_id_t id, void *user_data)
{
    struct ntp *ntp = (struct ntp *)user_data;
    ntp_result(ntp, -1, NULL);
    return 0;
}

// Call back with a DNS result
static void ntp_dns_found(const char *hostname, const ip_addr_t *ipaddr, void *arg) {
    struct ntp *ntp = (struct ntp *)arg;
    if (ipaddr) {
        ntp->server_address = *ipaddr;
        ntp_request(ntp);
    } else {
        ntp_result(ntp, -1, NULL);
    }
}

// NTP data received
static void ntp_recv(void *arg, struct udp_pcb *pcb, struct pbuf *p, const ip_addr_t *addr, u16_t port) {
    struct ntp *ntp = (struct ntp *)arg;
    uint8_t mode = pbuf_get_at(p, 0) & 0x7;
    uint8_t stratum = pbuf_get_at(p, 1);

    // Check the result
    if (ip_addr_cmp(addr, &ntp->server_address) && port == NTP_PORT && p->tot_len == NTP_MSG_LEN && mode == 0x4 && stratum != 0) {
        uint8_t seconds_buf[4] = {0};
        pbuf_copy_partial(p, seconds_buf, sizeof(seconds_buf), 40);
        uint32_t seconds_since_1900 = seconds_buf[0] << 24 | seconds_buf[1] << 16 | seconds_buf[2] << 8 | seconds_buf[3];
        uint32_t seconds_since_1970 = seconds_since_1900 - NTP_DELTA;
        time_t epoch = seconds_since_1970;
        ntp_result(ntp, 0, &epoch);
    } else {
        ntp_result(ntp, -1, NULL);
    }
    pbuf_free(p);
}

// Perform initialisation
struct ntp * ntp_init(void (*success_cb)(struct tm *), void(*timeout_cb)()) {
    if (success_cb == NULL || timeout_cb == NULL) {
        return NULL;
    }
    struct ntp *ntp = calloc(1, sizeof(struct ntp));
    if (ntp == NULL) {
        return NULL;
    }

    ntp->dns_request_sent = false;
    ntp->timeout_time = make_timeout_time_ms(NTP_TIMEOUT_TIME);
    ntp->timeout_cb = timeout_cb;
    ntp->success_cb = success_cb;

    ntp->pcb = udp_new_ip_type(IPADDR_TYPE_ANY);
    if (ntp->pcb == NULL) {
        free(ntp);
        return NULL;
    }
    udp_recv(ntp->pcb, ntp_recv, ntp);
    return ntp;
}

void ntp_task(struct ntp *ntp) {
    if (absolute_time_diff_us(get_absolute_time(), ntp->timeout_time) < 0) {
        ntp->dns_request_sent = false;
        ntp->timeout_cb();
        return;
    }

    if (!ntp->dns_request_sent) {
        ntp->resend_alarm = add_alarm_in_ms(NTP_RESEND_TIME, ntp_failed_handler, ntp, true);

        cyw43_arch_lwip_begin();
        int err = dns_gethostbyname(NTP_SERVER, &ntp->server_address, ntp_dns_found, ntp);
        cyw43_arch_lwip_end();

        ntp->dns_request_sent = true;
        if (err == ERR_OK) {
            ntp_request(ntp);
        } else if (err != ERR_INPROGRESS) { // ERR_INPROGRESS means expect a callback
            ntp_result(ntp, -1, NULL);
        }
    }
}
