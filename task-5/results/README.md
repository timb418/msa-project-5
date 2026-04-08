# Task-5: Spring Batch с Наблюдаемостью — Результаты

## Описание задачи

Реализация Spring Batch приложения для обработки данных о продуктах с интеграцией полного стека наблюдаемости: метрики (Prometheus + Grafana), централизованное логирование (ELK) и оповещения (Grafana Alerting + Prometheus Alert Rules).

---

## 1. C4-диаграмма

Файл: `c4-diagram.puml` (PlantUML, формат C4 Container Diagram).

Диаграмма отражает:
- **Spring Batch Application** — основной компонент обработки данных с экспортом метрик и JSON-логов
- **PostgreSQL** — хранение данных лояльности (справочник) и результатов обработки
- **Prometheus** — периодический сбор (scrape) метрик приложения
- **Grafana** — визуализация метрик и отправка оповещений
- **Filebeat → Logstash → Elasticsearch** — конвейер сбора и хранения логов
- **Kibana** — просмотр и поиск по логам

---

## 2. Реализованные компоненты Spring Batch

### BatchConfiguration

- **Reader** (`FlatFileItemReader`) — читает `product-data.csv`, поля: `productId`, `productSku`, `productName`, `productAmount`, `productData`
- **Processor** (`ProductItemProcessor`) — обогащает продукт данными из таблицы `loyality_data` по ключу `productSku`
- **Writer** (`JdbcBatchItemWriter`) — записывает результат в таблицу `products`

Шаг (`step1`) обрабатывает чанки по 3 записи. Job (`importProductJob`) запускает шаг и уведомляет listener о завершении.

### ProductItemProcessor

Для каждого продукта выполняет запрос к `loyality_data` через `JdbcTemplate`. Если запись найдена — заменяет `productData` на значение программы лояльности. Результат трансформации логируется на уровне INFO.

### JobCompletionNotificationListener

После успешного завершения job выводит все записи из таблицы `products`, подтверждая корректность записи.

---

## 3. Обоснование выбранных метрик

Для мониторинга приложения выбраны следующие метрики, экспортируемые через Spring Boot Actuator (`/actuator/prometheus`):

| Метрика | Тип | Обоснование |
|---|---|---|
| `process_cpu_usage` | Gauge | Отражает текущую нагрузку на процессор. Рост CPU может сигнализировать о проблемах в логике обработки или бесконечных циклах. |
| `jvm_memory_used_bytes{area="heap"}` | Gauge | Показывает потребление heap-памяти JVM. Утечки памяти немедленно отражаются в этой метрике. |
| `jvm_memory_max_bytes{area="heap"}` | Gauge | Максимально доступная heap-память. Используется для вычисления процента использования. |
| `jvm_threads_live_threads` | Gauge | Количество активных потоков. Аномальный рост может свидетельствовать о thread leak или deadlock. |

**Почему именно эти метрики:**  
Spring Batch — это batch-процесс, который работает короткое время и завершается. Наиболее критичны для него ресурсы в момент работы: CPU (интенсивная обработка данных) и JVM Heap (буферизация чанков в памяти). Мониторинг этих метрик позволяет выявить деградацию производительности при увеличении объёма данных в CSV-файле.

---

## 4. Конфигурация сбора логов (ELK)

### Способ отправки логов

Выбран подход **Filebeat → Logstash → Elasticsearch** (агентный сбор через Docker).

**Обоснование выбора:**

| Критерий | Выбранный подход (Filebeat) | Альтернатива (прямая запись в Logstash/ES) |
|---|---|---|
| Связность | Приложение не знает о ELK — слабая связность | Приложение зависит от доступности Logstash |
| Надёжность | Filebeat буферизует логи при недоступности Logstash | Потеря логов при недоступности ES |
| Формат | Приложение пишет JSON в stdout — стандартный подход для контейнеров | Требует отдельного appender |
| Масштабируемость | Filebeat работает как sidecar/DaemonSet — универсален для любого числа контейнеров | Нужно настраивать каждый сервис отдельно |

**Логирование в приложении:**
- Формат: JSON (Logstash Logback Encoder) — каждая строка лога является валидным JSON-объектом
- Поля: `timestamp`, `level`, `logger`, `message`, `traceId`, `spanId` — поддержка distributed tracing
- Уровень: DEBUG для пакета `com.example.batchprocessing` — детальная трассировка трансформаций

**Конвейер:**
1. Приложение пишет JSON-логи в stdout Docker-контейнера
2. Filebeat читает логи через Docker socket, декодирует JSON-поля, добавляет Docker-метаданные (имя контейнера, image)
3. Logstash принимает события по протоколу Beats, индексирует в Elasticsearch с суффиксом даты (`logstash-YYYY.MM.DD`)
4. Kibana предоставляет UI для поиска, фильтрации и анализа логов

