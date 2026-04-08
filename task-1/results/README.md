# Задание 1. Пакетная обработка данных — Apache Airflow POC

## Содержимое директории

```
task-1/results/
├── README.md              # Этот файл
├── justification.md       # Обоснование выбора технологии
├── docker-compose.yml     # Airflow + PostgreSQL
├── .env                   # Конфигурация окружения
├── dags/
│   └── batch_processing_dag.py   # DAG с ветвлением, retry и уведомлениями
├── data/
│   ├── product-data.csv           # Источник данных (товары)
│   └── loyality_data.csv          # Данные программы лояльности
└── init-scripts/
    └── init.sql           # Инициализация БД productsdb
```

---

## Требования

- Docker Desktop (с включённым Docker Compose)
- 4 GB RAM минимум (рекомендуется 6 GB)

---

## Быстрый старт

### 1. Перейти в директорию с результатами

```bash
cd task-1/results
```

### 2. (Опционально) Настроить email-уведомления

Откройте `.env` и заполните SMTP-параметры:

```env
AIRFLOW__SMTP__SMTP_USER=your-email@gmail.com
AIRFLOW__SMTP__SMTP_PASSWORD=your-app-password
AIRFLOW__SMTP__SMTP_MAIL_FROM=your-email@gmail.com
```

> Для Gmail нужен **App Password** (не основной пароль). Без настройки SMTP пайплайн работает, email не отправляется.

### 3. Запустить контейнеры

```bash
docker-compose up -d
```

При первом запуске `airflow-init` выполнит инициализацию базы и создаст пользователя `admin/admin`. Процесс занимает ~1-2 минуты.

Проверить статус:
```bash
docker-compose ps
```

Все три сервиса должны быть `running`: `postgres`, `airflow-webserver`, `airflow-scheduler`.

### 4. Открыть Airflow UI

Перейдите по адресу: **http://localhost:8080**

Логин: `admin` / Пароль: `admin`

### 5. Запустить пайплайн

1. На главной странице найдите DAG **`batch_processing_dag`**
2. Включите его (переключатель слева)
3. Нажмите кнопку **▶ Trigger DAG** (иконка Play справа)
4. Нажмите на название DAG → вкладка **Graph** для наблюдения за выполнением

---

## Пайплайн — что происходит

```
read_csv → analyze_data → branch_on_count
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
              process_large         process_small
              (count > 3)           (count ≤ 3)
                    │                     │
                    └──────────┬──────────┘
                               ▼
                          load_complete
                               │
                               ▼
                         notify_success
```

| Задача | Что делает |
|--------|-----------|
| `read_csv` | Читает `product-data.csv`, передаёт записи через XCom |
| `analyze_data` | Выводит статистику по записям в лог |
| `branch_on_count` | Если записей > 3 → `process_large`, иначе → `process_small` |
| `process_large` | Чанковая загрузка в PostgreSQL с обогащением данными лояльности. Retry: 3 попытки, задержка 1 мин |
| `process_small` | Единичная загрузка в PostgreSQL. Retry: 3 попытки, задержка 1 мин |
| `load_complete` | Точка соединения веток |
| `notify_success` | Логирует успешное завершение (email при настроенном SMTP) |

---

## Проверка результатов в БД

Подключиться к PostgreSQL:

```bash
docker exec -it $(docker-compose ps -q postgres) \
  psql -U postgres -d productsdb
```

Запросить загруженные данные:

```sql
SELECT * FROM products;
```

Ожидаемый результат (5 строк с обогащёнными данными лояльности):

```
 product_id | product_sku | product_name | product_amount | product_data
------------+-------------+--------------+----------------+--------------
          1 | 20001       | hammer       |             45 | Loyality_on
          2 | 30001       | sink         |             20 | Loyality_on
          3 | 40001       | roof_shell   |            256 | Loyality_on
          4 | 50001       | priming      |             67 | Loyality_on
          5 | 60001       | clapboard    |            120 | Loyality_on
```

---

## Просмотр логов задачи

В Airflow UI:
1. Graph view → кликнуть на задачу (например, `process_large`)
2. Нажать **Log**

Или через CLI:
```bash
docker-compose logs airflow-scheduler
```

---

## Демонстрация retry-политики

Чтобы принудительно вызвать retry, временно укажите неверный хост БД в DAG:

```python
DB_CONFIG = {
    "host": "wrong-host",   # <-- намеренная ошибка
    ...
}
```

После перезапуска задача упадёт и выполнит 3 retry с интервалом 1 минута. В UI это видно в колонке `Tries`.

---

## Остановка

```bash
docker-compose down          # остановить контейнеры
docker-compose down -v       # остановить и удалить данные
```

---

## Облачное развёртывание (GCP)

Для перехода с локального Docker Compose на продакшн достаточно:

1. Создать **Cloud Composer** окружение в GCP (управляемый Airflow)
2. Загрузить DAG-файл в GCS bucket, связанный с Composer
3. Настроить подключения (`Admin → Connections`) для BigQuery, PostgreSQL, Kafka

DAG-код не требует изменений — Airflow-операторы работают одинаково локально и в облаке.
