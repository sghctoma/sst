#include <stdint.h>
#include <stdio.h>

#include "cyw43.h"
#include "cyw43_country.h"
#include "cyw43_ll.h"
#include "device/usbd.h"
#include "include/ds3231.h"
#include "include/ntp.h"
#include "lwip/dhcp.h"
#include "pico/platform.h"
#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/cyw43_arch.h"
#include "pico/sleep.h"
#include "pico/time.h"
#include "pico/types.h"
#include "pico/util/datetime.h"
#include "hardware/clocks.h"
#include "hardware/adc.h"
#include "hardware/rtc.h"
#include "hardware/rosc.h"
#include "hardware/timer.h"
#include "hardware/i2c.h"
#include "hardware/spi.h"
#include "hardware/watchdog.h"
#include "bsp/board.h"

// For scb_hw so we can enable deep sleep
#include "hardware/structs/scb.h"

#include "sst.h"
#include "list.h"
#include "config.h"
#include "pin_config.h"

static volatile enum state state;

static uint32_t scb_orig;
static uint32_t clock0_orig;
static uint32_t clock1_orig;

static ssd1306_t disp;
static struct ds3231 rtc;
static repeating_timer_t data_acquisition_timer;
static FIL recording;

// ----------------------------------------------------------------------------
// Helper functions

static void display_message(ssd1306_t *disp, char *message) {
    ssd1306_clear(disp);
    ssd1306_draw_string(disp, 0, 10, 2, message);
    ssd1306_show(disp);
}

static void soft_reset() {
      watchdog_enable(1, 1);
      while(1);
}

static bool on_battery() {
    cyw43_arch_init();
    bool ret = !cyw43_arch_gpio_get(2);
    cyw43_arch_deinit();
    return ret;
}

static float read_voltage() {
    cyw43_arch_init();
    sleep_ms(1); // NOTE ADC3 readings are way too high without this sleep.
    adc_gpio_init(29);   // GPIO29 measures VSYS/3
    adc_select_input(3); // GPIO29 is ADC #3
    uint32_t vsys = 0;
    for(int i = 0; i < 3; i++) {
        vsys += adc_read();
    }
    cyw43_thread_exit();
    const float conversion_factor = 3.3f / (1 << 12);
    float ret = vsys * conversion_factor;
    cyw43_arch_deinit();
    return ret;
}

