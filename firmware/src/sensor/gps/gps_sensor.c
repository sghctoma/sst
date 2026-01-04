#include "gps_sensor.h"

bool gps_sensor_init(struct gps_sensor *gps) {
    if (gps->init) {
        gps->init(gps);
    }
    return gps->available;
}

bool gps_sensor_available(struct gps_sensor *gps) { return gps->available; }

bool gps_sensor_configure(struct gps_sensor *gps, uint16_t fix_interval_ms, bool gps_en, bool glonass_en,
                          bool galileo_en, bool bds_en, bool qzss_en) {
    if (gps->configure) {
        return gps->configure(gps, fix_interval_ms, gps_en, glonass_en, galileo_en, bds_en, qzss_en);
    }
    return false;
}

void gps_sensor_process(struct gps_sensor *gps) {
    if (gps->process) {
        gps->process(gps);
    }
}

bool gps_sensor_fix_ready(struct gps_sensor *gps) { return gps->fix_tracker.ready; }

#define GPS_FIX_READY_SAMPLES  10
#define GPS_FIX_MIN_SATELITES  6
#define GPS_FIX_EPE_THRESHOLD  6.0f
#define GPS_FIX_HDOP_THRESHOLD 5.0f

void gps_update_fix_tracker(struct gps_sensor *gps, const struct gps_telemetry *telemetry) {
    bool good = (telemetry->fix_mode == GPS_FIX_3D) && (telemetry->satellites >= 6);

    if (good) {
        if (telemetry->epe_3d >= 0.0f) {
            good = (telemetry->epe_3d <= GPS_FIX_EPE_THRESHOLD);
        } else {
            good = (telemetry->hdop <= GPS_FIX_HDOP_THRESHOLD);
        }
    }

    if (good) {
        if (gps->fix_tracker.consecutive_good < GPS_FIX_READY_SAMPLES) {
            gps->fix_tracker.consecutive_good++;
        }
    } else {
        if (gps->fix_tracker.consecutive_good >= 3) {
            gps->fix_tracker.consecutive_good -= 3; // Rollback good count, but do not fully reset
        } else {
            gps->fix_tracker.consecutive_good = 0;
        }
    }

    gps->fix_tracker.ready = (gps->fix_tracker.consecutive_good >= GPS_FIX_READY_SAMPLES);
}

bool gps_sensor_hot_start(struct gps_sensor *gps) {
    if (gps->hot_start) {
        return gps->hot_start(gps);
    }
    return false;
}

bool gps_sensor_cold_start(struct gps_sensor *gps) {
    if (gps->cold_start) {
        return gps->cold_start(gps);
    }
    return false;
}

bool gps_sensor_power_on(struct gps_sensor *gps) {
    if (gps->power_on) {
        return gps->power_on(gps);
    }
    return false;
}

bool gps_sensor_power_off(struct gps_sensor *gps) {
    if (gps->power_off) {
        return gps->power_off(gps);
    }
    return false;
}