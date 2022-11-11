#include <stdint.h>
#include <stdio.h>

#include "device/usbd.h"
#include "include/ntp.h"
#include "pico/platform.h"
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/cyw43_arch.h"
#include "pico/sleep.h"
#include "pico/time.h"
#include "pico/types.h"
#include "pico/util/datetime.h"
#include "hardware/clocks.h"
#include "hardware/rtc.h"
#include "hardware/rosc.h"
#include "hardware/timer.h"
#include "hardware/i2c.h"
#include "hardware/spi.h"
#include "bsp/board.h"

// For scb_hw so we can enable deep sleep
#include "hardware/structs/scb.h"

#include "sst.h"
#include "list.h"

static volatile enum state state;
static ssd1306_t disp;
static repeating_timer_t data_acquisition_timer;
static FIL recording;

static const uint BTN_LEFT = 5;
static const uint BTN_RIGHT = 1;

// ----------------------------------------------------------------------------
// Helper functions

static void display_message(ssd1306_t *disp, char *message) {
    ssd1306_clear(disp);
    ssd1306_draw_string(disp, 0, 10, 2, message);
    ssd1306_show(disp);
}

static bool msc_present() {
    // WL_GPIO2 is VBUS sense. WL_GPIO2 low -> no USB cable -> no MSC.
    if (cyw43_arch_gpio_get(2)) {
        // Wait for a maximum of 1 second for USB MSC to initialize
        uint32_t t = time_us_32();
        while (!tud_ready()) {
            if (time_us_32() - t > 1000000) {
                return false;
            }
            tud_task();
        }
        return true;
    }

    return false;
}

static bool connect() {
    cyw43_arch_init();
    cyw43_arch_enable_sta_mode();
    return !cyw43_arch_wifi_connect_timeout_ms("sst", "c9Aw-deLd-g3HR-Rvff", CYW43_AUTH_WPA2_AES_PSK, 10000);
}

static time_t rtc_timestamp() {
    datetime_t rtc;
    rtc_get_datetime(&rtc);

    struct tm utc = {
        .tm_year = rtc.year - 1900,
        .tm_mon = rtc.month - 1,
        .tm_mday = rtc.day,
        .tm_hour = rtc.hour,
        .tm_min = rtc.min,
        .tm_sec = rtc.sec,
        .tm_isdst = -1,
        .tm_wday = 0,
        .tm_yday = 0,
    };

    time_t t = mktime(&utc);

    return t;
}

// ----------------------------------------------------------------------------
// Data acquisition

static const uint16_t SAMPLE_RATE = 1000;

static volatile bool have_fork;
static volatile bool have_shock;

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

static bool data_acquisition_cb(repeating_timer_t *rt) {
    if (count == BUFFER_SIZE) {
        count = 0;
        multicore_fifo_push_blocking(DUMP);
        multicore_fifo_push_blocking((uintptr_t)active_buffer);
        active_buffer = (struct record *)((uintptr_t)multicore_fifo_pop_blocking());
    }

    if (have_fork) {
        active_buffer[count].fork_angle = as5600_get_scaled_angle(i2c0);
        //XXX active_buffer[count].fork_angle = 0xcafe;
    } else {
        active_buffer[count].fork_angle = 0xffff;
    }

    if (have_shock) {
        active_buffer[count].shock_angle = as5600_get_scaled_angle(i2c1);
        //XXX active_buffer[count].shock_angle = 0xbabe;
    } else {
        active_buffer[count].shock_angle = 0xffff;
    }

    count += 1;

    return state == RECORD; // keep repeating if we are still recording
}

// ----------------------------------------------------------------------------
// Data storage

static int setup_storage() {
    sd_card_t *sd = sd_get_by_num(0);
    FRESULT fr = f_mount(&sd->fatfs, sd->pcName, 1);
    if (fr != FR_OK) {
        return PICO_ERROR_GENERIC;
    }

    fr = f_mkdir("uploaded");
    if (!(fr == FR_OK || fr == FR_EXIST)) {
        return PICO_ERROR_GENERIC;
    }

    return 0;
}

static int open_datafile() {
    uint16_t index = 0;
    FIL index_fil;
    FRESULT fr = f_open(&index_fil, "INDEX", FA_OPEN_EXISTING | FA_READ);
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
    fr = f_open(&recording, filename, FA_CREATE_NEW | FA_WRITE);
    if (fr != FR_OK) {
        return fr;
    }

    struct header h = {"SST", 3, SAMPLE_RATE, rtc_timestamp()};
    f_write(&recording, &h, sizeof(struct header), NULL);

    return index;
}

