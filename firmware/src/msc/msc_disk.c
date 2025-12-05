/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2019 Ha Thach (tinyusb.org)
 * Copyright (c) 2022 Tamás Szakály (sghctoma)
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 *
 */

#include "tusb.h"

#include "hw_config.h"
#include "sd_card.h"

#if CFG_TUD_MSC

static const uint16_t BLOCK_SIZE = 512; // hardcoded in FatFs_SPI/sd_driver/sd_card.c@232
static sd_card_t *sd = NULL;
static bool ejected = false;

// Invoked when received SCSI_CMD_INQUIRY
// Application fill vendor id, product id and revision with string up to 8, 16, 4 characters respectively
void tud_msc_inquiry_cb(uint8_t lun, uint8_t vendor_id[8], uint8_t product_id[16], uint8_t product_rev[4]) {
    (void)lun;

    const char vid[] = "sghctoma";
    const char pid[] = "Sufni Suspension";
    const char rev[] = "0.1";

    memcpy(vendor_id, vid, strlen(vid));
    memcpy(product_id, pid, strlen(pid));
    memcpy(product_rev, rev, strlen(rev));
}

// Invoked when received Test Unit Ready command.
// return true allowing host to read/write this LUN e.g SD card inserted
bool tud_msc_test_unit_ready_cb(uint8_t lun) {
    (void)lun;

    if (ejected) {
        tud_msc_set_sense(lun, SCSI_SENSE_NOT_READY, 0x3a, 0x00);
        return false;
    }

    return true;
}

// Invoked when received SCSI_CMD_READ_CAPACITY_10 and SCSI_CMD_READ_FORMAT_CAPACITY to determine the disk size
// Application update block count and block size
void tud_msc_capacity_cb(uint8_t lun, uint32_t *block_count, uint16_t *block_size) {
    (void)lun;

    if (sd == NULL) {
        sd_init_driver();
        sd = sd_get_by_num(0);
        sd->init(sd);
    }
    *block_count = sd->get_num_sectors(sd);
    *block_size = BLOCK_SIZE;
}

// Invoked when received Start Stop Unit command
// - Start = 0 : stopped power mode, if load_eject = 1 : unload disk storage
// - Start = 1 : active mode, if load_eject = 1 : load disk storage
bool tud_msc_start_stop_cb(uint8_t lun, uint8_t power_condition, bool start, bool load_eject) {
    (void)lun;
    (void)power_condition;

    if (load_eject) {
        if (start) {
            if (sd == NULL) {
                sd_init_driver();
                sd = sd_get_by_num(0);
                return sd->init(sd);
            } else {
                return true;
            }
        } else {
            // unload disk storage
            // XXX: not sure if this needs more handling...
            ejected = true;
        }
    }

    return true;
}

// Invoked when received SCSI READ10 command
// - Address = lba * BLOCK_SIZE + offset
//   - offset is only needed if CFG_TUD_MSC_EP_BUFSIZE is smaller than BLOCK_SIZE.
//
// - Application fill the buffer (up to bufsize) with address contents and return number of read byte. If
//   - read < bufsize : These bytes are transferred first and callback invoked again for remaining data.
//
//   - read == 0      : Indicate application is not ready yet e.g disk I/O busy.
//                      Callback invoked again with the same parameters later on.
//
//   - read < 0       : Indicate application error e.g invalid address. This request will be STALLed
//                      and return failed status in command status wrapper phase.
int32_t tud_msc_read10_cb(uint8_t lun, uint32_t lba, uint32_t offset, void *buffer, uint32_t bufsize) {
    (void)lun;
    (void)offset; // ignored because CFG_TUD_MSC_EP_BUFSIZE == BLOCK_SIZE

    uint32_t block_count = bufsize / BLOCK_SIZE;
    int status = sd->read_blocks(sd, buffer, lba, block_count);
    if (status != SD_BLOCK_DEVICE_ERROR_NONE) {
        return status;
    }

    // XXX: Not sure if this is necessary. Can bufsize not be a multiple of block size?
    uint32_t remainder = bufsize % BLOCK_SIZE;
    if (remainder != 0) {
        uint8_t block[BLOCK_SIZE];
        status = sd->read_blocks(sd, block, lba + block_count, 1);
        if (status != SD_BLOCK_DEVICE_ERROR_NONE) {
            return status;
        } else {
            memcpy(buffer + (bufsize - remainder), block, remainder);
        }
    }

    return bufsize;
}

// Invoked to check if device is writable as part of SCSI WRITE10
bool tud_msc_is_writable_cb(uint8_t lun) { return true; }

// Invoked when received SCSI WRITE10 command
// - Address = lba * BLOCK_SIZE + offset
//   - offset is only needed if CFG_TUD_MSC_EP_BUFSIZE is smaller than BLOCK_SIZE.
//
// - Application write data from buffer to address contents (up to bufsize) and return number of written byte. If
//   - write < bufsize : callback invoked again with remaining data later on.
//
//   - write == 0      : Indicate application is not ready yet e.g disk I/O busy.
//                       Callback invoked again with the same parameters later on.
//
//   - write < 0       : Indicate application error e.g invalid address. This request will be STALLed
//                       and return failed status in command status wrapper phase.
int32_t tud_msc_write10_cb(uint8_t lun, uint32_t lba, uint32_t offset, uint8_t *buffer, uint32_t bufsize) {
    (void)lun;
    (void)offset; // ignored because CFG_TUD_MSC_EP_BUFSIZE == BLOCK_SIZE

    uint32_t block_count = bufsize / BLOCK_SIZE;
    int status = sd->write_blocks(sd, buffer, lba, block_count);
    if (status != SD_BLOCK_DEVICE_ERROR_NONE) {
        return status;
    }

    return bufsize;
}

// Callback invoked when received an SCSI command not in built-in list below
// - READ_CAPACITY10, READ_FORMAT_CAPACITY, INQUIRY, MODE_SENSE6, REQUEST_SENSE
// - READ10 and WRITE10 has their own callbacks
int32_t tud_msc_scsi_cb(uint8_t lun, uint8_t const scsi_cmd[16], void *buffer, uint16_t bufsize) {
    // read10 & write10 has their own callback and MUST not be handled here

    void const *response = NULL;
    int32_t resplen = 0;

    // most scsi handled is input
    bool in_xfer = true;

    switch (scsi_cmd[0]) {
        case SCSI_CMD_PREVENT_ALLOW_MEDIUM_REMOVAL:
            // Host is about to read/write etc ... better not to disconnect disk
            resplen = 0;
            break;

        default:
            // Set Sense = Invalid Command Operation
            tud_msc_set_sense(lun, SCSI_SENSE_ILLEGAL_REQUEST, 0x20, 0x00);

            // negative means error -> tinyusb could stall and/or response with failed status
            resplen = -1;
            break;
    }

    // return resplen must not larger than bufsize
    if (resplen > bufsize)
        resplen = bufsize;

    if (response && (resplen > 0)) {
        if (in_xfer) {
            memcpy(buffer, response, resplen);
        } else {
            // SCSI output
        }
    }

    return resplen;
}

#endif
