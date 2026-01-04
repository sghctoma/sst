#ifndef NMEA_UTIL_H
#define NMEA_UTIL_H

#include "gps_sensor.h"
#include <stddef.h>
#include <stdint.h>

uint8_t nmea_checksum(const char *data, size_t len);
bool nmea_send_command(struct gps_sensor *gps, const char *cmd);

#endif
