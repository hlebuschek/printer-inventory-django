#!/bin/bash

# Воркер для высокоприоритетных задач (пользовательские запросы)
celery -A printer_inventory worker \
    --queues=high_priority \
    --loglevel=INFO \
    --concurrency=4 \
    --max-tasks-per-child=100 \
    --hostname=worker_high@%h &

# Воркер для низкоприоритетных задач (периодические)
celery -A printer_inventory worker \
    --queues=low_priority \
    --loglevel=INFO \
    --concurrency=10 \
    --max-tasks-per-child=200 \
    --hostname=worker_low@%h &

# Воркер для задач демона
celery -A printer_inventory worker \
    --queues=daemon \
    --loglevel=INFO \
    --concurrency=1 \
    --max-tasks-per-child=50 \
    --hostname=worker_daemon@%h &

# Celery Beat для периодических задач
celery -A printer_inventory beat --loglevel=INFO &

wait