static void data_storage_core1() {
    int err = setup_storage();
    multicore_fifo_push_blocking(err);

    int index;
    enum command cmd;
    uint16_t size;
    struct record *buffer;
    while (true) {
        cmd = (enum command)multicore_fifo_pop_blocking();
        switch(cmd) {
            case OPEN:
                multicore_fifo_drain();
                index = open_datafile();
                multicore_fifo_push_blocking(index);
                multicore_fifo_push_blocking((uintptr_t)databuffer2);
                break;
            case DUMP:
                buffer = (struct record *)((uintptr_t)multicore_fifo_pop_blocking());
                multicore_fifo_push_blocking((uintptr_t)buffer);
                f_write(&recording, buffer, sizeof(struct record)*BUFFER_SIZE, NULL);
                f_sync(&recording);
                break;
            case FINISH:
                size = (uint16_t)multicore_fifo_pop_blocking();
                buffer = (struct record *)((uintptr_t)multicore_fifo_pop_blocking());
                f_write(&recording, buffer, sizeof(struct record)*size, NULL);
                f_sync(&recording);
                f_close(&recording);
                break;
        }
    }
}

// ----------------------------------------------------------------------------
// Setup functions

static void setup_i2c() {
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

static bool setup_baseline(i2c_inst_t *i2c) {
    if (as5600_connected(i2c) && as5600_detect_magnet(i2c)) {
        uint16_t baseline = as5600_get_raw_angle(i2c);
        as5600_set_start_position(i2c, baseline);

        // Power down tha DAC, we don't need it.
        as5600_conf_set_output(i2c, OUTPUT_PWM);
        // Helps with those 1-quanta-high rapid spikes.
        as5600_conf_set_hysteresis(i2c, HYSTERESIS_2_LSB);
        // 0.55 ms step response delay, 0.03 RMS output noise.
        as5600_conf_set_slow_filter(i2c, SLOW_FILTER_4x);
        // TODO: experiment with fast filter.
        as5600_conf_set_fast_filter_threshold(i2c, FAST_FILTER_THRESHOLD_6_LSB);
        return true;
    } else {
        return false;
    }
}

static void setup_sensors() {
    uint8_t dummy;
    while (!((as5600_connected(i2c0) && as5600_detect_magnet(i2c0)) ||
            (as5600_connected(i2c1) && as5600_detect_magnet(i2c1)))) {
        sleep_ms(500);
    }

    have_fork = setup_baseline(i2c0);
    have_shock = setup_baseline(i2c1);
}

static void setup_display(ssd1306_t *disp) {
    spi_init(spi1, 1000000);
    gpio_set_function(14, GPIO_FUNC_SPI); // SCK
    gpio_set_function(15, GPIO_FUNC_SPI); // MOSI

    disp->external_vcc = false;
    ssd1306_init(disp, 128, 32, spi1,
        13,  // CS
        12,  // DC
        11); // RST
            
    ssd1306_clear(disp);
    ssd1306_show(disp);
}

// ----------------------------------------------------------------------------
// State handlers

static void on_rec_start() {
    count = 0;
    active_buffer = databuffer1;
    multicore_fifo_drain();
    
    display_message(&disp, "INIT SENS");
    setup_sensors();

    state = RECORD;
    char msg[8];
    sprintf(msg, "REC:%s|%s", have_fork ? "F" : ".", have_shock ? "S" : ".");
    display_message(&disp, msg);

    multicore_fifo_push_blocking(OPEN);
    int index = (int)multicore_fifo_pop_blocking();
    if (index < 0) {
        display_message(&disp, "FILE ERR");
        while(true) { tight_loop_contents(); }
    }

    // Start data acquisition timer
    if (!add_repeating_timer_us(-1000000/SAMPLE_RATE, data_acquisition_cb, NULL, &data_acquisition_timer)) {
        display_message(&disp, "TIMER ERR");
        while(true) { tight_loop_contents(); }
    }
}

static void on_rec_stop() {
    state = IDLE;
    display_message(&disp, "IDLE");
    cancel_repeating_timer(&data_acquisition_timer);

    multicore_fifo_push_blocking(FINISH);
    multicore_fifo_push_blocking(count);
    multicore_fifo_push_blocking((uintptr_t)active_buffer);
}

static void on_sync_data() {
    display_message(&disp, "CONNECT");
    if (!connect()) {
        display_message(&disp, "CONN ERR");
        sleep_ms(1000);
    } else {
        display_message(&disp, "DAT SYNC");
        struct list *imported = list_create();
 
        // send all .SST files in the root directory via TCP
        FRESULT fr;
        DIR dj;
        FILINFO fno;
        uint all = 0;
        uint succ = 0;
        fr = f_findfirst(&dj, &fno, "", "?????.SST");
        while (fr == FR_OK && fno.fname[0]) {
            ++all;
            display_message(&disp, fno.fname);
            if (send_file(fno.fname)) {
                list_push(imported, fno.fname);
                ++succ;
            }
            sleep_ms(100);
            fr = f_findnext(&dj, &fno);
        }
        f_closedir(&dj);

        // move successfully imported files to "uploaded" directory
        struct node *n = imported->head;
        while (n != NULL) {
            TCHAR path_new[19];
            sprintf(path_new, "uploaded/%s", n->data);
            f_rename(n->data, path_new);
            n = n->next;
        }
        list_delete(imported);

        // display results
        char s[16], a[16];
        sprintf(s, "S: %u", succ);
        sprintf(a, "A: %u", all);
        ssd1306_clear(&disp);
        ssd1306_draw_string(&disp, 0,  0, 2, s);
        ssd1306_draw_string(&disp, 0, 16, 2, a);
        ssd1306_show(&disp);
        sleep_ms(3000);
    }
    cyw43_arch_deinit();
    state = IDLE;
}

// ----------------------------------------------------------------------------
// Button handlers

static void on_left_press(void *user_data) {
    switch(state) {
        case IDLE:
            state = REC_START;
            break;
        case RECORD:
            state = REC_STOP;
            break;
        default:
            break;
    }
}

static void on_left_longpress(void *user_data) {
    switch(state) {
        case IDLE:
            state = SYNC_DATA;
            break;
        default:
            break;
    }
}

static void on_right_press(void *user_data) {
    switch(state) {
        case IDLE:
            state = SLEEP;
            break;
        default:
            break;
    }
}

static void on_right_longpress(void *user_data) {
    switch(state) {
        case IDLE:
            state = SYNC_TIME;
            break;
        default:
            break;
    }
}

// ----------------------------------------------------------------------------
// Entry point 

int main() {
    setup_i2c();
    board_init();
    tusb_init();
    rtc_init();

    datetime_t t = {
        .year  = 2022,
        .month = 11,
        .day   = 03,
        .dotw  = 4,
        .hour  = 13,
        .min   = 37,
        .sec   = 00
    };
    rtc_set_datetime(&t);

    setup_display(&disp);

    gpio_init(5);
    gpio_pull_up(5);
    sleep_ms(10);
    if (!gpio_get(5) && msc_present()) {
        state = MSC;
        display_message(&disp, "MSC MODE");
    } else {
        create_button(BTN_LEFT, NULL, on_left_press, on_left_longpress);
        create_button(BTN_RIGHT, NULL, on_right_press, on_right_longpress);

        display_message(&disp, "INIT STOR");
        multicore_launch_core1(&data_storage_core1);
        int err = (int)multicore_fifo_pop_blocking();
        if (err < 0) {
            display_message(&disp, "CARD ERR");
            while(true) { tight_loop_contents(); }
        }
 
        state = IDLE;
    }

    uint32_t scb_orig = scb_hw->scr;
    uint32_t clock0_orig = clocks_hw->sleep_en0;
    uint32_t clock1_orig = clocks_hw->sleep_en1;
    uint32_t last_time_update = time_us_32();
    char time_str[9];
    while (true) {
        switch(state) {
            case MSC:
                tud_task();
                break;
            case IDLE:
                if (time_us_32() - last_time_update >= 1000000) {
                    last_time_update = time_us_32();
                    rtc_get_datetime(&t);
                    sprintf(time_str, "%02d:%02d:%02d", t.hour, t.min, t.sec);
                    display_message(&disp, time_str);
                }
                break;
            case SYNC_TIME:
                display_message(&disp, "NTP SYNC");
                if (!connect()) {
                    display_message(&disp, "CONN ERR");
                    sleep_ms(1000);
                } else if (!sync_rtc_to_ntp()) {
                    display_message(&disp, "NTP ERR");
                    sleep_ms(1000);
                }
                cyw43_arch_deinit();
                state = IDLE;
                break;
            case SYNC_DATA:
                on_sync_data();
                break;
            case SLEEP:
                sleep_run_from_xosc();
                display_message(&disp, "SLEEP.");

                clocks_hw->sleep_en0 = CLOCKS_SLEEP_EN0_CLK_RTC_RTC_BITS;
                clocks_hw->sleep_en1 = 0x0;
                display_message(&disp, "SLEEP..");

                scb_hw->scr = scb_orig | M0PLUS_SCR_SLEEPDEEP_BITS;
                display_message(&disp, "SLEEP...");

                disable_button(BTN_LEFT, false);
                disable_button(BTN_RIGHT, true);
                ssd1306_poweroff(&disp);
                state = WAKING;
                __wfi();
                break;
            case WAKING:
                rosc_write(&rosc_hw->ctrl, ROSC_CTRL_ENABLE_BITS);

                scb_hw->scr = scb_orig;
                clocks_hw->sleep_en0 = clock0_orig;
                clocks_hw->sleep_en1 = clock1_orig;
                clocks_init();

                ssd1306_poweron(&disp);
                enable_button(BTN_LEFT);
                enable_button(BTN_RIGHT);
                state = IDLE;
            case REC_START:
                on_rec_start();
                break;
            case REC_STOP:
                on_rec_stop();
                break;
            default:
                break;
        }
    }

    return 0;
}

