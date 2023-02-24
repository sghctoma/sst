#include "include/lwipopts.h"
#include "lwip/ip_addr.h"
#include "lwip/tcpbase.h"
#include "pico/unique_id.h"
#include "pico/cyw43_arch.h"
#include "lwip/dns.h"
#include "lwip/pbuf.h"
#include "lwip/tcp.h"

#include "hw_config.h"
#include "pico/time.h"
#include "tcpclient.h"
#include "config.h"

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

static err_t tcp_result(void *arg, int8_t status) {
    struct connection *conn = (struct connection *)arg;
    conn->status = status;
    return tcp_client_close(arg);
}

static err_t tcp_client_sent(void *arg, struct tcp_pcb *tpcb, u16_t len) {
    struct connection *conn = (struct connection *)arg;
    conn->sent_len += len;

    if (conn->sent_len == conn->data_len) {
        conn->status = STATUS_DATA_SENT;
    }

    return ERR_OK;
}

static err_t tcp_client_connected(void *arg, struct tcp_pcb *tpcb, err_t err) {
    if (err != ERR_OK) {
        return tcp_result(arg, err);
    }
    struct connection *conn = (struct connection *)arg;
    conn->status = STATUS_CONNECTED;
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

err_t tcp_client_recv(void *arg, struct tcp_pcb *tpcb, struct pbuf *p, err_t err) {
    struct connection *conn= (struct connection *)arg;
    if (NULL == p) {
        return tcp_result(arg, -1);
    }

    cyw43_arch_lwip_check();
    if (p->tot_len > 0) {
        int8_t s = *(int8_t *)p->payload;
        tcp_recved(tpcb, p->tot_len);
        
        if (s < 0 || s == STATUS_SUCCESS) {
            tcp_result(arg, s);
        } else {
            conn->status = s;
        }        
    }
    pbuf_free(p);

    return ERR_OK;
}

static void dns_found(const char *hostname, const ip_addr_t *ipaddr, void *arg) {
    struct connection *conn = (struct connection *)arg;
    if (ipaddr != NULL) {
        conn->remote_addr = *ipaddr;
        conn->status = STATUS_DNS_FOUND;
    }
}

static bool tcp_client_open(void *arg) {
    struct connection *conn = (struct connection *)arg;
    
    cyw43_arch_lwip_begin();
    err_t err = dns_gethostbyname(config.sst_server , &conn->remote_addr, dns_found, conn);
    cyw43_arch_lwip_end();
  
    if (err == ERR_OK) { // domain name was in cache
        conn->status = STATUS_DNS_FOUND;
    }
    while (conn->status != STATUS_DNS_FOUND) {
        if (conn->status < 0) {
            free(conn);
            return false;
        }
        cyw43_arch_poll();
        sleep_ms(1);
    }
    
    conn->pcb = tcp_new_ip_type(IP_GET_TYPE(&conn->remote_addr));
    if (conn->pcb == NULL) {
        return false;
    }
    
    tcp_arg(conn->pcb, conn);
    tcp_poll(conn->pcb, tcp_client_poll, POLL_TIME_S * 2);
    tcp_sent(conn->pcb, tcp_client_sent);
    tcp_recv(conn->pcb, tcp_client_recv);
    tcp_err(conn->pcb, tcp_client_err);

    cyw43_arch_lwip_begin();
    err = tcp_connect(conn->pcb, &conn->remote_addr, config.sst_server_port, tcp_client_connected);
    cyw43_arch_lwip_end();

    return err == ERR_OK;
}

static struct connection * tcp_client_init() {
    struct connection *conn = malloc(sizeof(struct connection));
    if (conn == NULL) {
        return NULL;
    }

    conn->status = STATUS_INIT;
    conn->sent_len = 0;

    return conn;
}

bool send_file(const char *filename) {
    pico_unique_board_id_t board_id;
    pico_get_unique_board_id(&board_id);

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

    while (conn->status != STATUS_CONNECTED) {
        if (conn->status < 0) {
            return false;
        }
        cyw43_arch_poll();
        sleep_ms(1);
    }

    conn->data_len =
        PICO_UNIQUE_BOARD_ID_SIZE_BYTES +
        sizeof(FSIZE_t) +
        (FILENAME_LENGTH - 1) + // we don't send the terminating null byte
        finfo.fsize;

    //cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);
    cyw43_arch_lwip_begin();
    tcp_write(conn->pcb, board_id.id, PICO_UNIQUE_BOARD_ID_SIZE_BYTES, TCP_WRITE_FLAG_COPY | TCP_WRITE_FLAG_MORE);
    tcp_write(conn->pcb, &finfo.fsize, sizeof(FSIZE_t), TCP_WRITE_FLAG_COPY | TCP_WRITE_FLAG_MORE);
    tcp_write(conn->pcb, filename, FILENAME_LENGTH - 1, TCP_WRITE_FLAG_COPY); 
    tcp_output(conn->pcb);
    cyw43_arch_lwip_end();

    while (conn->status != STATUS_HEADER_OK) {
        if (conn->status < 0) {
            return false;
        }
        cyw43_arch_poll();
        sleep_ms(1);
    }

    uint8_t buffer[READ_BUF_LEN];
    uint br = READ_BUF_LEN;
    FSIZE_t total_read = 0;
    while (br == READ_BUF_LEN) {
        fr = f_read(&f, buffer, READ_BUF_LEN, &br);
        if (fr != FR_OK) {
            tcp_result(conn, -1);
            return false;
        }
        total_read += br;

        // XXX Upload is painfully slow here if I don't nudge the LED PIN here.
        //     Must be some timing issue with LwIP that I am not ready to 
        //     debug... A single call to cyw43_arch_gpio_put would be enough
        //     to speed things up significantly (5-6x speedup), but might as
        //     well blink to show progress.
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);
        sleep_ms(10);
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);

        while (tcp_sndbuf(conn->pcb) < br) {
            cyw43_arch_poll();
            sleep_ms(1);
        }
        
        cyw43_arch_lwip_begin();
        tcp_write(conn->pcb, buffer, br, TCP_WRITE_FLAG_COPY | (total_read < finfo.fsize ? TCP_WRITE_FLAG_MORE : 0));
        cyw43_arch_lwip_end();

        if (total_read == finfo.fsize) {
            cyw43_arch_lwip_begin();
            tcp_output(conn->pcb);
            cyw43_arch_lwip_end();
            break;
        }
    }

    f_close(&f);

    while (conn->status != STATUS_SUCCESS) {
        if (conn->status < 0) {
            return false;
        }
        cyw43_arch_poll();
        sleep_ms(1);
    }

    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);
    free(conn);

    return true;
}
