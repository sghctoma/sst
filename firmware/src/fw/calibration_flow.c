#include "calibration_flow.h"
#include "../util/log.h"
#include "calibration_storage.h"
#include "hardware_config.h"

#include "hardware/adc.h"
#include "hardware/gpio.h"
#include "pico/cyw43_arch.h"
#include "pico/time.h"

#include <string.h>

#define CAL_MAX_RETRIES 3

// ----------------------------------------------------------------------------
// Display & button helper functions

// TODO: This duplicates some code from main, that would ideally be abstracted in it's own struct

static void display_message(ssd1306_t *disp, const char *message) {
    ssd1306_clear(disp);
    ssd1306_draw_string(disp, 0, 10, 2, message);
    ssd1306_show(disp);
}

static bool on_battery(void) {
    cyw43_thread_enter();
    bool ret = !cyw43_arch_gpio_get(2);
    cyw43_thread_exit();
    return ret;
}

static float read_voltage(void) {
    cyw43_thread_enter();
    sleep_ms(1);
    adc_gpio_init(29);
    adc_select_input(3);
    uint32_t vsys = 0;
    for (int i = 0; i < 3; i++) { vsys += adc_read(); }
    cyw43_thread_exit();
    const float conversion_factor = 3.3f / (1 << 12);
    return vsys * conversion_factor;
}

static bool has_any_imu(struct calibration_ctx *ctx) {
    return (ctx->imu_frame && ctx->imu_frame->available) || (ctx->imu_fork && ctx->imu_fork->available) ||
           (ctx->imu_rear && ctx->imu_rear->available);
}

// Idle display update
static void idle_update(struct calibration_ctx *ctx, const char *message) {
    bool battery = on_battery();
    uint8_t voltage_pct = ((read_voltage() - BATTERY_MIN_V) / BATTERY_RANGE) * 100;

    char battery_str[5] = " PWR";
    if (battery) {
        if (voltage_pct > 99) {
            snprintf(battery_str, sizeof(battery_str), "FULL");
        } else {
            snprintf(battery_str, sizeof(battery_str), "% 3d%%", voltage_pct);
        }
    }

    ssd1306_clear(ctx->disp);
    ssd1306_draw_string(ctx->disp, 96, 0, 1, battery_str);
    ssd1306_draw_string(ctx->disp, 0, 0, 2, message);
    if (ctx->fork->check_availability(ctx->fork)) {
        ssd1306_draw_string(ctx->disp, 0, 24, 1, "fork");
    }
    if (ctx->shock->check_availability(ctx->shock)) {
        ssd1306_draw_string(ctx->disp, 40, 24, 1, "shock");
    }
    ssd1306_show(ctx->disp);
}

// Simple button poll to advance calibration steps
static void wait_for_left_button(struct calibration_ctx *ctx, const char *message) {
    absolute_time_t update_time = get_absolute_time();

    while (true) {
        // Update display periodically
        if (absolute_time_diff_us(get_absolute_time(), update_time) < 0) {
            update_time = make_timeout_time_ms(500);
            idle_update(ctx, message);
        }

        if (!gpio_get(BUTTON_LEFT)) {
            sleep_ms(50); // debounce
            while (!gpio_get(BUTTON_LEFT)) { tight_loop_contents(); }
            sleep_ms(50); // debounce release
            return;
        }

        sleep_ms(10);
    }
}

// ----------------------------------------------------------------------------
// Calibration steps

static bool do_travel_expanded(struct calibration_ctx *ctx) {
    LOG("CAL", "Calibrating travel expanded\n");

    ctx->fork->calibrate_expanded(ctx->fork);
    ctx->shock->calibrate_expanded(ctx->shock);

    LOG("CAL", "Fork baseline: 0x%04x, Shock baseline: 0x%04x\n", ctx->fork->baseline, ctx->shock->baseline);

    if (ctx->fork->baseline == 0xffff && ctx->shock->baseline == 0xffff) {
        LOG("CAL", "Error: Both sensors failed calibration\n");
        display_message(ctx->disp, "CAL ERR");
        sleep_ms(1000);
        return false;
    }

    LOG("CAL", "Travel expanded calibration complete\n");
    return true;
}

