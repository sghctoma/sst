cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(sufni-suspension-telemetry)

set(PICO_BOARD pico_w)

set(CMAKE_C_STANDARD 11)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

pico_sdk_init()

add_subdirectory(../lib/no-OS-FatFS-SD-SPI-RPi-Pico/FatFs_SPI lib/no-OS-FatFS-SD-SPI-RPi-Pico/FatFs_SPI)
add_subdirectory(../lib/pico-as5600 lib/pico-as5600)
add_subdirectory(../lib/pico-ssd1306-spi lib/pico-ssd1306-spi)

add_executable(sufni-suspension-telemetry
    sst.c
    pushbutton.c
    hw_config.c
    msc_disk.c
    sst_usb_descriptors.c
)

target_include_directories(sufni-suspension-telemetry
    PUBLIC
        ${CMAKE_CURRENT_LIST_DIR}/include/
)

target_link_libraries(sufni-suspension-telemetry
    pico_stdlib
    pico_multicore
    pico_cyw43_arch_none
    tinyusb_board
    tinyusb_device
    hardware_i2c
    FatFs_SPI
    as5600
    ssd1306_spi
)

pico_add_extra_outputs(sufni-suspension-telemetry)

