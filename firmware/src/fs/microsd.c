/*
Copyright 2021 Carl John Kugler III
          2023 Tamás Szakály

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

#include <string.h>
#include "hw_config.h"
#include "ff.h"
#include "diskio.h"
#include "../fw/hardware_config.h"

static spi_t spis[] = {  // One for each SPI.
#ifdef SPI_MICROSD
    {
        .hw_inst = MICROSD_SPI,
        .miso_gpio = MICROSD_PIN_MISO,
        .mosi_gpio = MICROSD_PIN_MOSI,
        .sck_gpio = MICROSD_PIN_SCK,
        .set_drive_strength = true,
        .mosi_gpio_drive_strength = GPIO_DRIVE_STRENGTH_2MA,
        .sck_gpio_drive_strength = GPIO_DRIVE_STRENGTH_2MA,

        .baud_rate = BAUD_RATE,

        .DMA_IRQ_num = DMA_IRQ_1,
    }
#endif // SPI_MICROSD
};

static sd_card_t sd_cards[] = {
#ifdef SPI_MICROSD
    {
        .pcName = "0:",
        .type = SD_IF_SPI,
        .spi_if.spi = &spis[0],
        .spi_if.ss_gpio = MICROSD_PIN_CS,
        .spi_if.set_drive_strength = true,
        .spi_if.ss_gpio_drive_strength = GPIO_DRIVE_STRENGTH_2MA,
        .use_card_detect = false,
    }
#else
    {
        .pcName = "0:",
        .type = SD_IF_SDIO,
        .sdio_if = {
            .CMD_gpio = SD_SDIO_PIN_CMD,
            .D0_gpio = SD_SDIO_PIN_D0,
            .SDIO_PIO = SD_SDIO_PIO,
            .DMA_IRQ_num = DMA_IRQ_1
        },
        .use_card_detect = false,    
    }
#endif // SPI_MICROSD
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

