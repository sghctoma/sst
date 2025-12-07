#include <stdint.h>
#include <stdio.h>
#include <time.h>

#ifndef USB_UART_DEBUG
#include "bsp/board.h"
#include "device/usbd.h"
#endif

#include "cyw43_ll.h"
#include "ff.h"
#include "hardware/adc.h"
#include "hardware/gpio.h"
#include "hardware/rosc.h"
#include "hardware/timer.h"
#include "hardware/watchdog.h"
#include "pico/cyw43_arch.h"
#include "pico/multicore.h"
#include "pico/platform.h"
#include "pico/runtime_init.h"
#include "pico/sleep.h"
#include "pico/time.h"
#include "pico/types.h"
#include "pico/unique_id.h"

// For scb_hw so we can enable deep sleep
#include "hardware/structs/scb.h"

#include "../net/tcpserver.h"
#include "../ntp//ntp.h"
#include "../rtc//ds3231.h"
#include "../sensor/sensor.h"
#include "../util/config.h"
#include "../util/list.h"
#include "../util/log.h"
#include "sst.h"

#include "hardware_config.h"

static volatile enum state state;

static uint32_t scb_orig;
static uint32_t clock0_orig;
static uint32_t clock1_orig;

static ssd1306_t disp;
static repeating_timer_t data_acquisition_timer;
static FIL recording;
static struct tcpserver server;

struct ds3231 rtc;

extern struct sensor fork_sensor;
extern struct sensor shock_sensor;

// ----------------------------------------------------------------------------
// Helper functions

static void display_message(ssd1306_t *disp, char *message) {
    ssd1306_clear(disp);
    ssd1306_draw_string(disp, 0, 10, 2, message);
    ssd1306_show(disp);
}

static void soft_reset() {
    watchdog_enable(1, 1);
    while (1);
}

static bool on_battery() {
    cyw43_thread_enter();
    bool ret = !cyw43_arch_gpio_get(2);
    cyw43_thread_exit();
    return ret;
}

static float read_voltage() {
    cyw43_thread_enter();
    sleep_ms(1);         // NOTE ADC3 readings are way too high without this sleep.
    adc_gpio_init(29);   // GPIO29 measures VSYS/3
    adc_select_input(3); // GPIO29 is ADC #3
    uint32_t vsys = 0;
    for (int i = 0; i < 3; i++) { vsys += adc_read(); }
    cyw43_thread_exit();
    const float conversion_factor = 3.3f / (1 << 12);
    float ret = vsys * conversion_factor;
    return ret;
}

static bool msc_present() {
#ifdef USB_UART_DEBUG
    return false;
#else
    // Wait for a maximum of 1 second for USB MSC to initialize
    uint32_t t = time_us_32();
    while (!tud_ready()) {
        if (time_us_32() - t > 1000000) {
            return false;
        }
        tud_task();
    }
    return true;
#endif
}

static bool wifi_connect(bool do_ntp) {
    LOG("WiFi", "Enabling STA mode\n");
    cyw43_arch_enable_sta_mode();
    LOG("WiFi", "Connecting to SSID: %s\n", config.ssid);
    bool ret = cyw43_arch_wifi_connect_timeout_ms(config.ssid, config.psk, CYW43_AUTH_WPA2_AES_PSK, 20000) == 0;
    if (ret) {
        LOG("WiFi", "Connected successfully\n");
        if (do_ntp) {
            LOG("WiFi", "Syncing RTC to NTP\n");
            sync_rtc_to_ntp();
        }
    } else {
        LOG("WiFi", "Connection failed\n");
    }
    return ret;
}

static void wifi_disconnect() {
    LOG("WiFi", "Disconnecting\n");
    cyw43_arch_disable_sta_mode();
    sleep_ms(100);
}

static void calibrate_if_needed() {
    gpio_init(BUTTON_LEFT);
    gpio_pull_up(BUTTON_LEFT);

    FRESULT fr = f_stat("CALIBRATION", NULL);
    bool button_pressed = !gpio_get(BUTTON_LEFT);
    LOG("CAL", "CALIBRATION file %s, button %s\n", fr == FR_OK ? "exists" : "missing",
        button_pressed ? "pressed" : "not pressed");

    if (fr != FR_OK || button_pressed) {
        LOG("CAL", "Entering calibration mode\n");
        state = CAL_IDLE_1;
    } else {
        LOG("CAL", "Skipping calibration\n");
        state = IDLE;
    }
}

// ----------------------------------------------------------------------------
// Data acquisition