static bool msc_present() {
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

static bool wifi_connect() {
    cyw43_arch_init_with_country(CYW43_COUNTRY_HUNGARY);
    cyw43_arch_enable_sta_mode();
    return cyw43_arch_wifi_connect_timeout_ms(config.ssid, config.psk, CYW43_AUTH_WPA2_AES_PSK, 20000) == 0;
}

static void wifi_disconnect() {
    cyw43_wifi_leave(&cyw43_state, CYW43_ITF_STA);
    sleep_ms(100);
    cyw43_arch_deinit();
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
        active_buffer[count].fork_angle = as5600_get_scaled_angle(FORK_I2C);
    } else {
        active_buffer[count].fork_angle = 0xffff;
    }

    if (have_shock) {
        active_buffer[count].shock_angle = as5600_get_scaled_angle(SHOCK_I2C);
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
    i2c_init(FORK_I2C, 1000000);
    gpio_set_function(FORK_PIN_SDA, GPIO_FUNC_I2C);
    gpio_set_function(FORK_PIN_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(FORK_PIN_SDA);
    gpio_pull_up(FORK_PIN_SCL);

    i2c_init(SHOCK_I2C, 1000000);
    gpio_set_function(SHOCK_PIN_SDA, GPIO_FUNC_I2C);
    gpio_set_function(SHOCK_PIN_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(SHOCK_PIN_SDA);
    gpio_pull_up(SHOCK_PIN_SCL);
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

static bool setup_sensors() {
    absolute_time_t timeout = make_timeout_time_ms(3000);
    while (!((as5600_connected(FORK_I2C) && as5600_detect_magnet(FORK_I2C)) ||
            (as5600_connected(SHOCK_I2C) && as5600_detect_magnet(SHOCK_I2C)))) {
        if (absolute_time_diff_us(get_absolute_time(), timeout) < 0) {
            return false;
        }
        sleep_ms(10);
    }

    have_fork = setup_baseline(FORK_I2C);
    have_shock = setup_baseline(SHOCK_I2C);
    return have_fork || have_shock;
}

static void setup_display(ssd1306_t *disp) {
#ifdef SPI_DISPLAY
    spi_init(DISPLAY_SPI, 1000000);
    gpio_set_function(DISPLAY_PIN_SCK, GPIO_FUNC_SPI);  // SCK
    gpio_set_function(DISPLAY_PIN_MOSI, GPIO_FUNC_SPI); // MOSI

    disp->external_vcc = false;
    ssd1306_proto_t p = {
        DISPLAY_SPI,
        DISPLAY_PIN_CS,   // CS
        DISPLAY_PIN_MISO, // DC
        DISPLAY_PIN_RST   // RST
    };
    ssd1306_init(disp, DISPLAY_WIDTH, DISPLAY_HEIGHT, p);
#else
    ssd1306_proto_t p = {DISPLAY_ADDRESS, I2C_PIO, I2C_SM, pio_i2c_write_blocking};
    ssd1306_init(disp, DISPLAY_WIDTH, DISPLAY_HEIGHT, p);
#endif // SPI_DISPLAY
            
    ssd1306_flip(disp, DISPLAY_FLIPPED);
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
    if (!setup_sensors()) {
        display_message(&disp, "NO SENS");
        sleep_ms(1000);
        state = IDLE;
        return;
    }

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
    if (!wifi_connect()) {
        display_message(&disp, "CONN ERR");
        sleep_ms(1000);
    } else {
        display_message(&disp, "DAT SYNC");
        FRESULT fr;
        DIR dj;
        FILINFO fno;
        uint all = 0;

        // get a list of all .SST files in the root directory
        struct list *to_import = list_create();
        fr = f_findfirst(&dj, &fno, "", "?????.SST");
        while (fr == FR_OK && fno.fname[0]) {
            ++all;
            list_push(to_import, fno.fname);
            fr = f_findnext(&dj, &fno);
        }
        f_closedir(&dj);

        // send all files on the list via TCP, and move them
        // to the "uploaded" directory
        uint err = 0;
        uint curr = 0;
        struct node *n = to_import->head;
        TCHAR path_new[19];
        TCHAR status[10];
        TCHAR failed[12];

        while (n != NULL) {
            ++curr;
            if (send_file(n->data)) {
                sprintf(path_new, "uploaded/%s", n->data);
                f_rename(n->data, path_new);
            } else {
                ++err;
            }
            sprintf(status, "%u / %u", curr, all);
            sprintf(failed, "failed: %u", err);
            ssd1306_clear(&disp);
            ssd1306_draw_string(&disp, 0,  0, 2, status);
            ssd1306_draw_string(&disp, 0, 24, 1, failed);
            ssd1306_show(&disp);

            // wait a bit to avoid weird TCP errors...
            sleep_ms(100);
            n = n->next;
        }
        list_delete(to_import);

        // leave results on the display for a bit
        sleep_ms(3000);
    }
    wifi_disconnect();
    state = IDLE;
}

static void on_idle() {
    // No MSC if there is no USB cable connected, so checking
    // tud is not necessary.
    bool battery = on_battery();
    if (!battery && msc_present()) {
        soft_reset();
    }

    static absolute_time_t timeout = {0};
    if (absolute_time_diff_us(get_absolute_time(), timeout) < 0) {
        timeout = make_timeout_time_ms(1000);

        uint8_t voltage_percentage = ((read_voltage() - BATTERY_MIN_V) / BATTERY_RANGE) * 100;
        static char battery_str[] = " PWR";
        if (battery) {
            if (voltage_percentage > 99) {
                snprintf(battery_str, sizeof(battery_str), "FULL");
            } else {
                snprintf(battery_str, sizeof(battery_str), "% 3d%%", voltage_percentage);
            }
        }

        static char time_str[] = "00:00";
        static datetime_t t;
        rtc_get_datetime(&t);
        snprintf(time_str, sizeof(time_str), "%02d:%02d", t.hour, t.min);

        ssd1306_clear(&disp);
        ssd1306_draw_string(&disp, 96,  0, 1, battery_str);
        ssd1306_draw_string(&disp,   0, 0, 2, time_str);
        if (as5600_connected(FORK_I2C) && as5600_detect_magnet(FORK_I2C)) {
            ssd1306_draw_string(&disp,  0, 24, 1, "fork");
        }
        if (as5600_connected(SHOCK_I2C) && as5600_detect_magnet(SHOCK_I2C)) {
            ssd1306_draw_string(&disp, 40, 24, 1, "shock");
        }
        ssd1306_show(&disp);
    }
}

static void on_sync_time() {
    display_message(&disp, "CONNECT");
    if (!wifi_connect()) {
        display_message(&disp, "CONN ERR");
        sleep_ms(1000);
    } else {
        display_message(&disp, "NTP SYNC");
        if (!sync_rtc_to_ntp()) {
            display_message(&disp, "NTP ERR");
            sleep_ms(1000);
        } else {
            datetime_t dt;
            rtc_get_datetime(&dt);
            ds3231_set_datetime(&rtc, &dt);
        }
    }
    wifi_disconnect();
    state = IDLE;
}

static void on_sleep() {
    sleep_run_from_xosc();
    display_message(&disp, "SLEEP.");

    clocks_hw->sleep_en0 = CLOCKS_SLEEP_EN0_CLK_RTC_RTC_BITS;
    clocks_hw->sleep_en1 = 0x0;
    display_message(&disp, "SLEEP..");

    scb_hw->scr = scb_orig | M0PLUS_SCR_SLEEPDEEP_BITS;
    display_message(&disp, "SLEEP...");

    disable_button(BUTTON_LEFT, false);
    disable_button(BUTTON_RIGHT, true);
    ssd1306_poweroff(&disp);
    state = WAKING;
    __wfi();
}

static void on_waking() {
    rosc_write(&rosc_hw->ctrl, ROSC_CTRL_ENABLE_BITS);

    scb_hw->scr = scb_orig;
    clocks_hw->sleep_en0 = clock0_orig;
    clocks_hw->sleep_en1 = clock1_orig;
    clocks_init();

    ssd1306_poweron(&disp);
    enable_button(BUTTON_LEFT);
    enable_button(BUTTON_RIGHT);
    state = IDLE;
}

static void on_msc() {
    if (!msc_present()) {
        soft_reset();
    }
    tud_task();
}

static void dummy() {
}

static void (*state_handlers[STATES_COUNT])() = {
    on_idle,      /* IDLE */
    on_sleep,     /* SLEEP */
    on_waking,    /* WAKING */
    on_rec_start, /* REC_START */
    dummy,        /* RECORD */
    on_rec_stop,  /* REC_STOP */
    on_sync_time, /* SYNC_TIME */
    on_sync_data, /* SYNC_DATA */
    on_msc        /* MSC */
};

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
    adc_init();

    uint offset = pio_add_program(I2C_PIO, &i2c_program);
    i2c_program_init(I2C_PIO, I2C_SM, offset, PIO_PIN_SDA, PIO_PIN_SCL);

    datetime_t dt;
    ds3231_init(&rtc, I2C_PIO, I2C_SM,
                pio_i2c_write_blocking,
                pio_i2c_read_blocking);
    ds3231_get_datetime(&rtc, &dt);
    rtc_set_datetime(&dt);

    setup_display(&disp);

    if (msc_present()) {
        state = MSC;
        display_message(&disp, "MSC MODE");
    } else {
        create_button(BUTTON_LEFT, NULL, on_left_press, on_left_longpress);
        create_button(BUTTON_RIGHT, NULL, on_right_press, on_right_longpress);

        display_message(&disp, "INIT STOR");
        multicore_launch_core1(&data_storage_core1);
        int err = (int)multicore_fifo_pop_blocking();
        if (err < 0) {
            display_message(&disp, "CARD ERR");
            while(true) { tight_loop_contents(); }
        }
        
        if (!load_config()) {
            display_message(&disp, "CONF ERR");
            while(true) { tight_loop_contents(); }
        }
 
        scb_orig = scb_hw->scr;
        clock0_orig = clocks_hw->sleep_en0;
        clock1_orig = clocks_hw->sleep_en1;

        state = IDLE;
    }

    while (true) {
        state_handlers[state]();
    }

    return 0;
}

