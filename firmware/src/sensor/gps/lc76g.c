#include "lc76g.h"
#include "../../fw/hardware_config.h"
#include "../../util/log.h"
#include "hardware/gpio.h"
#include "hardware/irq.h"
#include "lwgps/lwgps.h"
#include "nmea_util.h"
#include "pico/stdlib.h"
#include "pico/time.h"
#include <stdio.h>

static volatile bool s_rx_enabled = false;
static lwgps_t s_lwgps;
static struct gps_telemetry s_building;
static bool s_pvt_received = false;
static bool s_epe_received = false;

// The unit responds to all commands with an ack
// This fields are used to track the expected ack to the last command sent
typedef enum { ACK_NONE, ACK_PAIR, ACK_PQTM_CFGMSGRATE, ACK_PQTM_SAVEPAR } ack_type_t;
static ack_type_t s_expected_ack = ACK_NONE;
static uint16_t s_expected_pair_cmd = 0;
static int8_t s_ack_result = -1;

// UART helpers
static void gps_uart_irq_handler(void) {
    while (uart_is_readable(gps.comm.uart.instance)) {
        uint8_t byte = uart_getc(gps.comm.uart.instance);
        struct gps_rx_buffer *buf = &gps.comm.uart.rx_buffer;
        uint16_t next_head = (buf->head + 1) & (GPS_RX_BUFFER_SIZE - 1);
        if (next_head != buf->tail) {
            buf->data[buf->head] = byte;
            buf->head = next_head;
        }
    }
}

void lc76g_send_command(struct gps_sensor *gps, const uint8_t *data, size_t len) {
    uart_write_blocking(gps->comm.uart.instance, data, len);
}

void lc76g_rx_enable(struct gps_sensor *g) {
    g->comm.uart.rx_buffer.head = 0;
    g->comm.uart.rx_buffer.tail = 0;
    uart_set_irq_enables(g->comm.uart.instance, true, false);
    irq_set_enabled(GPS_IRQ, true);
    s_rx_enabled = true;
}

void lc76g_rx_disable(struct gps_sensor *g) {
    irq_set_enabled(GPS_IRQ, false);
    uart_set_irq_enables(g->comm.uart.instance, false, false);
    s_rx_enabled = false;
}

bool lc76g_rx_is_enabled(void) { return s_rx_enabled; }

// Send a command and wait for an expected ACK
static bool lc76g_send_cmd_wait(struct gps_sensor *g, const char *cmd, ack_type_t ack_type, uint16_t pair_cmd_id,
                                uint32_t timeout_ms) {
    s_expected_ack = ack_type;
    s_expected_pair_cmd = pair_cmd_id;
    s_ack_result = -1;

    if (!nmea_send_command(g, cmd)) {
        s_expected_ack = ACK_NONE;
        return false;
    }

    absolute_time_t deadline = make_timeout_time_ms(timeout_ms);
    while (s_expected_ack != ACK_NONE && !time_reached(deadline)) {
        lc76g_process(g);
        sleep_ms(1);
    }

    if (s_ack_result != 0) {
        LOG("GPS", "CMD '%s' result=%d\n", cmd, s_ack_result);
    }
    return (s_ack_result == 0);
}