static const uint16_t SAMPLE_RATE = 1000;

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

    active_buffer[count].fork_angle = fork_sensor.measure(&fork_sensor);
    active_buffer[count].shock_angle = shock_sensor.measure(&shock_sensor);

    count += 1;

    return state == RECORD; // keep repeating if we are still recording
}

static bool start_sensors() {
    absolute_time_t timeout = make_timeout_time_ms(3000);
    while (!(fork_sensor.check_availability(&fork_sensor) || shock_sensor.check_availability(&shock_sensor))) {
        if (absolute_time_diff_us(get_absolute_time(), timeout) < 0) {
            return false;
        }
        sleep_ms(10);
    }

    FIL calibration_fil;
    FRESULT fr = f_open(&calibration_fil, "CALIBRATION", FA_OPEN_EXISTING | FA_READ);
    if (!(fr == FR_OK || fr == FR_EXIST)) {
        return false;
    }

    uint br;
    uint16_t baseline;
    bool inverted;
    f_read(&calibration_fil, &baseline, sizeof(uint16_t), &br);
    f_read(&calibration_fil, &inverted, sizeof(bool), &br);
    fork_sensor.start(&fork_sensor, baseline, inverted);
    LOG("SENSOR", "Fork sensor: baseline=0x%04x, inverted=%d, available=%d\n", baseline, inverted,
        fork_sensor.available);

    f_read(&calibration_fil, &baseline, sizeof(uint16_t), &br);
    f_read(&calibration_fil, &inverted, sizeof(bool), &br);
    shock_sensor.start(&shock_sensor, baseline, inverted);
    LOG("SENSOR", "Shock sensor: baseline=0x%04x, inverted=%d, available=%d\n", baseline, inverted,
        shock_sensor.available);

    f_close(&calibration_fil);
    return fork_sensor.available || shock_sensor.available;
}

// ----------------------------------------------------------------------------
// Data storage
static int setup_storage() {
    static FATFS fs;
    FRESULT fr = f_mount(&fs, "", 1);
    if (fr != FR_OK) {
        LOG("STORAGE", "Failed to mount filesystem: %d\n", fr);
        return PICO_ERROR_GENERIC;
    }
    LOG("STORAGE", "Filesystem mounted\n");

    char board_id_str[2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1];
    pico_get_unique_board_id_string(board_id_str, 2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1);
    FIL f;
    uint btw;
    fr = f_open(&f, "BOARDID", FA_OPEN_ALWAYS | FA_WRITE);
    if (fr == FR_OK || fr == FR_EXIST) {
        f_write(&f, board_id_str, 2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES, &btw);
    }
    f_close(&f);

    fr = f_mkdir("uploaded");
    if (!(fr == FR_OK || fr == FR_EXIST)) {
        return PICO_ERROR_GENERIC;
    }

    fr = f_mkdir("trash");
    if (!(fr == FR_OK || fr == FR_EXIST)) {
        return PICO_ERROR_GENERIC;
    }

    return 0;
}

static int open_datafile() {
    // start from 1, 0 is the special value for the headers in tcpserver
    uint16_t index = 1;
    FIL index_fil;
    FRESULT fr = f_open(&index_fil, "INDEX", FA_OPEN_EXISTING | FA_READ);
    if (fr == FR_OK || fr == FR_EXIST) {
        uint br;
        f_read(&index_fil, &index, 2, &br);
        if (br == 2) {
            index = index + 1;
        }
    }
    f_close(&index_fil);

    fr = f_open(&index_fil, "INDEX", FA_OPEN_ALWAYS | FA_WRITE);
    if (fr == FR_OK) {
        f_lseek(&index_fil, 0);
        uint bw;
        f_write(&index_fil, &index, 2, &bw);
        f_close(&index_fil);
    } else {
        return PICO_ERROR_GENERIC;
    }

    char filename[10];
    sprintf(filename, "%05u.SST", index);
    LOG("STORAGE", "Creating file: %s\n", filename);
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
        switch (cmd) {
            case OPEN:
                multicore_fifo_drain();
                index = open_datafile();
                multicore_fifo_push_blocking(index);
                multicore_fifo_push_blocking((uintptr_t)databuffer2);
                break;
            case DUMP:
                buffer = (struct record *)((uintptr_t)multicore_fifo_pop_blocking());
                multicore_fifo_push_blocking((uintptr_t)buffer);
                f_write(&recording, buffer, sizeof(struct record) * BUFFER_SIZE, NULL);
                f_sync(&recording);
                break;
            case FINISH:
                size = (uint16_t)multicore_fifo_pop_blocking();
                buffer = (struct record *)((uintptr_t)multicore_fifo_pop_blocking());
                f_write(&recording, buffer, sizeof(struct record) * size, NULL);
                f_sync(&recording);
                f_close(&recording);
                break;
        }
    }
}

