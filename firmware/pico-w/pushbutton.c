#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "hardware/timer.h"
#include "pico/stdlib.h"
#include "hardware/gpio.h"

#include "pushbutton.h"

static struct button *buttons[28] = { NULL };

static int64_t longpress_callback(alarm_id_t id, void *user_data) {
    struct button *btn = user_data;
    bool state = gpio_get(btn->gpio);
    if (state == btn->state) {
        btn->alarm = -1;
        if (btn->onlongpress != NULL) {
            btn->onlongpress(btn->user_data);
        }
    }
    return 0;
}

static int64_t debounce_callback(alarm_id_t id, void *user_data) {
    struct button *btn = user_data;
    bool state = gpio_get(btn->gpio);
    if (state != btn->state) {
        btn->state = state;
        if (state == false && btn->alarm == -1) { // button press
            btn->alarm = add_alarm_in_us(1000000, longpress_callback, btn, true);
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

static void gpio_callback(uint gpio, uint32_t events) {
    struct button *btn = buttons[gpio];
    if (NULL != btn && btn->enabled) {
        add_alarm_in_us(250, debounce_callback, btn, true);
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
	btn->enabled = true;
    btn->alarm = -1;
    btn->user_data = user_data;
    btn->onpress = onpress;
    btn->onlongpress = onlongpress;
    buttons[gpio] = btn;
}

void disable_button(uint gpio, bool release_only) {
	buttons[gpio]->enabled = false;
	uint32_t mask = GPIO_IRQ_EDGE_RISE | (release_only ? 0 : GPIO_IRQ_EDGE_FALL);
    gpio_set_irq_enabled(gpio, mask, false);
}

void enable_button(uint gpio) {
	buttons[gpio]->enabled = true;
    gpio_set_irq_enabled(gpio, GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, true);
}
