#ifndef LWGPS_OPTS_H
#define LWGPS_OPTS_H

// Use double for lat/lon precision
#define LWGPS_CFG_DOUBLE 1

// Enable statement completion callback
#define LWGPS_CFG_STATUS 1

// Disable standard NMEA (we use PQTM instead)
#define LWGPS_CFG_STATEMENT_GPGGA 0
#define LWGPS_CFG_STATEMENT_GPGSA 0
#define LWGPS_CFG_STATEMENT_GPGSV 0
#define LWGPS_CFG_STATEMENT_GPRMC 0

// Enable Quectel proprietary messages
// This is LC76G specific, but that is the only currently supported module
#define LWGPS_CFG_STATEMENT_PQTMPVT 1
#define LWGPS_CFG_STATEMENT_PQTMEPE 1

// Enable Quectel command acknowledgment parsing
#define LWGPS_CFG_STATEMENT_PAIR_ACK            1
#define LWGPS_CFG_STATEMENT_PQTM_CFGMSGRATE_ACK 1
#define LWGPS_CFG_STATEMENT_PQTM_SAVEPAR_ACK    1

// Enable CRC validation
#define LWGPS_CFG_CRC 1

#endif