// ----------------------------------------------------------------------------
// Setup functions

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

static void on_cal_idle() {
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

        // Print sensor values
        if (fork_sensor.check_availability(&fork_sensor)) {
            uint16_t fork_val = fork_sensor.measure(&fork_sensor);
            LOG("SENSOR", "Fork: 0x%04x\n", fork_val);
        }
        if (shock_sensor.check_availability(&shock_sensor)) {
            uint16_t shock_val = shock_sensor.measure(&shock_sensor);
            LOG("SENSOR", "Shock: 0x%04x\n", shock_val);
        }

        ssd1306_clear(&disp);
        ssd1306_draw_string(&disp, 96, 0, 1, battery_str);
        ssd1306_draw_string(&disp, 0, 0, 2, state == CAL_IDLE_1 ? "CAL EXP" : "CAL COMP");
        if (fork_sensor.check_availability(&fork_sensor)) {
            ssd1306_draw_string(&disp, 0, 24, 1, "fork");
        }
        if (shock_sensor.check_availability(&shock_sensor)) {
            ssd1306_draw_string(&disp, 40, 24, 1, "shock");
        }
        ssd1306_show(&disp);
    }
}

static void on_cal_exp() {
    LOG("CAL", "Calibrating expanded position\n");
    fork_sensor.calibrate_expanded(&fork_sensor);
    shock_sensor.calibrate_expanded(&shock_sensor);

    LOG("CAL", "Fork baseline: 0x%04x, Shock baseline: 0x%04x\n", fork_sensor.baseline, shock_sensor.baseline);

    if (fork_sensor.baseline == 0xffff && shock_sensor.baseline == 0xffff) {
        LOG("CAL", "Error: Both sensors failed calibration\n");
        display_message(&disp, "CAL ERR");
        sleep_ms(1000);
        state = CAL_IDLE_1;
        return;
    }

    LOG("CAL", "Expanded calibration complete\n");
    state = CAL_IDLE_2;
}

static void on_cal_comp() {
    LOG("CAL", "Calibrating compressed position\n");
    fork_sensor.calibrate_compressed(&fork_sensor);
    shock_sensor.calibrate_compressed(&shock_sensor);

    LOG("CAL", "Fork: baseline=0x%04x inverted=%d\n", fork_sensor.baseline, fork_sensor.inverted);
    LOG("CAL", "Shock: baseline=0x%04x inverted=%d\n", shock_sensor.baseline, shock_sensor.inverted);

    FIL calibration_fil;
    FRESULT fr = f_open(&calibration_fil, "CALIBRATION", FA_OPEN_ALWAYS | FA_WRITE);
    if (!(fr == FR_OK || fr == FR_EXIST)) {
        LOG("CAL", "Error: Failed to open CALIBRATION file\n");
        display_message(&disp, "CAL ERR");
        sleep_ms(1000);
        state = CAL_IDLE_2;
        return;
    }

    uint bw;
    f_write(&calibration_fil, &fork_sensor.baseline, sizeof(uint16_t), &bw);
    f_write(&calibration_fil, (const void *)&fork_sensor.inverted, sizeof(bool), &bw);
    f_write(&calibration_fil, &shock_sensor.baseline, sizeof(uint16_t), &bw);
    f_write(&calibration_fil, (const void *)&shock_sensor.inverted, sizeof(bool), &bw);
    f_close(&calibration_fil);

    LOG("CAL", "Calibration saved successfully\n");
    state = IDLE;
}

static void on_rec_start() {
    LOG("REC", "Starting recording session\n");
    count = 0;
    active_buffer = databuffer1;
    multicore_fifo_drain();

    display_message(&disp, "INIT SENS");
    if (!start_sensors()) {
        LOG("REC", "No sensors available\n");
        display_message(&disp, "NO SENS");
        sleep_ms(1000);
        state = IDLE;
        return;
    }

    state = RECORD;
    char msg[8];
    sprintf(msg, "REC:%s|%s", fork_sensor.available ? "F" : ".", shock_sensor.available ? "S" : ".");
    display_message(&disp, msg);

    multicore_fifo_push_blocking(OPEN);
    int index = (int)multicore_fifo_pop_blocking();
    if (index < 0) {
        LOG("REC", "Failed to open data file\n");
        display_message(&disp, "FILE ERR");
        while (true) { tight_loop_contents(); }
    }
    LOG("REC", "Recording to file index %d\n", index);

    // Start data acquisition timer
    if (!add_repeating_timer_us(-1000000 / SAMPLE_RATE, data_acquisition_cb, NULL, &data_acquisition_timer)) {
        display_message(&disp, "TIMER ERR");
        while (true) { tight_loop_contents(); }
    }
}

