#include "lsm6dso.h"
#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "hardware/spi.h"
#include "imu_sensor.h"
#include "pico/error.h"
#include "pico/time.h"
#include <stdio.h>

#define WHO_AM_I   0x0F
#define CTRL1_XL   0x10
#define CTRL2_G    0x11
#define CTRL3_C    0x12
#define CTRL4_C    0x13
#define OUT_TEMP_L 0x20
#define OUTX_L_G   0x22

#define WRITE_MASK 0x7F
#define READ_MASK  0x80

static void write_register(struct imu_sensor *imu, uint8_t reg, uint8_t data) {
    if (imu->protocol == IMU_PROTOCOL_SPI) {
        uint8_t buf[2];
        buf[0] = reg & WRITE_MASK;
        buf[1] = data;
        gpio_put(imu->comm.spi.cs_gpio, 0);
        spi_write_blocking(imu->comm.spi.instance, buf, 2);
        gpio_put(imu->comm.spi.cs_gpio, 1);
    } else {
        uint8_t buf[2] = {reg, data};
        i2c_write_blocking(imu->comm.i2c.instance, imu->comm.i2c.address, buf, 2, false);
    }
}

static uint8_t read_register(struct imu_sensor *imu, uint8_t reg) {
    uint8_t buf[1];
    if (imu->protocol == IMU_PROTOCOL_SPI) {
        uint8_t reg_addr = reg | READ_MASK;
        gpio_put(imu->comm.spi.cs_gpio, 0);
        spi_write_blocking(imu->comm.spi.instance, &reg_addr, 1);
        spi_read_blocking(imu->comm.spi.instance, 0, buf, 1);
        gpio_put(imu->comm.spi.cs_gpio, 1);
    } else {
        i2c_write_blocking(imu->comm.i2c.instance, imu->comm.i2c.address, &reg, 1, true);
        i2c_read_blocking(imu->comm.i2c.instance, imu->comm.i2c.address, buf, 1, false);
    }
    return buf[0];
}

static void read_registers(struct imu_sensor *imu, uint8_t reg, uint8_t *buf, size_t len) {
    if (imu->protocol == IMU_PROTOCOL_SPI) {
        uint8_t reg_addr = reg | READ_MASK;
        gpio_put(imu->comm.spi.cs_gpio, 0);
        spi_write_blocking(imu->comm.spi.instance, &reg_addr, 1);
        spi_read_blocking(imu->comm.spi.instance, 0, buf, len);
        gpio_put(imu->comm.spi.cs_gpio, 1);
    } else {
        i2c_write_blocking(imu->comm.i2c.instance, imu->comm.i2c.address, &reg, 1, true);
        i2c_read_blocking(imu->comm.i2c.instance, imu->comm.i2c.address, buf, len, false);
    }
}

void lsm6dso_init(struct imu_sensor *imu) {
    if (imu->protocol == IMU_PROTOCOL_SPI) {
        spi_init(imu->comm.spi.instance, 1000000);
        spi_set_format(imu->comm.spi.instance, 8, SPI_CPOL_1, SPI_CPHA_1, SPI_MSB_FIRST);
        gpio_set_function(imu->comm.spi.sck_gpio, GPIO_FUNC_SPI);
        gpio_set_function(imu->comm.spi.mosi_gpio, GPIO_FUNC_SPI);
        gpio_set_function(imu->comm.spi.miso_gpio, GPIO_FUNC_SPI);

        gpio_init(imu->comm.spi.cs_gpio);
        gpio_set_dir(imu->comm.spi.cs_gpio, GPIO_OUT);
        gpio_put(imu->comm.spi.cs_gpio, 1);
    } else {
        i2c_init(imu->comm.i2c.instance, 1000000);
        gpio_set_function(imu->comm.i2c.sda_gpio, GPIO_FUNC_I2C);
        gpio_set_function(imu->comm.i2c.scl_gpio, GPIO_FUNC_I2C);
        gpio_pull_up(imu->comm.i2c.sda_gpio);
        gpio_pull_up(imu->comm.i2c.scl_gpio);
    }

    sleep_ms(10);

    printf("[LSM6DSO] Resetting...\n");
    write_register(imu, CTRL3_C, 0x01);
    sleep_ms(10);

    imu->available = lsm6dso_check_availability(imu);
    if (!imu->available) {
        return;
    }

    if (imu->protocol == IMU_PROTOCOL_SPI) {
        write_register(imu, CTRL4_C, 0x04); // Disable I2C
    }

    write_register(imu, CTRL3_C, 0x44);
    write_register(imu, CTRL1_XL, 0x8C); // 1.66kHz ODR, ±8g
    write_register(imu, CTRL2_G, 0x88);  // 1.66kHz ODR, 1000dps

    // Set scale factors based on config
    // ±8g (FS_XL=11): 0.244 mg/LSB → 1g = 4096 LSB
    // 1000dps (FS_G=10): 35 mdps/LSB → 1 dps = 28.57 LSB
    imu->accel_lsb_per_g = 4096.0f;
    imu->gyro_lsb_per_dps = 28.57f;
}

bool lsm6dso_check_availability(struct imu_sensor *imu) {
    uint8_t id = 0;
    for (int i = 0; i < 5; i++) {
        id = read_register(imu, WHO_AM_I);
        if (id == 0x6C) {
            return true;
        }
        sleep_ms(10);
    }
    return false;
}

void lsm6dso_read_raw(struct imu_sensor *imu, int16_t raw[6]) {
    uint8_t buffer[12];
    read_registers(imu, OUTX_L_G, buffer, 12);

    raw[3] = (int16_t)(buffer[1] << 8 | buffer[0]);   // gx
    raw[4] = (int16_t)(buffer[3] << 8 | buffer[2]);   // gy
    raw[5] = (int16_t)(buffer[5] << 8 | buffer[4]);   // gz
    raw[0] = (int16_t)(buffer[7] << 8 | buffer[6]);   // ax
    raw[1] = (int16_t)(buffer[9] << 8 | buffer[8]);   // ay
    raw[2] = (int16_t)(buffer[11] << 8 | buffer[10]); // az
}

int16_t lsm6dso_read_temperature(struct imu_sensor *imu) {
    uint8_t buffer[2];
    read_registers(imu, OUT_TEMP_L, buffer, 2); // Reads both OUT_TEMP_L & OUT_TEMP_H
    return (int16_t)(buffer[1] << 8 | buffer[0]);
}

float lsm6dso_temperature_celsius(struct imu_sensor *imu) {
    int16_t raw_temperature = lsm6dso_read_temperature(imu);
    return 25.0f + (float)raw_temperature / 256.0f;
}