// Act on received messages recognized by lwgps
static void lc76g_on_statement(lwgps_statement_t stat) {
    switch (stat) {
        case STAT_PAIR_ACK:
            if (s_expected_ack == ACK_PAIR && s_lwgps.pair_ack_cmd == s_expected_pair_cmd) {
                if (s_lwgps.pair_ack_result != 1) {
                    // 0 = success, 2/3/4/5 = failures (1 = still processing)
                    s_ack_result = s_lwgps.pair_ack_result;
                    s_expected_ack = ACK_NONE;
                }
            }
            break;
        case STAT_PQTM_CFGMSGRATE_ACK:
            if (s_expected_ack == ACK_PQTM_CFGMSGRATE) {
                s_ack_result = s_lwgps.pqtm_ack_ok ? 0 : (s_lwgps.pqtm_ack_error ? s_lwgps.pqtm_ack_error : 1);
                s_expected_ack = ACK_NONE;
            }
            break;
        case STAT_PQTM_SAVEPAR_ACK:
            if (s_expected_ack == ACK_PQTM_SAVEPAR) {
                s_ack_result = s_lwgps.pqtm_ack_ok ? 0 : (s_lwgps.pqtm_ack_error ? s_lwgps.pqtm_ack_error : 1);
                s_expected_ack = ACK_NONE;
            }
            break;
        case STAT_PQTM_PVT:
            s_building.date = s_lwgps.pqtm_date;
            s_building.time_ms = (uint32_t)s_lwgps.pqtm_hours * 3600000 + (uint32_t)s_lwgps.pqtm_minutes * 60000 +
                                 (uint32_t)s_lwgps.pqtm_seconds * 1000 + s_lwgps.pqtm_milliseconds;
            s_building.latitude = s_lwgps.pqtm_lat;
            s_building.longitude = s_lwgps.pqtm_lon;
            s_building.altitude = s_lwgps.pqtm_alt;
            s_building.speed = s_lwgps.pqtm_speed;
            s_building.heading = s_lwgps.pqtm_heading;
            s_building.fix_mode = (enum gps_fix_mode)s_lwgps.pqtm_fix_mode;
            s_building.quality = (enum gps_quality)s_lwgps.pqtm_quality;
            s_building.satellites = s_lwgps.pqtm_sats_in_use;
            s_building.hdop = s_lwgps.pqtm_dop_h;
            s_building.pdop = s_lwgps.pqtm_dop_p;
            s_building.last_update_ms = time_us_32() / 1000;
            s_pvt_received = true;
            break;
        case STAT_PQTM_EPE:
            s_building.epe_2d = s_lwgps.pqtm_epe_2d;
            s_building.epe_3d = s_lwgps.pqtm_epe_3d;
            s_epe_received = true;
            break;
        default:
            break;
    }

    // When PQMT PVT & EPE have been recognized, update fix quality and report fix to the main app on the callback
    if (s_pvt_received && s_epe_received) {
        gps_update_fix_tracker(&gps, &s_building);
        if (gps.on_fix) {
            gps.on_fix(&s_building);
        }
        s_pvt_received = false;
        s_epe_received = false;
        s_building.epe_2d = -1.0f;
        s_building.epe_3d = -1.0f;
    }
}

// Public API

// Setup communication with the unit
void lc76g_init(struct gps_sensor *g) {
    LOG("GPS", "Init: TX=%d RX=%d baud=%d\n", g->comm.uart.tx_gpio, g->comm.uart.rx_gpio, g->comm.uart.baudrate);

    gpio_set_function(g->comm.uart.tx_gpio, GPIO_FUNC_UART);
    gpio_set_function(g->comm.uart.rx_gpio, GPIO_FUNC_UART);

    uart_init(g->comm.uart.instance, g->comm.uart.baudrate);
    uart_set_fifo_enabled(g->comm.uart.instance, true);

    irq_set_exclusive_handler(GPS_IRQ, gps_uart_irq_handler);

    lwgps_init(&s_lwgps);

    s_building.epe_2d = -1.0f;
    s_building.epe_3d = -1.0f;

    lc76g_rx_enable(g);
    LOG("GPS", "UART initialized\n");

    sleep_ms(100);

    g->available = true;
}

