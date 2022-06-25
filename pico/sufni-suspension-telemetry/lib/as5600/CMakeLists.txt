add_library(as5600 INTERFACE)
target_sources(as5600 INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/as5600.c
)
target_include_directories(as5600 INTERFACE
    include
)
target_link_libraries(as5600 INTERFACE
    pico_stdlib
    hardware_i2c
)

