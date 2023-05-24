#ifndef _HARDWARE_CONFIG_H
#define _HARDWARE_CONFIG_H

#include <string.h>
#include "hw_config.h"
#include "ff.h"
#include "diskio.h"

#define MICROSD_SPI      spi0
#define MICROSD_PIN_MISO 16
#define MICROSD_PIN_MOSI 19
#define MICROSD_PIN_SCK  18
#define MICROSD_PIN_CS   17

#define DISPLAY_WIDTH    128
#define DISPLAY_HEIGHT    64

#define PIO_PIN_SDA  6
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
#define DISPLAY_FLIPPED  1

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

/* from hw_config.c
Copyright 2021 Carl John Kugler III

Licensed under the Apache License, Version 2.0 (the License); you may not use 
this file except in compliance with the License. You may obtain a copy of the 
License at

   http://www.apache.org/licenses/LICENSE-2.0 
Unless required by applicable law or agreed to in writing, software distributed 
under the License is distributed on an AS IS BASIS, WITHOUT WARRANTIES OR 
CONDITIONS OF ANY KIND, either express or implied. See the License for the 
specific language governing permissions and limitations under the License.
*/
/*

This file should be tailored to match the hardware design.

There should be one element of the spi[] array for each hardware SPI used.

There should be one element of the sd_cards[] array for each SD card slot.
The name is should correspond to the FatFs "logical drive" identifier.
(See http://elm-chan.org/fsw/ff/doc/filename.html#vol)
The rest of the constants will depend on the type of
socket, which SPI it is driven by, and how it is wired.

*/

static spi_t spis[] = {  // One for each SPI.
    {
        .hw_inst = MICROSD_SPI,
        .miso_gpio = MICROSD_PIN_MISO,
        .mosi_gpio = MICROSD_PIN_MOSI,
        .sck_gpio = MICROSD_PIN_SCK,
        .set_drive_strength = true,
        .mosi_gpio_drive_strength = GPIO_DRIVE_STRENGTH_2MA,
        .sck_gpio_drive_strength = GPIO_DRIVE_STRENGTH_2MA,

        .baud_rate = 25 * 1000 * 1000, // Actual frequency: 20833333.

        .DMA_IRQ_num = DMA_IRQ_1,
    }
};

static sd_card_t sd_cards[] = {
    {
        .pcName = "0:",
        .type = SD_IF_SPI,
        .spi_if.spi = &spis[0],
        .spi_if.ss_gpio = MICROSD_PIN_CS,
        .spi_if.set_drive_strength = true,
        .spi_if.ss_gpio_drive_strength = GPIO_DRIVE_STRENGTH_2MA,
        .use_card_detect = false,
    }
};

size_t sd_get_num() { return count_of(sd_cards); }
sd_card_t *sd_get_by_num(size_t num) {
    if (num <= sd_get_num()) {
        return &sd_cards[num];
    } else {
        return NULL;
    }
}
size_t spi_get_num() { return count_of(spis); }
spi_t *spi_get_by_num(size_t num) {
    if (num <= spi_get_num()) {
        return &spis[num];
    } else {
        return NULL;
    }
}

#endif // _HARDWARE_CONFIG_H