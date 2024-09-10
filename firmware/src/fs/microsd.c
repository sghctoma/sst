/* hw_config.c
Copyright 2021 Carl John Kugler III
          2024 Tamás Szakály

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

See 
https://github.com/carlk3/no-OS-FatFS-SD-SDIO-SPI-RPi-Pico/tree/main#customizing-for-the-hardware-configuration
*/

#include <string.h>
#include "hw_config.h"
#include "../fw/hardware_config.h"

#ifdef SPI_MICROSD

/* Configuration of RP2040 hardware SPI object */
static spi_t spi = {
    .hw_inst = MICROSD_SPI,
    .sck_gpio = MICROSD_PIN_SCK,
    .mosi_gpio = MICROSD_PIN_MOSI,
    .miso_gpio = MICROSD_PIN_MISO,
    .set_drive_strength = true,
    .mosi_gpio_drive_strength = GPIO_DRIVE_STRENGTH_4MA,
    .sck_gpio_drive_strength = GPIO_DRIVE_STRENGTH_2MA,
    .no_miso_gpio_pull_up = true,
    .spi_mode = 3,
    .baud_rate = BAUD_RATE,
};

/* SPI Interface */
static sd_spi_if_t spi_if = {
    .spi = &spi,
    .ss_gpio = MICROSD_PIN_CS,
    .set_drive_strength = true,
    .ss_gpio_drive_strength = GPIO_DRIVE_STRENGTH_4MA,
};

/* Configuration of the SD Card socket object */
static sd_card_t sd_card = {
    .type = SD_IF_SPI,
    .spi_if_p = &spi_if,
    .use_card_detect = false,
};

#else

/* SDIO Interface */
static sd_sdio_if_t sdio_if = {
    .CMD_gpio = SD_SDIO_PIN_CMD,
    .D0_gpio = SD_SDIO_PIN_D0,
    .SDIO_PIO = SD_SDIO_PIO,
    .DMA_IRQ_num = DMA_IRQ_1,
};

/* Hardware Configuration of the SD Card socket "object" */
static sd_card_t sd_card = {
    .type = SD_IF_SDIO,
    .sdio_if_p = &sdio_if
};

#endif // SPI_MICROSD

size_t sd_get_num() { return 1; }

sd_card_t *sd_get_by_num(size_t num) {
    if (0 == num) {
        return &sd_card;
    } else {
        return NULL;
    }
}