static void on_rec_stop() {
    LOG("REC", "Stopping recording, samples: %u\n", count);
    state = IDLE;
    display_message(&disp, "IDLE");
    cancel_repeating_timer(&data_acquisition_timer);

    multicore_fifo_push_blocking(FINISH);
    multicore_fifo_push_blocking(count);
    multicore_fifo_push_blocking((uintptr_t)active_buffer);
}

static void on_sync_data() {
    LOG("SYNC", "Starting data sync\n");
    display_message(&disp, "CONNECT");
    if (!wifi_connect(true)) {
        LOG("SYNC", "Could not connect wifi\n");
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
        LOG("SYNC", "Found %u files to sync\n", all);

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
            LOG("SYNC", "Sending file: %s (%u/%u)\n", (char *)n->data, curr, all);
            if (send_file(n->data)) {
                LOG("SYNC", "File sent successfully\n");
                sprintf(path_new, "uploaded/%s", n->data);
                f_rename(n->data, path_new);
            } else {
                LOG("SYNC", "File send failed\n");
                ++err;
            }
            sprintf(status, "%u / %u", curr, all);
            sprintf(failed, "failed: %u", err);
            ssd1306_clear(&disp);
            ssd1306_draw_string(&disp, 0, 0, 2, status);
            ssd1306_draw_string(&disp, 0, 24, 1, failed);
            ssd1306_show(&disp);

            // wait a bit to avoid weird TCP errors...
            sleep_ms(100);
            n = n->next;
        }
        list_delete(to_import);
        LOG("SYNC", "Sync complete: %u succeeded, %u failed\n", all - err, err);

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
        static struct tm tz_tm;
        time_t t = rtc_timestamp();
        localtime_r(&t, &tz_tm);
        snprintf(time_str, sizeof(time_str), "%02d:%02d", tz_tm.tm_hour, tz_tm.tm_min);

        ssd1306_clear(&disp);
        ssd1306_draw_string(&disp, 96, 0, 1, battery_str);
        ssd1306_draw_string(&disp, 0, 0, 2, time_str);
        if (fork_sensor.check_availability(&fork_sensor)) {
            ssd1306_draw_string(&disp, 0, 24, 1, "fork");
        }
        if (shock_sensor.check_availability(&shock_sensor)) {
            ssd1306_draw_string(&disp, 40, 24, 1, "shock");
        }
        ssd1306_show(&disp);
    }
}

static void on_sleep() {
    LOG("POWER", "Entering sleep mode\n");
    sleep_run_from_xosc();
    display_message(&disp, "SLEEP.");

#if PICO_RP2040
    clocks_hw->sleep_en0 = CLOCKS_SLEEP_EN0_CLK_RTC_RTC_BITS;
    clocks_hw->sleep_en1 = 0x0;
#endif
    display_message(&disp, "SLEEP..");

#if PICO_RP2040
    scb_hw->scr = scb_orig | M0PLUS_SCR_SLEEPDEEP_BITS;
#else
    scb_hw->scr = scb_orig | M33_SCR_SLEEPDEEP_BITS;
#endif
    display_message(&disp, "SLEEP...");

    disable_button(BUTTON_LEFT, false);
    disable_button(BUTTON_RIGHT, true);
    ssd1306_poweroff(&disp);
    state = WAKING;
    __wfi();
}

