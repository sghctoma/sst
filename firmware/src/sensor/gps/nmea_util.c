#include "nmea_util.h"
#include "../../util/log.h"
#include <stdio.h>
#include <string.h>

uint8_t nmea_checksum(const char *data, size_t len) {
    uint8_t crc = 0;
    for (size_t i = 0; i < len; i++) { crc ^= (uint8_t)data[i]; }
    return crc;
}

bool nmea_send_command(struct gps_sensor *gps, const char *cmd) {
    char buf[128];
    size_t cmd_len = strlen(cmd);
    uint8_t crc = nmea_checksum(cmd, cmd_len);
    int len = snprintf(buf, sizeof(buf), "$%s*%02X\r\n", cmd, crc);
    if (len < 0 || len >= (int)sizeof(buf)) {
        LOG("GPS", "TX: buffer overflow\n");
        return false;
    }
    // LOG("GPS", "TX: $%s*%02X\n", cmd, crc);
    gps->send_command(gps, (const uint8_t *)buf, len);
    return true;
}
