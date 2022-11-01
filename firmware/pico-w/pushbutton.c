#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "hardware/timer.h"
#include "pico/stdlib.h"
#include "hardware/gpio.h"
#include "pico/time.h"

struct button {
    uint gpio;
    bool state;
    alarm_id_t alarm;
    void *user_data;
    void (*onpress)(void *user_data);
    void (*onlongpress)(void *user_data);
};

struct button *buttons[28] = { NULL };

int64_t longpress_callback(alarm_id_t id, void *user_data) {
    struct button *btn = user_data;
    bool state = gpio_get(btn->gpio);
    if (state == btn->state) {
        btn->alarm = -1;
        btn->onlongpress(btn->user_data);
    }
    return 0;
}

int64_t debounce_callback(alarm_id_t id, void *user_data) {
    struct button *btn = user_data;
    bool state = gpio_get(btn->gpio);
    if (state != btn->state) {
        btn->state = state;
        if (state == false && btn->alarm == -1) { // button press
            if (btn->onlongpress != NULL) {
                btn->alarm = add_alarm_in_us(1000000, longpress_callback, btn, false);
            }
        } else if (btn->alarm != -1) { // button release
            cancel_alarm(btn->alarm);
            btn->alarm = -1;
            if (btn->onpress != NULL) {
                btn->onpress(btn->user_data);
            }
        }
    }
    return 0;
}

void gpio_callback(uint gpio, uint32_t events) {
    struct button *btn = buttons[gpio];
    if (NULL != btn) {
        add_alarm_in_us(200, debounce_callback, btn, true);
    }
}

void create_button(uint gpio, void *user_data, void (*onpress)(void *), void (*onlongpress)(void *)) {
    gpio_init(gpio);
    gpio_pull_up(gpio);
    gpio_set_irq_enabled_with_callback(gpio, GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, true, &gpio_callback);

    struct button *btn = malloc(sizeof(struct button)); // NOTE: we are never freeing them, but
                                                        // buttons are assumed to live forever.
    btn->gpio = gpio;
    btn->state = gpio_get(gpio); // should be true, since we pulled the GPIO up
    btn->alarm = -1;
    btn->user_data = user_data;
    btn->onpress = onpress;
    btn->onlongpress = onlongpress;
    buttons[gpio] = btn;
}

