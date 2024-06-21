#include <stdio.h>
#include "tcpserver.h"
#include "lwip/tcp.h"
#include "lwip/tcpbase.h"
#include "lwip/apps/mdns.h"
#include "lwip/netif.h"
#include "pico/time.h"
#include "pico/unique_id.h"
#include "ff.h"

#include "../util/list.h"

#define READ_BUF_LEN (10 * 1024)
#define TCP_PORT 1557
#define POLL_TIME_S 5

#define STATUS_INITIALIZED      1
#define STATUS_CLIENT_CONNECTED 2
#define STATUS_FILE_REQUESTED   3
#define STATUS_HEADER_OK        4
#define STATUS_FILE_SENT        5
#define STATUS_FINISHED         6

static pico_unique_board_id_t board_id;

// ----------------------------------------------------------------------------
// TCP callback functions

static err_t tcp_server_result(void *arg, int status);

static err_t tcp_server_sent(void *arg, struct tcp_pcb *tpcb, u16_t len) {
    struct tcpserver *server = (struct tcpserver*)arg;
    server->sent_len += len;

    return ERR_OK;
}

err_t tcp_server_recv(void *arg, struct tcp_pcb *tpcb, struct pbuf *p, err_t err) {
    struct tcpserver *server = (struct tcpserver*)arg;
    if (NULL == p) {
        return tcp_server_result(arg, -1);
    }

    cyw43_arch_lwip_check();
    if (p->tot_len > 0) {
        int s;
        pbuf_copy_partial(p, &s, 4, 0);
        tcp_recved(tpcb, p->tot_len);
        
        if (s < 0 || s == STATUS_FINISHED) {
            // close the server
            tcp_server_result(arg, s);
        } else if (s == STATUS_FILE_SENT) {
            // close the client connection
            tcp_server_result(arg, s);
        } else if (s == STATUS_FILE_REQUESTED) {
            int id;
            pbuf_copy_partial(p, &id, 4, 4);
            server->requested_file = id;
            server->status = s;
        } else {
            server->status = s;
        }
    }
    pbuf_free(p);

    return ERR_OK;
}

static err_t tcp_server_poll(void *arg, struct tcp_pcb *tpcb) {
    return ERR_OK;
}

static void tcp_server_err(void *arg, err_t err) {
    if (err != ERR_ABRT) {
        tcp_server_result(arg, err);
    }
}

static err_t tcp_server_accept(void *arg, struct tcp_pcb *client_pcb, err_t err) {
    struct tcpserver *server = (struct tcpserver*)arg;
    if (err != ERR_OK || client_pcb == NULL) {
        tcp_server_result(arg, err);
        return ERR_VAL;
    }

    server->client_pcb = client_pcb;
    tcp_arg(client_pcb, server);
    tcp_sent(client_pcb, tcp_server_sent);
    tcp_recv(client_pcb, tcp_server_recv);
    tcp_poll(client_pcb, tcp_server_poll, POLL_TIME_S * 2);
    tcp_err(client_pcb, tcp_server_err);

    server->status = STATUS_CLIENT_CONNECTED;
    return ERR_OK;
}

// ----------------------------------------------------------------------------
// TCP helper functions

static bool tcp_server_open(void *arg) {
    struct tcpserver *server = (struct tcpserver*)arg;
    struct tcp_pcb *pcb = tcp_new_ip_type(IPADDR_TYPE_ANY);
    if (!pcb) {
        return false;
    }

    err_t err = tcp_bind(pcb, NULL, TCP_PORT);
    if (err) {
        return false;
    }

    server->server_pcb = tcp_listen_with_backlog(pcb, 1);
    if (!server->server_pcb) {
        if (pcb) {
            tcp_close(pcb);
        }
        return false;
    }

    tcp_arg(server->server_pcb, server);
    tcp_accept(server->server_pcb, tcp_server_accept);

    return true;
}

static err_t tcp_server_close(void *arg) {
    struct tcpserver *server = (struct tcpserver*)arg;
    err_t err = ERR_OK;
    if (server->client_pcb != NULL) {
        tcp_arg(server->client_pcb, NULL);
        tcp_poll(server->client_pcb, NULL, 0);
        tcp_sent(server->client_pcb, NULL);
        tcp_recv(server->client_pcb, NULL);
        tcp_err(server->client_pcb, NULL);
        err = tcp_close(server->client_pcb);
        if (err != ERR_OK) {
            tcp_abort(server->client_pcb);
            err = ERR_ABRT;
        }
        server->client_pcb = NULL;
    }
    
    if (server->status == STATUS_FINISHED && server->server_pcb) {
        tcp_arg(server->server_pcb, NULL);
        tcp_close(server->server_pcb);
        server->server_pcb = NULL;
    }
    
    return err;
}

static err_t tcp_server_result(void *arg, int status) {
    struct tcpserver *server = (struct tcpserver*)arg;
    server->status = status;
    return tcp_server_close(arg);
}