// Setup the unit to the expected configuration on every start
bool lc76g_configure(struct gps_sensor *g, uint16_t fix_interval_ms, bool gps_en, bool glonass_en, bool galileo_en,
                     bool bds_en, bool qzss_en) {
    char cmd[64];

    LOG("GPS", "Configure: fix=%dms gps=%d glo=%d gal=%d bds=%d qzss=%d\n", fix_interval_ms, gps_en, glonass_en,
        galileo_en, bds_en, qzss_en);

    // 1. Set constellations (causes reboot)
    snprintf(cmd, sizeof(cmd), "PAIR066,%d,%d,%d,%d,%d,0", gps_en, glonass_en, galileo_en, bds_en, qzss_en);
    LOG("GPS", "Step 1: Set constellations\n");
    if (!lc76g_send_cmd_wait(g, cmd, ACK_PAIR, 66, 3000)) {
        LOG("GPS", "Step 1 FAILED\n");
        return false;
    }
    sleep_ms(1000); // Wait for reboot

    // 2. Set fix rate
    snprintf(cmd, sizeof(cmd), "PAIR050,%u", fix_interval_ms);
    LOG("GPS", "Step 2: Set fix rate\n");
    if (!lc76g_send_cmd_wait(g, cmd, ACK_PAIR, 50, 1000)) {
        LOG("GPS", "Step 2 FAILED\n");
        return false;
    }

    // 3. Disable standard NMEA output (GGA, GLL, GSA, GSV, RMC, VTG)
    LOG("GPS", "Step 3: Disable NMEA output\n");
    for (int i = 0; i <= 10; i++) {
        snprintf(cmd, sizeof(cmd), "PAIR062,%d,0", i);
        if (!lc76g_send_cmd_wait(g, cmd, ACK_PAIR, 62, 1000)) {
            LOG("GPS", "Step 3.%d FAILED\n", i);
            return false;
        }
    }

    // 4. Save PAIR config (>1Hz requires power cycle)
    LOG("GPS", "Step 4: Save PAIR config\n");
    if (!lc76g_send_cmd_wait(g, "PAIR382,1", ACK_PAIR, 382, 1000)) {
        LOG("GPS", "Step 4a FAILED (lock sleep)\n");
        return false;
    }
    if (!lc76g_send_cmd_wait(g, "PAIR003", ACK_PAIR, 3, 1000)) {
        LOG("GPS", "Step 4b FAILED (power off)\n");
        return false;
    }
    if (!lc76g_send_cmd_wait(g, "PAIR513", ACK_PAIR, 513, 1000)) {
        LOG("GPS", "Step 4c FAILED (save)\n");
        return false;
    }
    if (!lc76g_send_cmd_wait(g, "PAIR002", ACK_PAIR, 2, 1000)) {
        LOG("GPS", "Step 4d FAILED (power on)\n");
        return false;
    }

    // 4. Enable PQTM output
    LOG("GPS", "Step 5: Enable PQTM output\n");
    if (!lc76g_send_cmd_wait(g, "PQTMCFGMSGRATE,W,PQTMPVT,1,1", ACK_PQTM_CFGMSGRATE, 0, 1000)) {
        LOG("GPS", "Step 5a FAILED (PVT)\n");
        return false;
    }
    if (!lc76g_send_cmd_wait(g, "PQTMCFGMSGRATE,W,PQTMEPE,1,2", ACK_PQTM_CFGMSGRATE, 0, 1000)) {
        LOG("GPS", "Step 5b FAILED (EPE)\n");
        return false;
    }

    // 6. Save PQTM config
    LOG("GPS", "Step 6: Save PQTM config\n");
    if (!lc76g_send_cmd_wait(g, "PQTMSAVEPAR", ACK_PQTM_SAVEPAR, 0, 1000)) {
        LOG("GPS", "Step 6 FAILED\n");
        return false;
    }

    LOG("GPS", "Configuration complete\n");
    return true;
}

static char s_debug_line[256];
static uint16_t s_debug_pos = 0;

void lc76g_process(struct gps_sensor *g) {
    struct gps_rx_buffer *buf = &g->comm.uart.rx_buffer;
    uint8_t byte;

    while (buf->tail != buf->head) {
        byte = buf->data[buf->tail];
        buf->tail = (buf->tail + 1) & (GPS_RX_BUFFER_SIZE - 1);

        // Log complete NMEA sentences
        if (byte == '$') {
            // Start of new sentence - reset buffer (handles missed newlines)
            s_debug_pos = 0;
            s_debug_line[s_debug_pos++] = byte;
        } else if (byte == '\n') {
            s_debug_line[s_debug_pos] = '\0';
            LOG("GPS", "RX: %s\n", s_debug_line);
            s_debug_pos = 0;
        } else if (byte != '\r' && s_debug_pos < sizeof(s_debug_line) - 1) {
            s_debug_line[s_debug_pos++] = byte;
        }

        lwgps_process(&s_lwgps, &byte, 1, lc76g_on_statement);
    }
}

bool lc76g_hot_start(struct gps_sensor *g) {
    // return lc76g_send_cmd_wait(g, "PAIR004", ACK_PAIR, 4, 1000);
}

bool lc76g_cold_start(struct gps_sensor *g) {
    // return lc76g_send_cmd_wait(g, "PAIR006", ACK_PAIR, 6, 1000);
}

bool lc76g_power_on(struct gps_sensor *g) { return lc76g_send_cmd_wait(g, "PAIR002", ACK_PAIR, 2, 1000); }

bool lc76g_power_off(struct gps_sensor *g) { return lc76g_send_cmd_wait(g, "PAIR003", ACK_PAIR, 3, 1000); }