---

## 5. Конфигурация оповещений

Оповещения настроены на двух уровнях: Prometheus Alert Rules и Grafana Alerting.

### 5.1 Prometheus Alert Rules (`prometheus/alerts.yml`)

**Алерт 1: HighCpuUsage**
- **Условие:** `process_cpu_usage * 100 > 80` в течение 1 минуты
- **Severity:** warning
- **Обоснование:** Порог 80% выбран как признак аномальной нагрузки. Кратковременные пики (< 1 мин) игнорируются — типично при старте JVM. Устойчивое превышение 80% на batch-процессе указывает на проблему в логике обработки.

**Алерт 2: HighJvmHeapUsage**
- **Условие:** `jvm_memory_used_bytes{area="heap"} / jvm_memory_max_bytes{area="heap"} * 100 > 85` в течение 1 минуты
- **Severity:** critical
- **Обоснование:** 85% heap — это порог перед началом интенсивной работы GC и возможного OutOfMemoryError. Алерт critical, т.к. при превышении этого уровня приложение может упасть. Для batch-процессов с большими чанками heap — первый индикатор необходимости тюнинга.

### 5.2 Grafana Alerting (`grafana/provisioning/alerting/rules.yml`)

Аналогичные правила продублированы в Grafana Unified Alerting для визуализации состояния непосредственно в дашборде:
- Алерт по CPU (> 80%) — severity: warning
- Алерт по JVM Heap (> 85%) — severity: critical

Оповещения видны в UI Grafana в разделе Alerting → Alert Rules.

---

## 6. Grafana дашборд

Файл: `grafana/provisioning/dashboards/batch-processing-dashboard.json`

Панели дашборда:

| Панель | Тип | Метрика |
|---|---|---|
| CPU Usage (%) | Stat | `process_cpu_usage * 100` |
| JVM Heap Usage (%) | Gauge | `jvm_memory_used / jvm_memory_max * 100` |
| JVM Heap Used | Stat | `jvm_memory_used_bytes{area="heap"}` |
| JVM Live Threads | Stat | `jvm_threads_live_threads` |
| CPU Usage — динамика | Timeseries | `process_cpu_usage * 100` |
| JVM Heap Memory — динамика | Timeseries | `jvm_memory_used_bytes` + `jvm_memory_max_bytes` |

Дашборд автоматически загружается при старте Grafana через provisioning.

---

## 7. Инфраструктура (Docker Compose)

| Сервис | Порт | Назначение |
|---|---|---|
| PostgreSQL | 5432 | База данных |
| Elasticsearch | 9200 | Хранилище логов |
| Logstash | 5044 | Обработка логов |
| Kibana | 5601 | UI для логов |
| Filebeat | — | Сбор Docker-логов |
| Prometheus | 9090 | Сбор и хранение метрик |
| Grafana | 3000 | Дашборды и оповещения |
| batch-processing | 8080 | Приложение |

---

## 8. Запуск

```bash
# Сборка JAR
./gradlew build

# Сборка Docker-образа
docker build . -t batch-processing

# Запуск всего стека
docker-compose up
```

Перед первым запуском создать таблицы через клиент БД:
```
src/main/resources/schema-all.sql
```

### Проверка результатов

| Компонент | URL |
|---|---|
| Prometheus | http://localhost:9090 |
| Prometheus alerts | http://localhost:9090/alerts |
| Grafana | http://localhost:3000 (admin/admin) |
| Kibana | http://localhost:5601 |
| Метрики приложения | http://localhost:8080/actuator/prometheus |

В логах приложения после выполнения job должны быть:
```
Transforming (Product[...]) into (Product[...])
!!! JOB FINISHED! Time to verify the results
Transformed <Product[...]> in the database.
```

---

## 9. Демонстрация логов в ELK

Реальный дамп логов Spring Batch приложения, собранных через ELK-стек (Filebeat → Logstash → Elasticsearch), приведён в Task 6: [`../task-6/results/elk-logs-dump.txt`](../../task-6/results/elk-logs-dump.txt).

Приложение в Task 5 использует идентичный стек и конфигурацию:
- тот же `logback-spring.xml` — JSON-формат с полями `ts`, `level`, `logger`, `msg`, `app`, `thread`
- тот же конвейер: Filebeat читает stdout контейнера → Logstash → Elasticsearch → Kibana
- те же логи batch job: трансформация продуктов, завершение job, верификация записей в БД

Отличие Task 6 от Task 5 только в способе запуска job (через HTTP API vs при старте приложения), что не влияет на формат и содержимое логов в ELK.
