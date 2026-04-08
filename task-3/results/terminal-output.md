# Дамп терминального вывода — Task 3

Демонстрация реальной работы экспортного задания.  
Запуск выполнен через Docker Compose (локальный эквивалент k8s Job).

---

## Сборка образа и запуск

```
$ docker compose up --build

 Image task-3-export_job Building
...
Successfully installed psycopg2-binary-2.9.9
...
 Image task-3-export_job Built

 Network task-3_default Created
 Volume task-3_postgres_data Created
 Volume task-3_export_data Created
 Container logistics-postgres Created
 Container logistics-export Created

logistics-postgres  | PostgreSQL init process complete; ready for start up.
logistics-postgres  | 2026-04-08 22:09:24 UTC [1] LOG: database system is ready to accept connections
logistics-postgres  | CREATE TABLE
logistics-postgres  | INSERT 0 20

logistics-export    | 2026-04-08 22:09:29,098 [INFO] Connecting to PostgreSQL at postgres:5432/logistics_db
logistics-export    | 2026-04-08 22:09:29,107 [INFO] Running SELECT * FROM shipments
logistics-export    | 2026-04-08 22:09:29,109 [INFO] Exporting 20 rows to /data/exports/shipments_2026-04-08.csv
logistics-export    | 2026-04-08 22:09:29,110 [INFO] Export completed successfully: /data/exports/shipments_2026-04-08.csv

logistics-export exited with code 0
```

---

## Проверка CSV-файла

```
$ docker run --rm -v task-3_export_data:/data/exports busybox sh -c \
    "ls /data/exports/ && echo '---' && cat /data/exports/shipments_2026-04-08.csv"

shipments_2026-04-08.csv
---
id,shipment_date,origin,destination,driver_id,vehicle_id,client_id,status,weight_kg,created_at
1,2026-04-01,Москва,Санкт-Петербург,1,101,201,delivered,1250.00,2026-04-08 22:09:24.114052
2,2026-04-01,Екатеринбург,Новосибирск,2,102,202,delivered,870.50,2026-04-08 22:09:24.114052
3,2026-04-02,Казань,Самара,3,103,203,in_transit,430.00,2026-04-08 22:09:24.114052
4,2026-04-02,Нижний Новгород,Ростов-на-Дону,4,104,204,delivered,2100.75,2026-04-08 22:09:24.114052
5,2026-04-03,Москва,Краснодар,1,105,205,in_transit,980.00,2026-04-08 22:09:24.114052
6,2026-04-03,Санкт-Петербург,Москва,5,101,206,delivered,640.25,2026-04-08 22:09:24.114052
7,2026-04-04,Новосибирск,Екатеринбург,2,102,207,pending,1800.00,2026-04-08 22:09:24.114052
8,2026-04-04,Самара,Казань,6,103,208,delivered,310.00,2026-04-08 22:09:24.114052
9,2026-04-05,Ростов-на-Дону,Москва,3,106,209,in_transit,750.50,2026-04-08 22:09:24.114052
10,2026-04-05,Краснодар,Санкт-Петербург,7,107,210,delivered,920.00,2026-04-08 22:09:24.114052
11,2026-04-06,Москва,Казань,4,108,211,delivered,1560.00,2026-04-08 22:09:24.114052
12,2026-04-06,Екатеринбург,Москва,1,109,212,in_transit,2300.50,2026-04-08 22:09:24.114052
13,2026-04-06,Нижний Новгород,Самара,8,110,213,pending,480.75,2026-04-08 22:09:24.114052
14,2026-04-07,Москва,Новосибирск,5,111,214,pending,3100.00,2026-04-08 22:09:24.114052
15,2026-04-07,Санкт-Петербург,Ростов-на-Дону,2,112,215,pending,1420.25,2026-04-08 22:09:24.114052
16,2026-04-07,Казань,Екатеринбург,9,113,216,in_transit,670.00,2026-04-08 22:09:24.114052
17,2026-04-07,Краснодар,Москва,6,114,217,pending,890.50,2026-04-08 22:09:24.114052
18,2026-04-07,Самара,Нижний Новгород,3,115,218,in_transit,550.00,2026-04-08 22:09:24.114052
19,2026-04-07,Москва,Санкт-Петербург,7,116,219,pending,1980.75,2026-04-08 22:09:24.114052
20,2026-04-07,Ростов-на-Дону,Краснодар,10,117,220,pending,730.00,2026-04-08 22:09:24.114052
```
