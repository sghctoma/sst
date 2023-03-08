#ifndef _PIN_CONFIG_H
#define _PIN_CONFIG_H

#define MICROSD_SPI      spi0
#define MICROSD_PIN_MISO 16
#define MICROSD_PIN_MOSI 19
#define MICROSD_PIN_SCK  18
#define MICROSD_PIN_CS   17

#define DISPLAY_WIDTH    128
#define DISPLAY_HEIGHT    64

#define PIO_PIN_SDA  12
#define PIO_PIN_SCL  (PIO_PIN_SDA + 1)

#ifdef SPI_DISPLAY
#define DISPLAY_SPI      spi1
#define DISPLAY_PIN_MISO 12
#define DISPLAY_PIN_MOSI 15
#define DISPLAY_PIN_SCK  14
#define DISPLAY_PIN_CS   13
#define DISPLAY_PIN_RST  11
#else
#define DISPLAY_ADDRESS  0x3c
#endif // SPI_DISPLAY

#define FORK_I2C         i2c0
#define FORK_PIN_SDA     8
#define FORK_PIN_SCL     9

#define SHOCK_I2C        i2c1
#define SHOCK_PIN_SDA    26
#define SHOCK_PIN_SCL    27

#define BUTTON_LEFT      5
#define BUTTON_RIGHT     1

#define BATTERY_MIN_V    3.3f
#define BATTERY_MAX_V    4.2f
#define BATTERY_RANGE    (BATTERY_MAX_V - BATTERY_MIN_V)

#endif // _PIN_CONFIG_H