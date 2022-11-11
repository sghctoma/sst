#include "include/lwipopts.h"
#include "lwip/tcpbase.h"
#include "pico/cyw43_arch.h"
#include "lwip/pbuf.h"
#include "lwip/tcp.h"

#include "hw_config.h"
#include "pico/time.h"
#include "tcpclient.h"

static err_t tcp_client_close(void *arg) {
    struct connection *conn = (struct connection *)arg;
    err_t err = ERR_OK;
    if (conn->pcb != NULL) {
        tcp_arg(conn->pcb, NULL);
        tcp_poll(conn->pcb, NULL, 0);
        tcp_sent(conn->pcb, NULL);
        tcp_recv(conn->pcb, NULL);
        tcp_err(conn->pcb, NULL);
        err = tcp_close(conn->pcb);
        if (err != ERR_OK) {
            tcp_abort(conn->pcb);
            err = ERR_ABRT;
        }
        conn->pcb = NULL;
    }
    return err;
}

static err_t tcp_result(void *arg, int status) {
    struct connection *conn = (struct connection *)arg;
    conn->success = (status == 0);
    conn->done = true;
    return tcp_client_close(arg);
}

static err_t tcp_client_sent(void *arg, struct tcp_pcb *tpcb, u16_t len) {
    struct connection *conn = (struct connection *)arg;
    conn->sent_len += len;

    if (conn->sent_len == conn->data_len) {
        tcp_result(arg, 0);
    }

    return ERR_OK;
}

static err_t tcp_client_connected(void *arg, struct tcp_pcb *tpcb, err_t err) {
    if (err != ERR_OK) {
        return tcp_result(arg, err);
    }
    struct connection *conn = (struct connection *)arg;
    conn->connected = true;
    return ERR_OK;
}

static err_t tcp_client_poll(void *arg, struct tcp_pcb *tpcb) {
    return tcp_result(arg, -1); // no response is an error?
}

static void tcp_client_err(void *arg, err_t err) {
    if (err != ERR_ABRT) {
        tcp_result(arg, err);
    }
}

static bool tcp_client_open(void *arg) {
    struct connection *conn = (struct connection *)arg;
    conn->pcb = tcp_new_ip_type(IP_GET_TYPE(&conn->remote_addr));
    if (conn->pcb == NULL) {
        return false;
    }

    tcp_arg(conn->pcb, conn);
    tcp_poll(conn->pcb, tcp_client_poll, POLL_TIME_S * 2);
    tcp_sent(conn->pcb, tcp_client_sent);
    tcp_err(conn->pcb, tcp_client_err);

    cyw43_arch_lwip_begin();
    err_t err = tcp_connect(conn->pcb, &conn->remote_addr, SERVER_PORT, tcp_client_connected);
    cyw43_arch_lwip_end();

    return err == ERR_OK;
}

static struct connection * tcp_client_init() {
    struct connection *conn = malloc(sizeof(struct connection));
    if (conn == NULL) {
        return NULL;
    }

    conn->connected = false;
    conn->done = false;
    conn->success = false;
    conn->sent_len = 0;
    ipaddr_aton(SERVER_IP, &conn->remote_addr);
    
    return conn;
}

bool send_file(const char *filename) {
    FILINFO finfo;
    FRESULT fr = f_stat(filename, &finfo);
    if (fr != FR_OK) {
        return false;
    }

    FIL f;
    fr = f_open(&f, filename, FA_OPEN_EXISTING | FA_READ);
    if (!(fr == FR_OK || fr == FR_EXIST)) {
        return false;
    }
    
    struct connection *conn = tcp_client_init();
    if (conn == NULL) {
        return false;
    }
    if (!tcp_client_open(conn)) {
        tcp_result(&conn, -1);
        return false;
    }

    while (!conn->connected) {
        cyw43_arch_poll();
        sleep_ms(1);
    }
    conn->data_len = sizeof(FSIZE_t) + FILENAME_LENGTH + finfo.fsize;

    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);

    cyw43_arch_lwip_begin();
    tcp_write(conn->pcb, &finfo.fsize, sizeof(FSIZE_t), TCP_WRITE_FLAG_MORE);
    tcp_write(conn->pcb, filename, FILENAME_LENGTH, 0); 
    tcp_output(conn->pcb);
    cyw43_arch_lwip_end();

    cyw43_arch_poll();
    sleep_ms(1);

    uint8_t buffer[READ_BUF_LEN];
    uint br = READ_BUF_LEN;
    while (br == READ_BUF_LEN) {
        fr = f_read(&f, buffer, READ_BUF_LEN, &br);
        if (fr != FR_OK) {
            tcp_result(conn, -1);
            return false;
        }

        while (tcp_sndbuf(conn->pcb) < br) {
            cyw43_arch_poll();
            sleep_ms(1);
        }
        
        cyw43_arch_lwip_begin();
        tcp_write(conn->pcb, buffer, br, (br == READ_BUF_LEN ? TCP_WRITE_FLAG_MORE : 0));
        tcp_output(conn->pcb);
        cyw43_arch_lwip_end();
    }

    f_close(&f);

    while (!conn->done) {
        cyw43_arch_poll();
        sleep_ms(1);
    }

    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);

    bool ret = conn->success;
    free(conn);
    return ret;
}
