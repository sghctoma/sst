#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "hardware/timer.h"
#include "hardware/i2c.h"
#include "bsp/board.h"
#include "tusb.h"
#include "ssd1306.h"
#include "as5600.h"

#include "ff.h"
#include "hw_config.h"
#include <stdint.h>

// ----------------------------------------------------------------------------
// Data acquisition

static bool have_fork;
static bool have_shock;

struct record {
    uint32_t micros;
    uint16_t fork_angle;
    uint16_t shock_angle;
};

// We are using two buffers. Data acquisition happens on core #1 into the active
// buffer (referred to by the pointer active_buffer) and we dump to Micro SD card
// on core #2.
//
// When the active buffer is filled on core #1,
//  - the buffer's pointer is sent to core #2 via the Pico's multicore FIFO
//  - the other buffer's address is read from the FIFO, and set as active buffer.
//  
// Core #2 waits until an address is sent from core #1, and
//  - dumps the content at that address to the card
//  - sends the buffer address to core #1 via FIFO 
// 

#define BUFFER_SIZE 2048 // Not declared as a static const, because variable
                         // length arrays are not a thing in C.

struct record databuffer1[BUFFER_SIZE];
struct record databuffer2[BUFFER_SIZE];
struct record *active_buffer = databuffer1;
uint16_t count = 0;

bool data_acquisition_cb(repeating_timer_t *rt) {
    if (++count == BUFFER_SIZE) {
        count = 0;
        multicore_fifo_push_blocking((uintptr_t)active_buffer);
        active_buffer = (struct record *)((uintptr_t)multicore_fifo_pop_blocking());
    }

    active_buffer[count].micros = time_us_32();
    if (have_fork) {
        active_buffer[count].fork_angle = as5600_get_scaled_angle(i2c0);
    } else {
        active_buffer[count].fork_angle = 0xffff;
    }

    if (have_shock) {
        active_buffer[count].shock_angle = as5600_get_scaled_angle(i2c1);
    } else {
        active_buffer[count].shock_angle = 0xffff;
    }

    return true; // keep repeating
}

// ----------------------------------------------------------------------------
// Data storage

int open_datafile(FIL *file) {
    sd_card_t *sd = sd_get_by_num(0);
    FRESULT fr = f_mount(&sd->fatfs, sd->pcName, 1);
    if (fr != FR_OK) {
        return PICO_ERROR_GENERIC;
    }

    uint16_t index = 0;
    FIL index_fil;
    fr = f_open(&index_fil, "INDEX", FA_OPEN_EXISTING | FA_READ);
    if (fr == FR_OK || fr == FR_EXIST) {
        uint8_t buf[2];
        uint br;
        f_read(&index_fil, buf, 2, &br);
        if (br == 2) {
            index = ((buf[0] << 8) | buf[1]) + 1;
        }
    }
    f_close(&index_fil);

    fr = f_open(&index_fil, "INDEX", FA_OPEN_ALWAYS | FA_WRITE);
    if (fr == FR_OK) {
        f_lseek(&index_fil, 0);
        uint8_t buf[2] = {
            (index >> 8) & 0xff,
            index & 0xff
        };
        uint bw;
        f_write(&index_fil, buf, 2, &bw);
        f_close(&index_fil);
    } else {
        return PICO_ERROR_GENERIC;
    }

    char filename[10];
    sprintf(filename, "%05u.SST", index);
    fr = f_open(file, filename, FA_CREATE_NEW | FA_WRITE);
    if (fr != FR_OK) {
        return fr;
    }

    return index;
}

void data_storage_core1() {
    FIL file;
    int index = open_datafile(&file);
    multicore_fifo_push_blocking(index);
    multicore_fifo_push_blocking((uintptr_t)databuffer2);

    struct record *buffer;
    struct record b[BUFFER_SIZE];
    while (1) {
        buffer = (struct record *)((uintptr_t)multicore_fifo_pop_blocking());

        //TODO: Need this memcpy, otherwise write is not happening. Reason?
        //     Also, is this still better performance-wise, than running data
        //     acquisition and storage on the same core?
        memcpy(b, buffer, sizeof(struct record)*BUFFER_SIZE);
        multicore_fifo_push_blocking((uintptr_t)buffer);
        f_write(&file, b, sizeof(struct record)*BUFFER_SIZE, NULL);
        f_sync(&file);
    }
}