static void on_waking() {
    LOG("POWER", "Waking from sleep\n");
    rosc_write(&rosc_hw->ctrl, ROSC_CTRL_ENABLE_BITS);

    scb_hw->scr = scb_orig;
    clocks_hw->sleep_en0 = clock0_orig;
    clocks_hw->sleep_en1 = clock1_orig;
    runtime_init_clocks();

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

static void dummy() { tight_loop_contents(); }

static void on_serve_tcp() {
    display_message(&disp, "CONNECT");
    if (!wifi_connect(true)) {
        display_message(&disp, "CONN ERR");
        sleep_ms(1000);
    } else if (tcpserver_init(&server)) {
        display_message(&disp, "SERVER ON");
        tcpserver_serve(&server);
    }
    wifi_disconnect();
    state = IDLE;
}

static void (*state_handlers[STATES_COUNT])() = {
    on_idle,      /* IDLE */
    on_sleep,     /* SLEEP */
    on_waking,    /* WAKING */
    on_rec_start, /* REC_START */
    dummy,        /* RECORD */
    on_rec_stop,  /* REC_STOP */
    on_sync_data, /* SYNC_DATA */
    on_serve_tcp, /* SERVE_TCP */
    on_msc,       /* MSC */
    on_cal_idle,  /* CAL_IDLE_1 */
    on_cal_exp,   /* CAL_EXP */
    on_cal_idle,  /* CAL_IDLE_2 */
    on_cal_comp,  /* CAL_COMP */
};

// ----------------------------------------------------------------------------
// Button handlers

static void on_left_press(void *user_data) {
    switch (state) {
        case CAL_IDLE_1:
            state = CAL_EXP;
            break;
        case CAL_IDLE_2:
            state = CAL_COMP;
            break;
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
    switch (state) {
        case IDLE:
            state = SYNC_DATA;
            break;
        default:
            break;
    }
}

static void on_right_press(void *user_data) {
    switch (state) {
        case IDLE:
            state = SLEEP;
            break;
        case SERVE_TCP:
            tcpserver_finish(&server);
            state = IDLE;
            break;
        default:
            break;
    }
}

static void on_right_longpress(void *user_data) {
    switch (state) {
        case IDLE:
            state = SERVE_TCP;
            break;
        default:
            break;
    }
}

// ----------------------------------------------------------------------------
// Entry point

int main() {
#ifndef USB_UART_DEBUG
    board_init();
    tusb_init();
#else
    stdio_usb_init();
    sleep_ms(3000); // Give time for the tty to get enumerated on the host
#endif

    adc_init();
    fork_sensor.init(&fork_sensor);
    shock_sensor.init(&shock_sensor);
#ifndef NDEBUG
    stdio_uart_init();
#endif

    uint offset = pio_add_program(I2C_PIO, &i2c_program);
    i2c_program_init(I2C_PIO, I2C_SM, offset, PIO_PIN_SDA, PIO_PIN_SDA + 1);

    struct tm tm_now;
    LOG("DS3231", "Initializing RTC\n");
    ds3231_init(&rtc, I2C_PIO, I2C_SM, pio_i2c_write_blocking, pio_i2c_read_blocking);
    sleep_ms(1); // without this, garbage values are read from the RTC
    LOG("DS3231", "Reading datetime\n");
    ds3231_get_datetime(&rtc, &tm_now);
    LOG("DS3231", "Time: %04d-%02d-%02d %02d:%02d:%02d\n", tm_now.tm_year + 1900, tm_now.tm_mon + 1, tm_now.tm_mday,
        tm_now.tm_hour, tm_now.tm_min, tm_now.tm_sec);

    if (!aon_timer_start_calendar(&tm_now)) {
        setup_display(&disp);
        display_message(&disp, "AON ERR");
        while (true) { tight_loop_contents(); }
    }

    setup_display(&disp);

#ifndef USB_UART_DEBUG
    if (msc_present()) {
        LOG("INIT", "Entering MSC mode\n");
        state = MSC;
        display_message(&disp, "MSC MODE");
    } else {
#endif

        display_message(&disp, "INIT STOR");
        multicore_launch_core1(&data_storage_core1);
        int err = (int)multicore_fifo_pop_blocking();
        if (err < 0) {
            display_message(&disp, "CARD ERR");
            while (true) { tight_loop_contents(); }
        }
        LOG("INIT", "Storage initialized\n");

        if (!load_config()) {
            display_message(&disp, "CONF ERR");
            while (true) { tight_loop_contents(); }
        }
        LOG("INIT", "Config loaded\n");

        setup_ntp(config.ntp_server);
        cyw43_arch_init_with_country(config.country);
        setenv("TZ", config.timezone, 1);
        tzset();
        LOG("INIT", "WiFi initialized, country=%d, timezone=%s\n", config.country, config.timezone);

        scb_orig = scb_hw->scr;
        clock0_orig = clocks_hw->sleep_en0;
        clock1_orig = clocks_hw->sleep_en1;

        calibrate_if_needed();

        create_button(BUTTON_LEFT, NULL, on_left_press, on_left_longpress);
        create_button(BUTTON_RIGHT, NULL, on_right_press, on_right_longpress);

#ifndef USB_UART_DEBUG
    }
#endif

    while (true) { state_handlers[state](); }

    return 0;
}
