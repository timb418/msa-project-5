# Результаты выполнения Task 1: Apache Airflow Batch Processing POC

---

## 1. Развёртывание — `docker-compose ps`

```
$ docker-compose ps

NAME                          IMAGE                  COMMAND                  SERVICE             CREATED       STATUS                    PORTS
results-airflow-scheduler-1   apache/airflow:2.9.1   "/usr/bin/dumb-init …"   airflow-scheduler   2 min ago     Up About a minute         8080/tcp
results-airflow-webserver-1   apache/airflow:2.9.1   "/usr/bin/dumb-init …"   airflow-webserver   2 min ago     Up About a minute (healthy)   0.0.0.0:8080->8080/tcp
results-postgres-1            postgres:15            "docker-entrypoint.s…"   postgres            2 min ago     Up About a minute (healthy)   0.0.0.0:5432->5432/tcp
```

Все три сервиса запущены и здоровы:
- `airflow-webserver` — UI на http://localhost:8080 (admin/admin)
- `airflow-scheduler` — планировщик задач
- `postgres` — БД для Airflow и приложения

---

## 2. Список DAG-ов — `airflow dags list`

```
$ docker-compose exec airflow-webserver airflow dags list

dag_id               | fileloc                                   | owners    | is_paused
=====================+===========================================+===========+==========
batch_processing_dag | /opt/airflow/dags/batch_processing_dag.py | tradeware | False
```

DAG `batch_processing_dag` зарегистрирован и включён (is_paused = False).

---

## 3. Топология пайплайна

```
read_csv
    │
    ▼
analyze_data
    │
    ▼
branch_on_count   ◄── BranchPythonOperator
   │           │
   ▼           ▼
process_large  process_small
(count > 3)    (count ≤ 3)
   │           │
   └─────┬─────┘
         ▼
    load_complete   ◄── TriggerRule: NONE_FAILED_MIN_ONE_SUCCESS
         │
         ▼
    notify_success
```

При 5 записях (порог = 3) активируется ветка `process_large`, `process_small` — пропускается (skipped).

---

## 4. Успешный запуск — статус Run

```
$ docker-compose exec airflow-webserver airflow dags list-runs -d batch_processing_dag

dag_id               | run_id                               | state   | execution_date            | start_date                       | end_date
=====================+======================================+=========+===========================+==================================+===================================
batch_processing_dag | manual__2026-04-08T21:59:35+00:00    | success | 2026-04-08T21:59:35+00:00 | 2026-04-08T21:59:36.708322+00:00 | 2026-04-08T21:59:42.823325+00:00
```

```
$ docker-compose exec airflow-webserver airflow tasks states-for-dag-run \
      batch_processing_dag manual__2026-04-08T21:59:35+00:00

dag_id               | execution_date            | task_id         | state   | start_date                       | end_date
=====================+===========================+=================+=========+==================================+=================================
batch_processing_dag | 2026-04-08T21:59:35+00:00 | read_csv        | success | 2026-04-08T21:59:36.917254+00:00 | 2026-04-08T21:59:37.139452+00:00
batch_processing_dag | 2026-04-08T21:59:35+00:00 | analyze_data    | success | 2026-04-08T21:59:38.067173+00:00 | 2026-04-08T21:59:38.274637+00:00
batch_processing_dag | 2026-04-08T21:59:35+00:00 | branch_on_count | success | 2026-04-08T21:59:39.144283+00:00 | 2026-04-08T21:59:39.387228+00:00
batch_processing_dag | 2026-04-08T21:59:35+00:00 | process_large   | success | 2026-04-08T21:59:40.247782+00:00 | 2026-04-08T21:59:40.493914+00:00
batch_processing_dag | 2026-04-08T21:59:35+00:00 | process_small   | skipped | 2026-04-08T21:59:39.342475+00:00 | 2026-04-08T21:59:39.342475+00:00
batch_processing_dag | 2026-04-08T21:59:35+00:00 | load_complete   | success | 2026-04-08T21:59:40.711565+00:00 | 2026-04-08T21:59:40.711567+00:00
batch_processing_dag | 2026-04-08T21:59:35+00:00 | notify_success  | success | 2026-04-08T21:59:41.939618+00:00 | 2026-04-08T21:59:42.157884+00:00
```

Все задачи успешны. `process_small` — skipped (корректно, т.к. записей > 3).

---

## 5. Лог задачи `read_csv` — чтение из источника данных

```
[2026-04-08T21:59:36.923+0000] {taskinstance.py:2306} INFO - Starting attempt 1 of 4
[2026-04-08T21:59:36.935+0000] {taskinstance.py:2330} INFO - Executing <Task(PythonOperator): read_csv> on 2026-04-08 21:59:35+00:00
[2026-04-08T21:59:37.103+0000] {batch_processing_dag.py:79} INFO - Прочитано 5 записей из /opt/airflow/data/product-data.csv
[2026-04-08T21:59:37.161+0000] {local_task_job_runner.py:240} INFO - Task exited with return code 0
```

Задача прочитала 5 строк из `/opt/airflow/data/product-data.csv` (файловая система контейнера).

---

## 6. Лог задачи `analyze_data` — анализ датасета

```
[2026-04-08T21:59:38.262+0000] {batch_processing_dag.py:88} INFO - === Анализ данных ===
[2026-04-08T21:59:38.262+0000] {batch_processing_dag.py:89} INFO - Всего записей: 5
[2026-04-08T21:59:38.262+0000] {batch_processing_dag.py:91} INFO -   product_id=1, sku=20001, name=hammer, amount=45
[2026-04-08T21:59:38.262+0000] {batch_processing_dag.py:91} INFO -   product_id=2, sku=30001, name=sink, amount=20
[2026-04-08T21:59:38.262+0000] {batch_processing_dag.py:91} INFO -   product_id=3, sku=40001, name=roof_shell, amount=256
[2026-04-08T21:59:38.262+0000] {batch_processing_dag.py:91} INFO -   product_id=4, sku=50001, name=priming, amount=67
[2026-04-08T21:59:38.262+0000] {batch_processing_dag.py:91} INFO -   product_id=5, sku=60001, name=clapboard, amount=120
```