// ----------------------------------------------------------------------------
// SST file handler

static bool process_sst_file_request(struct tcpserver *server) {
    server->sent_len = 0;

    // get size of requested file
    char filename[10];
    sprintf(filename, "%05d.SST", server->requested_file);
    FILINFO finfo;
    FRESULT fr = f_stat(filename, &finfo);
    if (fr != FR_OK) {
        return false;
    }

    // calculate total size
    server->data_len = sizeof(FSIZE_t) + finfo.fsize;
    
    // send size
    cyw43_arch_lwip_begin();
    tcp_write(server->client_pcb, &finfo.fsize, sizeof(FSIZE_t), TCP_WRITE_FLAG_COPY);
    tcp_output(server->client_pcb);
    cyw43_arch_lwip_end();

    // wait for client to accept and validate size
    while (server->status != STATUS_HEADER_OK) {
        if (server->status < 0) {
            return false;
        }
        sleep_ms(1);
    }

    // open the file for reading
    FIL f;
    fr = f_open(&f, filename, FA_OPEN_EXISTING | FA_READ);
    if (!(fr == FR_OK || fr == FR_EXIST)) {
        return false;
    }

    // send the file
    static uint8_t buffer[READ_BUF_LEN];
    uint br = READ_BUF_LEN;
    FSIZE_t total_read = 0;
    while (br == READ_BUF_LEN) {
        fr = f_read(&f, buffer, READ_BUF_LEN, &br);
        if (fr != FR_OK) {
            tcp_server_result(server, -1);
            return false;
        }
        total_read += br;

        // XXX Upload is painfully slow if I don't nudge the LED PIN here.
        //     Must be some timing issue with LwIP that I am not ready to 
        //     debug... A single call to cyw43_arch_gpio_put would be enough
        //     to speed things up significantly (5-6x speedup), but might as
        //     well blink to show progress.
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);

        while (tcp_sndbuf(server->client_pcb) < br) {
            // XXX Lots of errors in Release mode if we have a too short sleep
            //     here.
            sleep_ms(20);
        }
    
        cyw43_arch_lwip_begin();
        tcp_write(server->client_pcb, buffer, br, TCP_WRITE_FLAG_COPY | (total_read < finfo.fsize ? TCP_WRITE_FLAG_MORE : 0));
        cyw43_arch_lwip_end();

        if (total_read == finfo.fsize && NULL != server->client_pcb) {
            cyw43_arch_lwip_begin();
            tcp_output(server->client_pcb);
            cyw43_arch_lwip_end();
            break;
        }
    }

    f_close(&f);

    // wait for client to acknowledge file was received
    while (server->status != STATUS_FILE_SENT) {
        if (server->status < 0) {
            return false;
        }
        sleep_ms(1);
    }

    return true;
}

// ----------------------------------------------------------------------------
// Directory info handler

static FSIZE_t get_size(const char *path) {
    FILINFO finfo;
    FRESULT fr = f_stat(path, &finfo);
    if (fr != FR_OK) {
        return 0;
    }

    return finfo.fsize;
}

static time_t get_timestamp(const char *path) {
    FRESULT fr;
    FIL f;

    fr = f_open(&f, path, FA_OPEN_EXISTING | FA_READ);
    if (!(fr == FR_OK || fr == FR_EXIST)) {
        return 0;
    }

    fr = f_lseek(&f, 8);
    if (fr != FR_OK) {
        return 0;
    }

    time_t timestamp;
    uint br;
    fr = f_read(&f, &timestamp, 8, &br);
    if (fr != FR_OK || br != 8) {
        return 0;
    }

    f_close(&f);

    return timestamp;
}

