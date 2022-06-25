cmake_minimum_required(VERSION 3.13)

# initialize the SDK based on PICO_SDK_PATH
# note: this must happen before project()
include(pico_sdk_import.cmake)

project(sufni-suspension-telemetry)

set(CMAKE_C_STANDARD 11)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# initialize the Raspberry Pi Pico SDK
pico_sdk_init()

# rest of your project

add_subdirectory(lib/FatFs_SPI build)

add_executable(sufni-suspension-telemetry
	sst.c
    msc_disk.c
    sst_usb_descriptors.c
    hw_config.c
    lib/ssd1306/ssd1306.c
    lib/as5600/as5600.c
)

target_include_directories(sufni-suspension-telemetry
    PUBLIC
        ${CMAKE_CURRENT_LIST_DIR}/include/
        ${CMAKE_CURRENT_LIST_DIR}/lib/ssd1306/
        ${CMAKE_CURRENT_LIST_DIR}/lib/as5600/
)

target_link_libraries(sufni-suspension-telemetry
    pico_stdlib
    pico_multicore
    tinyusb_board
    tinyusb_device
    hardware_i2c
    FatFs_SPI
)

# create map/bin/hex/uf2 file in addition to ELF.
pico_add_extra_outputs(sufni-suspension-telemetry)