static bool do_travel_compressed(struct calibration_ctx *ctx) {
    LOG("CAL", "Calibrating travel compressed\n");

    ctx->fork->calibrate_compressed(ctx->fork);
    ctx->shock->calibrate_compressed(ctx->shock);

    LOG("CAL", "Fork: baseline=0x%04x inverted=%d\n", ctx->fork->baseline, ctx->fork->inverted);
    LOG("CAL", "Shock: baseline=0x%04x inverted=%d\n", ctx->shock->baseline, ctx->shock->inverted);

    struct travel_cal_data travel = {
        .fork_baseline = ctx->fork->baseline,
        .fork_inverted = ctx->fork->inverted ? 1 : 0,
        .shock_baseline = ctx->shock->baseline,
        .shock_inverted = ctx->shock->inverted ? 1 : 0,
    };

    if (!calibration_create_with_travel(&travel)) {
        LOG("CAL", "Error: Failed to save travel calibration\n");
        display_message(ctx->disp, "CAL ERR");
        sleep_ms(1000);
        return false;
    }

    LOG("CAL", "Travel calibration saved\n");
    return true;
}

static void do_imu_stationary(struct calibration_ctx *ctx) {
    display_message(ctx->disp, "IMU STAT..");
    LOG("CAL", "Starting IMU stationary calibration\n");

    if (ctx->imu_frame && ctx->imu_frame->available) {
        LOG("CAL", "Calibrating Frame IMU stationary\n");
        imu_sensor_calibrate_stationary(ctx->imu_frame);
    }
    if (ctx->imu_fork && ctx->imu_fork->available) {
        LOG("CAL", "Calibrating Fork IMU stationary\n");
        imu_sensor_calibrate_stationary(ctx->imu_fork);
    }
    if (ctx->imu_rear && ctx->imu_rear->available) {
        LOG("CAL", "Calibrating Rear IMU stationary\n");
        imu_sensor_calibrate_stationary(ctx->imu_rear);
    }

    LOG("CAL", "IMU stationary calibration complete\n");
}

static void copy_imu_cal_to_data(struct imu_sensor *imu, struct imu_cal_data *data) {
    data->present = true;
    memcpy(data->gyro_bias, imu->calibration.gyro_bias, sizeof(data->gyro_bias));
    memcpy(data->accel_bias, imu->calibration.accel_bias, sizeof(data->accel_bias));
    memcpy(data->rotation, &imu->calibration.rotation, sizeof(data->rotation));
    data->cal_temperature = imu->calibration.cal_temperature;
}

static void copy_data_to_imu_cal(struct imu_cal_data *data, struct imu_sensor *imu) {
    memcpy(imu->calibration.gyro_bias, data->gyro_bias, sizeof(data->gyro_bias));
    memcpy(imu->calibration.accel_bias, data->accel_bias, sizeof(data->accel_bias));
    memcpy(&imu->calibration.rotation, data->rotation, sizeof(data->rotation));
    imu->calibration.cal_temperature = data->cal_temperature;
}

static bool do_imu_tilt(struct calibration_ctx *ctx) {
    display_message(ctx->disp, "IMU TILT..");
    LOG("CAL", "Starting IMU tilt calibration\n");

    if (ctx->imu_frame && ctx->imu_frame->available) {
        LOG("CAL", "Calibrating Frame IMU tilt\n");
        imu_sensor_calibrate_tilted(ctx->imu_frame);
    }
    if (ctx->imu_fork && ctx->imu_fork->available) {
        LOG("CAL", "Calibrating Fork IMU tilt\n");
        imu_sensor_calibrate_tilted(ctx->imu_fork);
    }
    if (ctx->imu_rear && ctx->imu_rear->available) {
        LOG("CAL", "Calibrating Rear IMU tilt\n");
        imu_sensor_calibrate_tilted(ctx->imu_rear);
    }

    LOG("CAL", "IMU tilt calibration complete\n");

    // Save IMU calibrations
    struct imu_cal_data imu_data;

    if (ctx->imu_frame && ctx->imu_frame->available) {
        copy_imu_cal_to_data(ctx->imu_frame, &imu_data);
        if (!calibration_append_imu(IMU_FRAME_MAGIC, &imu_data)) {
            LOG("CAL", "Failed to save frame IMU calibration\n");
            display_message(ctx->disp, "SAVE ERR");
            sleep_ms(1000);
            return false;
        }
    }
    if (ctx->imu_fork && ctx->imu_fork->available) {
        copy_imu_cal_to_data(ctx->imu_fork, &imu_data);
        if (!calibration_append_imu(IMU_FORK_MAGIC, &imu_data)) {
            LOG("CAL", "Failed to save fork IMU calibration\n");
            display_message(ctx->disp, "SAVE ERR");
            sleep_ms(1000);
            return false;
        }
    }
    if (ctx->imu_rear && ctx->imu_rear->available) {
        copy_imu_cal_to_data(ctx->imu_rear, &imu_data);
        if (!calibration_append_imu(IMU_REAR_MAGIC, &imu_data)) {
            LOG("CAL", "Failed to save rear IMU calibration\n");
            display_message(ctx->disp, "SAVE ERR");
            sleep_ms(1000);
            return false;
        }
    }

    display_message(ctx->disp, "CAL OK");
    sleep_ms(1000);
    return true;
}

