#ifndef LC76G_H
#define LC76G_H

#include "gps_sensor.h"

void lc76g_send_command(struct gps_sensor *gps, const uint8_t *data, size_t len);

void lc76g_init(struct gps_sensor *gps);
bool lc76g_configure(struct gps_sensor *gps, uint16_t fix_interval_ms, bool gps_en, bool glonass_en, bool galileo_en,
                     bool bds_en, bool qzss_en);
void lc76g_process(struct gps_sensor *gps);
bool lc76g_hot_start(struct gps_sensor *gps);
bool lc76g_cold_start(struct gps_sensor *gps);
bool lc76g_power_on(struct gps_sensor *gps);
bool lc76g_power_off(struct gps_sensor *gps);

void lc76g_rx_enable(struct gps_sensor *gps);
void lc76g_rx_disable(struct gps_sensor *gps);
bool lc76g_rx_is_enabled(void);

#endif
