#ifndef _CONFIG_H
#define _CONFIG_H

#include <stdbool.h>
#include <stdint.h>

struct config {
    char ssid[33];
    char psk[64];
    char ntp_server[264];
    char sst_server[264];
    uint16_t sst_server_port;
    uint32_t country;
};

extern struct config config;

bool load_config();

#endif // _CONFIG_H