// ----------------------------------------------------------------------------
// Public API

bool calibration_check_needed(struct calibration_ctx *ctx) {
    gpio_init(BUTTON_LEFT);
    gpio_pull_up(BUTTON_LEFT);

    bool file_exists = calibration_file_exists();
    bool button_pressed = !gpio_get(BUTTON_LEFT);

    LOG("CAL", "CALIBRATION file %s, button %s\n", file_exists ? "exists" : "missing",
        button_pressed ? "pressed" : "not pressed");

    return !file_exists || button_pressed;
}

bool calibration_run(struct calibration_ctx *ctx) {
    LOG("CAL", "Entering calibration mode\n");

    // Wait for the button used to enter calibration to be released
    while (!gpio_get(BUTTON_LEFT)) { tight_loop_contents(); }
    sleep_ms(100);

    for (int attempt = 0; attempt < CAL_MAX_RETRIES; attempt++) {
        if (attempt > 0) {
            LOG("CAL", "Retry attempt %d/%d\n", attempt + 1, CAL_MAX_RETRIES);
        }

        // Travel calibration - expanded position
        idle_update(ctx, "CAL EXP");
        wait_for_left_button(ctx, "CAL EXP");

        if (!do_travel_expanded(ctx)) {
            continue;
        }

        // Travel calibration - compressed position
        idle_update(ctx, "CAL COMP");
        wait_for_left_button(ctx, "CAL COMP");

        if (!do_travel_compressed(ctx)) {
            continue;
        }

        // IMU calibration (if any IMU available)
        if (has_any_imu(ctx)) {
            // IMU level position
            idle_update(ctx, "IMU LEVEL");
            wait_for_left_button(ctx, "IMU LEVEL");
            do_imu_stationary(ctx);

            // IMU tilted position
            idle_update(ctx, "IMU TILT");
            wait_for_left_button(ctx, "IMU TILT");
            if (!do_imu_tilt(ctx)) {
                continue;
            }
        }

        LOG("CAL", "Calibration complete\n");
        return true;
    }

    LOG("CAL", "Calibration failed after %d attempts\n", CAL_MAX_RETRIES);
    display_message(ctx->disp, "CAL FAIL");
    return false;
}

bool calibration_apply_to_sensors(struct calibration_ctx *ctx) {
    // Wait for at least one travel sensor
    absolute_time_t timeout = make_timeout_time_ms(3000);
    while (!(ctx->fork->check_availability(ctx->fork) || ctx->shock->check_availability(ctx->shock))) {
        if (absolute_time_diff_us(get_absolute_time(), timeout) < 0) {
            return false;
        }
        sleep_ms(10);
    }

    struct calibration_data data;
    if (!calibration_load(&data)) {
        return false;
    }

    // Apply travel calibration
    ctx->fork->start(ctx->fork, data.travel.fork_baseline, data.travel.fork_inverted != 0);
    ctx->shock->start(ctx->shock, data.travel.shock_baseline, data.travel.shock_inverted != 0);

    LOG("CAL", "Fork sensor: baseline=0x%04x, inverted=%d, available=%d\n", data.travel.fork_baseline,
        data.travel.fork_inverted, ctx->fork->available);
    LOG("CAL", "Shock sensor: baseline=0x%04x, inverted=%d, available=%d\n", data.travel.shock_baseline,
        data.travel.shock_inverted, ctx->shock->available);

    // Apply IMU calibrations
    if (data.imu_frame.present && ctx->imu_frame && ctx->imu_frame->available) {
        copy_data_to_imu_cal(&data.imu_frame, ctx->imu_frame);
        LOG("CAL", "Frame IMU calibration applied\n");
    }

    if (data.imu_fork.present && ctx->imu_fork && ctx->imu_fork->available) {
        copy_data_to_imu_cal(&data.imu_fork, ctx->imu_fork);
        LOG("CAL", "Fork IMU calibration applied\n");
    }

    if (data.imu_rear.present && ctx->imu_rear && ctx->imu_rear->available) {
        copy_data_to_imu_cal(&data.imu_rear, ctx->imu_rear);
        LOG("CAL", "Rear IMU calibration applied\n");
    }

    return ctx->fork->available || ctx->shock->available;
}
