#ifndef _HARDWARE_CONFIG_H
#define _HARDWARE_CONFIG_H

// ----------------------------------------------------------------------------
// PIO I2C (for DS3231 and default display)

#define I2C_PIO          pio0
#define I2C_SM           0
#define PIO_PIN_SDA      2
// SCL has to be PIO_PIN_SDA+1

// ----------------------------------------------------------------------------
// Battery

#define BATTERY_MIN_V    3.3f
#define BATTERY_MAX_V    4.2f
#define BATTERY_RANGE    (BATTERY_MAX_V - BATTERY_MIN_V)

// ----------------------------------------------------------------------------
// Buttons

#define BUTTON_LEFT      4
#define BUTTON_RIGHT     5

// ----------------------------------------------------------------------------
// Display

#define DISPLAY_WIDTH    128
#define DISPLAY_HEIGHT    64
#define DISPLAY_FLIPPED    1

#ifdef SPI_DISPLAY
#define DISPLAY_SPI      spi1
#define DISPLAY_PIN_MISO 12
#define DISPLAY_PIN_MOSI 11
#define DISPLAY_PIN_SCK  10
#define DISPLAY_PIN_CS   13
#define DISPLAY_PIN_RST  6
#else
#define DISPLAY_ADDRESS  0x3c
#endif // SPI_DISPLAY

// ----------------------------------------------------------------------------
// MicroSD card reader

#ifdef SPI_MICROSD
#define MICROSD_SPI      spi0
#define BAUD_RATE        (25 * 1000 * 1000)
#define MICROSD_PIN_MISO 16
#define MICROSD_PIN_MOSI 19
#define MICROSD_PIN_SCK  18
#define MICROSD_PIN_CS   17
#else
#define SD_SDIO_PIO      pio1
#define SD_SDIO_PIN_CMD  18
#define SD_SDIO_PIN_D0   19
// The other SDIO pins have to be:
//   CLK = SD_SDIO_PIN_D0 - 2
//   D1 = SD_SDIO_PIN_D0 + 1
//   D2 = SD_SDIO_PIN_D0 + 2
//   D3 = SD_SDIO_PIN_D0 + 3
#endif // SPI_MICROSD

// ----------------------------------------------------------------------------
// Fork and shock sensors

#define FORK_I2C         i2c0
#define FORK_PIN_SDA     8
#define FORK_PIN_SCL     9

#define SHOCK_I2C        i2c1
#define SHOCK_PIN_SDA    14
#define SHOCK_PIN_SCL    15

#endif // _HARDWARE_CONFIG_H