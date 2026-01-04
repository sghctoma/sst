#include "calibration_storage.h"
#include "../util/log.h"
#include "ff.h"
#include "pico/types.h"

#define CALIBRATION_FILENAME "CALIBRATION"

bool calibration_file_exists(void) { return f_stat(CALIBRATION_FILENAME, NULL) == FR_OK; }

bool calibration_load(struct calibration_data *data) {
    FIL fil;
    FRESULT fr = f_open(&fil, CALIBRATION_FILENAME, FA_OPEN_EXISTING | FA_READ);
    if (fr != FR_OK) {
        LOG("CAL", "No CALIBRATION file found\n");
        return false;
    }

    uint br;
    uint8_t magic;

    // Read travel section (mandatory)
    fr = f_read(&fil, &magic, 1, &br);
    if (fr != FR_OK || br != 1 || magic != TRAVEL_MAGIC) {
        LOG("CAL", "Invalid travel magic: 0x%02x\n", magic);
        f_close(&fil);
        return false;
    }

    f_read(&fil, &data->travel.fork_baseline, 2, &br);
    f_read(&fil, &data->travel.fork_inverted, 1, &br);
    f_read(&fil, &data->travel.shock_baseline, 2, &br);
    f_read(&fil, &data->travel.shock_inverted, 1, &br);

    LOG("CAL", "Travel loaded: fork=0x%04x inv=%d, shock=0x%04x inv=%d\n", data->travel.fork_baseline,
        data->travel.fork_inverted, data->travel.shock_baseline, data->travel.shock_inverted);

    // Initialize IMU data as not present
    data->imu_frame.present = false;
    data->imu_fork.present = false;
    data->imu_rear.present = false;

    // Read IMU sections (optional)
    while (f_read(&fil, &magic, 1, &br) == FR_OK && br == 1) {
        struct imu_cal_data *imu = NULL;
        const char *name = NULL;

        if (magic == IMU_FRAME_MAGIC) {
            imu = &data->imu_frame;
            name = "Frame";
        } else if (magic == IMU_FORK_MAGIC) {
            imu = &data->imu_fork;
            name = "Fork";
        } else if (magic == IMU_REAR_MAGIC) {
            imu = &data->imu_rear;
            name = "Rear";
        } else {
            LOG("CAL", "Unknown magic: 0x%02x\n", magic);
            break;
        }

        f_read(&fil, imu->gyro_bias, 6, &br);
        f_read(&fil, imu->accel_bias, 6, &br);
        f_read(&fil, imu->rotation, 36, &br);
        f_read(&fil, &imu->cal_temperature, 2, &br);
        imu->present = true;
        LOG("CAL", "%s IMU calibration loaded\n", name);
    }

    f_close(&fil);
    return true;
}

bool calibration_create_with_travel(const struct travel_cal_data *travel) {
    FIL fil;
    FRESULT fr = f_open(&fil, CALIBRATION_FILENAME, FA_CREATE_ALWAYS | FA_WRITE);
    if (fr != FR_OK) {
        LOG("CAL", "Failed to create CALIBRATION file\n");
        return false;
    }

    uint bw;
    uint8_t magic = TRAVEL_MAGIC;

    f_write(&fil, &magic, 1, &bw);
    f_write(&fil, &travel->fork_baseline, 2, &bw);
    f_write(&fil, &travel->fork_inverted, 1, &bw);
    f_write(&fil, &travel->shock_baseline, 2, &bw);
    f_write(&fil, &travel->shock_inverted, 1, &bw);

    f_close(&fil);

    LOG("CAL", "Travel saved: fork=0x%04x inv=%d, shock=0x%04x inv=%d\n", travel->fork_baseline, travel->fork_inverted,
        travel->shock_baseline, travel->shock_inverted);

    return true;
}

bool calibration_append_imu(char magic, const struct imu_cal_data *imu) {
    FIL fil;
    FRESULT fr = f_open(&fil, CALIBRATION_FILENAME, FA_OPEN_EXISTING | FA_WRITE);
    if (fr != FR_OK) {
        LOG("CAL", "Failed to open CALIBRATION file for IMU append\n");
        return false;
    }

    // Seek to end of file
    f_lseek(&fil, f_size(&fil));

    uint bw;
    uint8_t m = (uint8_t)magic;

    f_write(&fil, &m, 1, &bw);
    f_write(&fil, imu->gyro_bias, 6, &bw);
    f_write(&fil, imu->accel_bias, 6, &bw);
    f_write(&fil, imu->rotation, 36, &bw);
    f_write(&fil, &imu->cal_temperature, 2, &bw);

    f_close(&fil);

    LOG("CAL", "IMU calibration appended (magic=%c)\n", magic);

    return true;
}
