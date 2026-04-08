# Обоснование выбора технологического решения для пакетной обработки данных

## Контекст задачи

Маркетинговому отделу необходимо объединять данные из нескольких источников (CSV-файлы, PostgreSQL, Kafka) и формировать отчёты. Ожидаемый объём — около 1 млн записей за один запуск пайплайна. Будущая инфраструктура — облако (GCP), текущий стек компании — Java, Docker, GCP.

---

## Сравнительный анализ решений

| Критерий | **Apache Airflow** | Spring Batch | K8s CronJob | Apache Spark |
|---|---|---|---|---|
| **Интеграция с BigQuery** | ✅ Нативный оператор `BigQueryOperator` | ⚠️ Требует кастомного адаптера | ❌ Нет | ✅ Коннектор через Spark BigQuery |
| **Интеграция с Redshift** | ✅ `RedshiftSQLOperator`, `S3ToRedshiftOperator` | ⚠️ Требует кастомного адаптера | ❌ Нет | ✅ Через JDBC |
| **Интеграция с Kafka** | ✅ `KafkaConsumeOperator`, `KafkaSensor` | ⚠️ `spring-kafka` вручную | ❌ Нет | ✅ Spark Streaming |
| **Интеграция со Spark** | ✅ `SparkSubmitOperator`, `DataprocSubmitJobOperator` | ❌ Нет | ❌ Нет | ✅ Нативно |
| **Ветвление пайплайна** | ✅ `BranchPythonOperator` | ⚠️ `JobExecutionDecider` (сложнее) | ❌ Не поддерживается | ⚠️ Условные шаги вручную |
| **Условные операторы** | ✅ Нативно + XCom для передачи данных | ⚠️ Через `StepDecider` | ❌ Нет | ⚠️ Программный код |
| **Event-triggers** | ✅ `FileSensor`, `KafkaSensor`, `HttpSensor` | ❌ Нет | ❌ Нет | ❌ Нет |
| **Retry-политика** | ✅ На уровне каждой задачи (`retries`, `retry_delay`, `retry_exponential_backoff`) | ✅ Встроенная (`@Retryable`) | ⚠️ `backoffLimit` на уровне Job | ❌ Нет |
| **Fallback-логика** | ✅ `trigger_rule`, `on_failure_callback`, `SkipMixin` | ⚠️ Требует кастомного кода | ❌ Нет | ❌ Нет |
| **Email-уведомления** | ✅ Встроенный SMTP, `email_on_failure`, `email_on_retry` | ⚠️ `JavaMailSender` вручную | ❌ Нет | ❌ Нет |
| **Встроенный мониторинг** | ✅ Web UI, Prometheus-экспортёр, Grafana-дашборды | ⚠️ Spring Actuator (базовый) | ⚠️ `kubectl` / k8s dashboard | ✅ Spark History Server |
| **Развёртывание в облаке** | ✅ **Cloud Composer** (GCP), MWAA (AWS), Astronomer | ⚠️ Cloud Run / GKE | ✅ GKE CronJob | ✅ Dataproc / EMR |
| **Сложность развёртывания** | Средняя (Docker Compose → Cloud Composer) | Низкая (Spring Boot) | Низкая (yaml) | Высокая |
| **Ресурсоёмкость** | Средняя (Webserver + Scheduler + DB) | Низкая | Минимальная | Высокая |

---

## Вывод: Apache Airflow

**Apache Airflow** — оптимальный выбор по следующим причинам:

### 1. Готовые интеграции ускоряют разработку
Все необходимые интеграции доступны через `apache-airflow-providers-*` пакеты:
- `apache-airflow-providers-google` → BigQuery, GCS, Cloud Composer, Dataproc (Spark)
- `apache-airflow-providers-apache-kafka` → чтение/запись в Kafka-топики
- `apache-airflow-providers-amazon` → Redshift, S3
- `apache-airflow-providers-apache-spark` → запуск Spark-джобов

Установка: `pip install apache-airflow-providers-google apache-airflow-providers-apache-kafka`

### 2. Гибкий пайплайн с ветвлением и условиями
`BranchPythonOperator` позволяет реализовать любое условное ветвление прямо в Python. `TriggerRule` управляет логикой downstream-задач (ANY_SUCCESS, NONE_FAILED и т.д.).

### 3. Из коробки: fallback-logic, retry, email
- `retries=N` и `retry_delay=timedelta(...)` — на уровне каждой задачи
- `retry_exponential_backoff=True` — экспоненциальная задержка
- `email_on_failure=True`, `email_on_retry=True` — email через SMTP без дополнительного кода
- `on_failure_callback` — произвольная логика при падении

### 4. Развёртывание в облаке (GCP)
Локальное развёртывание через **Docker Compose** — идентичная среда. Для перехода в продакшн достаточно создать **Cloud Composer** окружение в GCP: тот же Airflow, те же DAG-файлы, полная совместимость с существующей инфраструктурой TradeWare (GCS, GCP).

```
Локально:           Docker Compose (Airflow + PostgreSQL)
                          ↓  (те же DAG-файлы)
Облако (GCP):       Cloud Composer (управляемый Airflow)
                    + интеграция с BigQuery, GCS, Dataproc
```

### 5. Масштабируемость
- Локально: `LocalExecutor` → один процесс, подходит для POC
- Production: `CeleryExecutor` + Redis → горизонтальное масштабирование воркеров
- GCP Cloud Composer: автомасштабирование из коробки

---

## Описание POC-пайплайна

Реализованный DAG (`batch_processing_dag`) демонстрирует все требуемые возможности:

```
read_csv
    │
    ▼
analyze_data
    │
    ▼
branch_on_count  ──► (count > 3) ──► process_large ──┐
    │                                                  │
    └──────────── (count ≤ 3) ──► process_small ──────┤
                                                       │
                                                  load_complete
                                                       │
                                                  notify_success
```

| Шаг | Реализация |
|-----|-----------|
| Чтение из источника | `read_csv` — читает `product-data.csv`, пушит данные в XCom |
| Анализ и ветвление | `branch_on_count` — `BranchPythonOperator` |
| Обработка | `process_large` / `process_small` — обогащение данными лояльности, запись в PostgreSQL |
| Retry | `retries=3, retry_delay=timedelta(minutes=1)` на задачах обработки |
| Email при успехе | `notify_success` + `email_on_success=False` (уведомление через задачу) |
| Email при ошибке | `email_on_failure=True` + `on_failure_callback` |

---

## Альтернативы и почему они не выбраны

- **Spring Batch** — хорош для ETL в Java-экосистеме, но не имеет ветвления, сенсоров и нативных интеграций с облачными сервисами. Выбран для Task 4 именно как Java-нативный ETL.
- **K8s CronJob** — простое расписание, но нет DAG-оркестрации, ветвления, уведомлений, мониторинга.
- **Apache Spark** — отлично для трансформации больших объёмов данных (1 млн+ строк с вычислениями), но требует отдельного оркестратора (того же Airflow) для планирования и уведомлений. Не является standalone-решением для пайплайна.
