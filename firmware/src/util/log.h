#ifndef _LOG_H
#define _LOG_H

#include <stdio.h>

#ifdef NDEBUG
#define LOG(source, fmt, ...)
#else
#define LOG(source, fmt, ...) printf("[" source "] " fmt, ##__VA_ARGS__)
#endif

#endif // _LOG_H