---

## 7. Лог задачи `branch_on_count` — ветвление пайплайна по условию

```
[2026-04-08T21:59:39.326+0000] {batch_processing_dag.py:101} INFO - Количество записей: 5 (порог: 3)
[2026-04-08T21:59:39.326+0000] {batch_processing_dag.py:103} INFO - Переход на ветку: process_large
```

5 > 3, поэтому выбрана ветка `process_large`.

---

## 8. Retry-политика — конфигурация и демонстрация

### Конфигурация в коде (dags/batch_processing_dag.py)

```python
default_args = {
    "owner": "tradeware",
    "depends_on_past": False,
    "email": NOTIFICATION_EMAIL,
    "email_on_failure": True,
    "email_on_retry": True,
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "on_failure_callback": on_failure_callback,
}

# Явно задано также на уровне задачи:
t_large = PythonOperator(
    task_id="process_large",
    python_callable=process_large,
    retries=3,
    retry_delay=timedelta(minutes=1),
)
t_small = PythonOperator(
    task_id="process_small",
    python_callable=process_small,
    retries=3,
    retry_delay=timedelta(minutes=1),
)
```

Максимум попыток: **4** (1 основная + 3 retry).

### Retry в действии (предыдущий запуск с ошибкой аутентификации БД)

При первом запуске задача `process_large` падала из-за неверного пароля пользователя postgres.
Airflow автоматически перевёл её в состояние `up_for_retry` и запустил повторно через 1 минуту:

```
$ airflow tasks states-for-dag-run batch_processing_dag manual__2026-04-08T21:51:44+00:00

task_id         | state        | start_date
================+==============+==================================
read_csv        | success      | 2026-04-08T21:51:45.094799+00:00
analyze_data    | success      | 2026-04-08T21:51:45.752301+00:00
branch_on_count | success      | 2026-04-08T21:51:46.865498+00:00
process_small   | skipped      | 2026-04-08T21:51:47.100039+00:00
process_large   | up_for_retry | 2026-04-08T21:52:48.473699+00:00   ← retry
```

Лог ошибки и уведомления:
```
[2026-04-08T21:51:48.139+0000] {taskinstance.py:2905} ERROR - Task failed with exception
psycopg2.OperationalError: connection to server at "postgres" (172.20.0.2), port 5432 failed:
FATAL: password authentication failed for user "postgres"

[2026-04-08T21:51:50.298+0000] {taskinstance.py:879} ERROR - Failed to send email to: ['admin@example.com']
```

*(Email не отправлен, т.к. SMTP не настроен — используется шаблонный адрес admin@example.com.
 В реальном окружении сработает при заполненных SMTP-реквизитах в .env)*

### Статус успешного запуска после исправления

```
$ docker-compose exec airflow-webserver airflow tasks state \
      batch_processing_dag process_large "2026-04-08T21:59:35+00:00"

success
```

---

## 9. Email-уведомления — конфигурация

### Конфигурация в коде (default_args)

```python
default_args = {
    "email": ["admin@example.com"],   # адрес получателя
    "email_on_failure": True,         # письмо при падении задачи
    "email_on_retry": True,           # письмо при каждом retry
    "email_on_success": False,        # успех обрабатывается задачей notify_success
    "on_failure_callback": on_failure_callback,
}
```

### SMTP-конфигурация (.env / Airflow config)

```
AIRFLOW__SMTP__SMTP_HOST=smtp.gmail.com
AIRFLOW__SMTP__SMTP_STARTTLS=true
AIRFLOW__SMTP__SMTP_SSL=false
AIRFLOW__SMTP__SMTP_PORT=587
AIRFLOW__SMTP__SMTP_USER=your-email@gmail.com
AIRFLOW__SMTP__SMTP_PASSWORD=your-app-password
AIRFLOW__SMTP__SMTP_MAIL_FROM=your-email@gmail.com
```

Проверка через Airflow CLI:
```
$ docker-compose exec airflow-webserver airflow config get-value smtp smtp_host
smtp.gmail.com

$ docker-compose exec airflow-webserver airflow config get-value smtp smtp_port
587
```

Для активации достаточно заменить `your-email@gmail.com` и `your-app-password` реальными значениями.

---

## 10. Данные в PostgreSQL — результат end-to-end

```
$ docker-compose exec postgres \
      psql -U postgres -d productsdb -c "SELECT * FROM products ORDER BY product_id;"

 product_id | product_sku | product_name | product_amount | product_data
------------+-------------+--------------+----------------+--------------
          1 | 20001       | hammer       |             45 | Loyality_on
          2 | 30001       | sink         |             20 | Loyality_on
          3 | 40001       | roof_shell   |            256 | Loyality_on
          4 | 50001       | priming      |             67 | Loyality_on
          5 | 60001       | clapboard    |            120 | Loyality_on
(5 rows)
```

5 записей загружены. Обогащение данными лояльности сработало корректно:
- Исходное значение `product_data` в CSV: `Loyality_off` для записей 1, 2, 4
- После обогащения из `loyality_data.csv`: все 4 SKU (20001, 30001, 50001, 60001) → `Loyality_on`
- SKU 40001 (roof_shell) исходно уже имел `Loyality_on` и отсутствует в таблице лояльности

---