static bool process_dirinfo_request(struct tcpserver *server) {
    server->sent_len = 0;

    // get a list of all .SST files in the root directory
    FRESULT fr;
    DIR dj;
    FILINFO fno;
    uint all = 0;

    struct list *to_import = list_create();
    fr = f_findfirst(&dj, &fno, "", "?????.SST");
    while (fr == FR_OK && fno.fname[0]) {
        ++all;
        list_push(to_import, fno.fname);
        fr = f_findnext(&dj, &fno);
    }
    f_closedir(&dj);

    // calculate total size
    static FSIZE_t file_data_size = ((FILENAME_LENGTH - 1) + sizeof(FSIZE_t) + sizeof(time_t));
    FSIZE_t dirinfo_size =
        PICO_UNIQUE_BOARD_ID_SIZE_BYTES + // board identifier
        sizeof(uint16_t) +                // sample rate
        all * file_data_size;             // file info (name, size, timestamp) for all SSTs
    server->data_len =
        sizeof(FSIZE_t) +                 // directory info size
        dirinfo_size;                     // directory info

    // send size
    cyw43_arch_lwip_begin();
    tcp_write(server->client_pcb, &dirinfo_size,  sizeof(FSIZE_t), TCP_WRITE_FLAG_COPY); 
    tcp_output(server->client_pcb);
    cyw43_arch_lwip_end();
   
    // wait for client to accept and validate size
    while (server->status != STATUS_HEADER_OK) {
        if (server->status < 0) {
            return false;
        }
        sleep_ms(1);
    }

    // send board id and sample rate
    cyw43_arch_lwip_begin();
    static uint16_t SAMPLE_RATE = 1000;
    tcp_write(server->client_pcb, board_id.id, PICO_UNIQUE_BOARD_ID_SIZE_BYTES, TCP_WRITE_FLAG_COPY | TCP_WRITE_FLAG_MORE);
    tcp_write(server->client_pcb, &SAMPLE_RATE, sizeof(uint16_t), TCP_WRITE_FLAG_COPY | TCP_WRITE_FLAG_MORE);
    cyw43_arch_lwip_end();

    // send metadata of each SST file
    struct node *n = to_import->head;
    while (n != NULL) {
        // These will be dummy values if reading them fails, so that the combined size
        // we sent earlier would be correct.
        time_t timestamp = get_timestamp(n->data);
        FSIZE_t size = get_size(n->data);

        // XXX Upload is painfully slow here if I don't nudge the LED PIN here.
        //     Must be some timing issue with LwIP that I am not ready to 
        //     debug... A single call to cyw43_arch_gpio_put would be enough
        //     to speed things up significantly (5-6x speedup), but might as
        //     well blink to show progress.
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);

        while (tcp_sndbuf(server->client_pcb) < file_data_size) {
            // XXX Lots of errors in Release mode if we have a too short sleep
            //     here.
            sleep_ms(20);
        }

        cyw43_arch_lwip_begin();
        tcp_write(server->client_pcb, n->data, FILENAME_LENGTH - 1, TCP_WRITE_FLAG_COPY | TCP_WRITE_FLAG_MORE);
        tcp_write(server->client_pcb, &size, sizeof(FSIZE_t), TCP_WRITE_FLAG_COPY | TCP_WRITE_FLAG_MORE);
        tcp_write(server->client_pcb, &timestamp, sizeof(time_t), TCP_WRITE_FLAG_COPY | (n->next != NULL ? TCP_WRITE_FLAG_MORE : 0));

        if (n->next == NULL) {
            tcp_output(server->client_pcb);
        }
        cyw43_arch_lwip_end();

        n = n->next;
    }
    list_delete(to_import);

    // wait for client to acknowledge file was received
    while (server->status != STATUS_FILE_SENT) {
        if (server->status < 0) {
            return false;
        }
        sleep_ms(1);
    }

    return true;
}

// ----------------------------------------------------------------------------
// MDNS functions
static void mdns_srv_txt(struct mdns_service *service, void *txt_userdata) {
    err_t res;
    LWIP_UNUSED_ARG(txt_userdata);
    
    res = mdns_resp_add_service_txtitem(service, NULL, 0);
    LWIP_ERROR("mdns add service txt failed\n", (res == ERR_OK), return);
}

// ----------------------------------------------------------------------------
// "Public" functions

bool tcpserver_init(struct tcpserver *server) {
    pico_get_unique_board_id(&board_id);

    if (server->mdns_initialized) {
        mdns_resp_restart(netif_default);
    } else {
        mdns_resp_init();
        server->mdns_initialized = true;
    }
    mdns_resp_add_netif(netif_default, "sufni_telemetry_daq");
    server->mdns_slot = mdns_resp_add_service(netif_default, "sufnidaq", "_gosst",
        DNSSD_PROTO_TCP, 1557, mdns_srv_txt, NULL);
    mdns_resp_announce(netif_default);

    if (!tcp_server_open(server)) {
        tcp_server_result(server, -1);
        return false;
    }

    server->status = STATUS_INITIALIZED;
    
    return true;
}

void tcpserver_teardown(struct tcpserver *server) {
    tcp_server_close(server);
    mdns_resp_del_service (netif_default, server->mdns_slot);
    mdns_resp_remove_netif (netif_default);
}

bool tcpserver_process(struct tcpserver *server) {
    if (server->requested_file == 0) {
        return process_dirinfo_request(server);
    } else if (process_sst_file_request(server)) {
        TCHAR path_old[10];
        TCHAR path_new[19];
        sprintf(path_old, "%05d.SST", server->requested_file);
        sprintf(path_new, "uploaded/%s", path_old);
        f_rename(path_old, path_new);
        return true;
    }

    return false;
}

void inline tcpserver_finish(struct tcpserver *server) {
    server->status = STATUS_FINISHED;
}

bool inline tcpserver_finished(struct tcpserver *server) {
    return server->status == STATUS_FINISHED;    
}

bool inline tcpserver_requested(struct tcpserver *server) {
    return server->status == STATUS_FILE_REQUESTED;    
}
