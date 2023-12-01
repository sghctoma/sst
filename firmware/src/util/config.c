#include <stdint.h>

#include "pico/cyw43_arch.h"
#include "cyw43_country.h"
#include "pico/sleep.h"

#include "ff_stdio.h"
#include "config.h"

struct config config = {
    .ssid = "sst",
    .psk = "changemeplease",
    .ntp_server = "pool.ntp.org",
    .sst_server = "sst.sghctoma.com",
    .sst_server_port = 557,
    .country = CYW43_COUNTRY_HUNGARY,
    .timezone = "UTC0",
};

bool load_config() {
    FIL config_fil;
    uint8_t count = 0;
    FRESULT fr = f_open(&config_fil, "CONFIG", FA_OPEN_EXISTING | FA_READ);
    if (fr == FR_OK || fr == FR_EXIST) {
        char line[300];
        while (f_gets(line, 300, &config_fil) != NULL) {
            char *key = strtok(line, "=");
            char *value = strtok(NULL, "=");
            value[strcspn(value, "\r\n")] = 0;
            if (key == NULL || value == NULL) {
                continue;
            }
            if (strcmp(key, "SSID") == 0) {
                strncpy(config.ssid, value, 33);          
                ++count;
            } else if (strcmp(key, "PSK") == 0) {
                strncpy(config.psk, value, 64);
                ++count;
            } else if (strcmp(key, "NTP_SERVER") == 0) {
                strncpy(config.ntp_server, value, 264);
                ++count;
            } else if (strcmp(key, "SST_SERVER") == 0) {
                strncpy(config.sst_server, value, 264);
                ++count;
            } else if (strcmp(key, "SST_SERVER_PORT") == 0) {
                config.sst_server_port = atoi(value);
                ++count;
            } else if (strcmp(key, "COUNTRY") == 0) {
                config.country = CYW43_COUNTRY(key[0], key[1], 0);
                ++count;
            } else if (strcmp(key, "TIMEZONE") == 0) {
                strncpy(config.timezone, value, 100);
                ++count;
            }
        }
    }
    f_close(&config_fil);
  
    return count == 7;
}
