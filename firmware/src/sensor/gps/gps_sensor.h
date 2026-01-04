#ifndef GPS_SENSOR_H
#define GPS_SENSOR_H

#include <hardware/i2c.h>
#include <hardware/spi.h>
#include <hardware/uart.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Sensor Types
enum gps_type {
    GPS_TYPE_LC76G,
    GPS_TYPE_GENERIC_NMEA,
};

// Communication Protocol Abstraction
enum gps_protocol {
    GPS_PROTOCOL_UART,
    GPS_PROTOCOL_I2C,
    GPS_PROTOCOL_SPI,
};

enum gps_fix_mode {
    GPS_FIX_NONE = 0,
    GPS_FIX_2D = 2,
    GPS_FIX_3D = 3,
};

enum gps_quality {
    GPS_QUALITY_INVALID = 0,
    GPS_QUALITY_GPS_FIX = 1,
    GPS_QUALITY_DGPS = 2,
    GPS_QUALITY_ESTIMATED = 6,
};

struct gps_telemetry;
typedef void (*gps_fix_callback_t)(const struct gps_telemetry *telemetry);

#define GPS_RX_BUFFER_SIZE 1024

struct gps_rx_buffer {
    volatile uint8_t data[GPS_RX_BUFFER_SIZE];
    volatile uint16_t head;
    volatile uint16_t tail;
};

struct gps_uart_comm {
    uart_inst_t *instance;
    uint tx_gpio;
    uint rx_gpio;
    uint baudrate;
    struct gps_rx_buffer rx_buffer;
};

struct gps_i2c_comm {
    i2c_inst_t *instance;
    uint8_t address;
    uint sda_gpio;
    uint scl_gpio;
};

struct gps_spi_comm {
    spi_inst_t *instance;
    uint cs_gpio;
    uint sck_gpio;
    uint mosi_gpio;
    uint miso_gpio;
};

union gps_comm {
    struct gps_uart_comm uart;
    struct gps_i2c_comm i2c;
    struct gps_spi_comm spi;
};

// The regonised GPS telemetry
struct gps_telemetry {
    uint32_t date;
    uint32_t time_ms;

    double latitude;
    double longitude;
    float altitude;

    float speed;
    float heading;

    enum gps_fix_mode fix_mode;
    enum gps_quality quality;
    uint8_t satellites;
    float hdop;
    float pdop;

    float epe_2d;
    float epe_3d;

    uint32_t last_update_ms;
};

// Expect a certain number of samples to have reached a given accuracy and min number of visible satelites
// In order to consider the fix good & reliable
struct gps_fix_tracker {
    uint8_t consecutive_good;
    bool ready;
};

struct gps_sensor {
    enum gps_type type;
    enum gps_protocol protocol;
    union gps_comm comm;

    volatile bool available;
    struct gps_fix_tracker fix_tracker;
    gps_fix_callback_t on_fix; // Callback provided by consumer that is called when a fix is received

    void (*init)(struct gps_sensor *gps);
    bool (*configure)(struct gps_sensor *gps, uint16_t fix_interval_ms, bool gps_en, bool glonass_en, bool galileo_en,
                      bool bds_en, bool qzss_en);
    void (*process)(struct gps_sensor *gps);
    void (*send_command)(struct gps_sensor *gps, const uint8_t *data, size_t len);
    bool (*hot_start)(struct gps_sensor *gps);
    bool (*cold_start)(struct gps_sensor *gps);
    bool (*power_on)(struct gps_sensor *gps);
    bool (*power_off)(struct gps_sensor *gps);
};

bool gps_sensor_init(struct gps_sensor *gps);
bool gps_sensor_available(struct gps_sensor *gps);
bool gps_sensor_configure(struct gps_sensor *gps, uint16_t fix_interval_ms, bool gps_en, bool glonass_en,
                          bool galileo_en, bool bds_en, bool qzss_en);
void gps_sensor_process(struct gps_sensor *gps);
bool gps_sensor_fix_ready(struct gps_sensor *gps);
void gps_update_fix_tracker(struct gps_sensor *gps, const struct gps_telemetry *telemetry);
bool gps_sensor_hot_start(struct gps_sensor *gps);
bool gps_sensor_cold_start(struct gps_sensor *gps);
bool gps_sensor_power_on(struct gps_sensor *gps);
bool gps_sensor_power_off(struct gps_sensor *gps);

extern struct gps_sensor gps;

#endif // GPS_SENSOR_H