// ----------------------------------------------------------------------------
// Setup functions

void setup_i2c() {
    i2c_init(i2c0, 1000000);
    gpio_set_function(20, GPIO_FUNC_I2C);
    gpio_set_function(21, GPIO_FUNC_I2C);
    gpio_pull_up(20);
    gpio_pull_up(21);

    i2c_init(i2c1, 1000000);
    gpio_set_function(26, GPIO_FUNC_I2C);
    gpio_set_function(27, GPIO_FUNC_I2C);
    gpio_pull_up(26);
    gpio_pull_up(27);
}

bool setup_baseline(i2c_inst_t *i2c) {
    if (as5600_connected(i2c) && as5600_detect_magnet(i2c)) {
        uint16_t baseline = 0;
        for (int i = 0; i < 10; ++i) {
            baseline += as5600_get_raw_angle(i2c);
            sleep_ms(100);
        }
        baseline /= 10;
        as5600_set_start_position(i2c, baseline);
        as5600_set_max_angle(i2c, 2048);
        return true;
    } else {
        return false;
    }
}

void setup_sensors(ssd1306_t *disp) {
    ssd1306_draw_string(disp, 8, 8, 2, "NO MAGNET");
    ssd1306_show(disp);

    uint8_t dummy;
    while (!((as5600_connected(i2c0) && as5600_detect_magnet(i2c0)) ||
            (as5600_connected(i2c1) && as5600_detect_magnet(i2c1)))) {
        sleep_ms(500);
    }

    ssd1306_clear(disp);

    have_fork = setup_baseline(i2c0);
    have_shock = setup_baseline(i2c1);

    if (have_fork) {
        ssd1306_draw_string(disp, 0, 0, 2, "FORK  OK");
    } else {
        ssd1306_draw_string(disp, 0, 0, 2, "FORK  NO");
    }

    if (have_shock) {
        ssd1306_draw_string(disp, 0, 16, 2, "SHOCK OK");
    } else {
        ssd1306_draw_string(disp, 0, 16, 2, "SHOCK NO");
    }

    ssd1306_show(disp);
}

// ----------------------------------------------------------------------------
// Entry point 

int main() {
    setup_i2c();
    ssd1306_t disp;
    disp.external_vcc = false;
    ssd1306_init(&disp, 128, 32, 0x3C, i2c1);
    ssd1306_clear(&disp);
    ssd1306_show(&disp);

    board_init();
    tusb_init();

    // Wait for a maximum of 1 second for USB MSC to initialize
    uint32_t t = time_us_32();
    while (!tud_ready() && (time_us_32() - t) < 1000000) {
        tud_task();
    }

    if (tud_ready()) {
        ssd1306_draw_string(&disp, 8, 8, 2, "MSC MODE");
        ssd1306_show(&disp);

        while(1) {
            tud_task();
        }
    } else {
        // Setup AS5600 encoder(s)
        setup_sensors(&disp);

        // Start data storage on 2nd core
        multicore_launch_core1(&data_storage_core1);
        int index;
        index = (int)multicore_fifo_pop_blocking();
        if (index < 0) {
            char s[10];
            sprintf(s, "0x%x", index);
            ssd1306_clear(&disp);
            ssd1306_draw_string(&disp, 8, 8, 2, s);
            ssd1306_show(&disp);
            while(1) {
                tight_loop_contents();
            }
        }

        // Start collection timer
        repeating_timer_t data_acquisition_timer;
        if (!add_repeating_timer_us(-200, data_acquisition_cb, NULL, &data_acquisition_timer)) {
            ssd1306_clear(&disp);
            ssd1306_draw_string(&disp, 8, 8, 2, "TIMER ERR");
            ssd1306_show(&disp);
            while(1) {
                tight_loop_contents();
            }
        }

        while (1) {
            tight_loop_contents();
        }
    }

    return 0;
}
