#include <string.h>
#include <stdlib.h>

#include "sst.h"

struct node {
    char data[FILENAME_LENGTH];
	struct node *next;
};

struct list {
    struct node *head;
    struct node *tail;
};

struct list * list_create();
void list_push(struct list *list, const char data[FILENAME_LENGTH]);
void list_delete(struct list *list);
