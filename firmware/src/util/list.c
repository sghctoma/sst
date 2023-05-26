#include "list.h"

static struct node * node_create(const char data[FILENAME_LENGTH]) {
    struct node *new = malloc(sizeof(struct node));
    if (new == NULL) {
        return NULL;
    }
    strncpy(new->data, data, FILENAME_LENGTH);
    new->next = NULL;
    return new;
}

struct list * list_create() {
    struct list *l = malloc(sizeof(struct list));
    if (l == NULL) {
        return NULL;
    }
    l->head = NULL;
    l->tail = NULL;
    return l;
}

void list_push(struct list *list, const char data[FILENAME_LENGTH]) {
    struct node *new = node_create(data);
    if (list->head == NULL) {
        list->head = new;
        list->tail = list->head;
    } else {
        list->tail->next = new;
        list->tail = new;
    }
}

void list_delete(struct list *list) {
     struct node *current = list->head;
     struct node *next = current;
     while(current != NULL) {
         next = current->next;
         free(current);
         current = next;
     }
     free(list);
}
