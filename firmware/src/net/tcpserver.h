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
};

bool start_tcp_server();

#endif /* _TCPSERVER_H */
