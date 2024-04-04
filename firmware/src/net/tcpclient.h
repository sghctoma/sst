#ifndef _TCPCLIENT_H
#define _TCPCLIENT_H

#include "lwip/ip_addr.h"

struct connection {
    struct tcp_pcb *pcb;
    ip_addr_t remote_addr;
    uint32_t data_len;
    uint32_t sent_len;
    int8_t status;
};

bool send_file(const char *filename);

#endif /* _TCPCLIENT_H */
