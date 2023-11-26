#ifndef _TCPSERVER_H
#define _TCPSERVER_H

#include <string.h>
#include <stdlib.h>

#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"

#include "lwip/pbuf.h"
#include "lwip/tcp.h"

struct tcpserver {
    struct tcp_pcb *server_pcb;
    struct tcp_pcb *client_pcb;
    int status;
    int requested_file;
    int data_len;
    int sent_len;
    s8_t mdns_slot;
    bool mdns_initialized;
};

bool tcpserver_init(struct tcpserver *server);
void tcpserver_teardown(struct tcpserver *server);
bool tcpserver_process(struct tcpserver *server);
void tcpserver_finish(struct tcpserver *server);
bool tcpserver_finished(struct tcpserver *server);
bool tcpserver_requested(struct tcpserver *server);

#endif /* _TCPSERVER_H */
