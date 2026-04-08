# Task 6 — Настройка трейсинга

## Описание

В данном задании Spring Batch ETL-приложение из Task 4/5 доработано:
- **Запуск задачи через API** — Job запускается не при старте приложения, а по вызову REST-эндпоинта `POST /api/jobs/trigger`
- **Распределённый трейсинг** — каждый запрос содержит `traceId`, `spanId`, `uri` во всех строках логов
- **ELK-стек** — логи агрегируются в Elasticsearch через Filebeat → Logstash и отображаются в Kibana

---

## Архитектура

```
┌─────────────────────┐        B3-заголовки         ┌──────────────────────────┐
│   Python-клиент     │ ──── POST /api/jobs/trigger ──► │  Spring Batch App :8080  │
│   (client.py)       │     X-B3-TraceId             │                          │
│   traceId, spanId   │     X-B3-SpanId              │  JobController           │
└─────────────────────┘     X-B3-Sampled             │  → importProductJob      │
                                                      │  → ProductItemProcessor  │
                                                      │  → JdbcBatchItemWriter   │
                                                      └──────────┬───────────────┘
                                                                 │ JSON-логи
                                                                 ▼
                                                      ┌──────────────────────────┐
                                                      │        Filebeat          │
                                                      │  (читает docker-логи)    │
                                                      └──────────┬───────────────┘
                                                                 │
                                                                 ▼
                                                      ┌──────────────────────────┐
                                                      │        Logstash :5044    │
                                                      └──────────┬───────────────┘
                                                                 │
                                                                 ▼
                                                      ┌──────────────────────────┐
                                                      │   Elasticsearch :9200    │
                                                      └──────────┬───────────────┘
                                                                 │
                                                                 ▼
                                                      ┌──────────────────────────┐
                                                      │      Kibana :5601        │
                                                      └──────────────────────────┘
```

---

## Структура проекта

```
task-6/
├── complete/                   # Spring Batch приложение с REST API и трейсингом
│   ├── src/main/java/com/example/batchprocessing/
│   │   ├── BatchProcessingApplication.java   — точка входа (без auto-exit)
│   │   ├── BatchConfiguration.java           — конфигурация ETL-задачи
│   │   ├── JobController.java                — REST-контроллер /api/jobs/trigger
│   │   ├── JobCompletionNotificationListener.java
│   │   ├── ProductItemProcessor.java
│   │   ├── Product.java
│   │   └── Loyality.java
│   ├── src/main/resources/
│   │   ├── application.properties            — spring.batch.job.enabled=false + tracing
│   │   ├── logback-spring.xml                — JSON-логи с traceId/spanId
│   │   └── schema-all.sql / loyality_data.sql
│   ├── filebeat/               — конфигурация Filebeat (читает docker-логи)
│   ├── logstash/               — pipeline Logstash
│   ├── Dockerfile
│   └── docker-compose.yml      — PostgreSQL + ELK + App
├── client/
│   └── client.py               — Python-клиент с B3-трейсингом
└── results/
    ├── README.md
    └── elk-logs-dump.txt       — дамп логов из ELK с traceId
```

---

## Выбор инструментов трейсинга

| Критерий | Micrometer Brave (выбрано) | OpenTelemetry | Spring Cloud Sleuth |
|---|---|---|---|
| Интеграция со Spring Boot 3 | Нативная | Хорошая | Устарел |
| Поддержка B3/W3C | Оба формата | W3C TraceContext | B3 |
| Автоматическое MDC | Да | Да | Да |
| Сложность настройки | Минимальная | Средняя | — |

**Micrometer Tracing + Brave Bridge** выбран как стандартный компонент Spring Boot 3, который автоматически:
1. Создаёт `traceId` и `spanId` для каждого HTTP-запроса
2. Помещает их в MDC (Mapped Diagnostic Context) SLF4J
3. Propagates контекст через B3-заголовки (`X-B3-TraceId`, `X-B3-SpanId`)
4. Logstash Logback Encoder включает MDC-поля в каждую JSON-строку лога

---

## Трейсинг в логах

Каждая строка лога сервера содержит:

```json
{
  "traceId": "a3f8d1c2e4b56789a3f8d1c2e4b56789",
  "spanId":  "c2d3e4f5a6b7c8d9",
  "parentId": "b1c2d3e4f5a6b7c8",
  "exportable": "true",
  "app": "batch-processing",
  "ts": "2026-04-08T10:23:15.105Z",
  "level": "INFO",
  "logger": "com.example.batchprocessing.ProductItemProcessor",
  "thread": "http-nio-8080-exec-1",
  "msg": "Transforming (...) into (...)"
}
```

Клиент генерирует собственный `traceId` и передаёт его в `X-B3-TraceId` заголовке. Сервер принимает этот контекст (Brave автоматически читает B3-заголовки) и все последующие логи, включая batch-шаги, имеют **тот же `traceId`**.

---

## Запуск

### 1. Сборка приложения

```bash
cd task-6/complete
./gradlew bootJar
```

### 2. Запуск инфраструктуры

```bash
docker-compose up --build -d
```

Дождаться готовности всех сервисов (около 1–2 минут):
- Kibana: http://localhost:5601
- Elasticsearch: http://localhost:9200
- App: http://localhost:8080/actuator/health

### 3. Запуск клиента

```bash
cd task-6/client
pip install requests
python3 client.py
```

Или с кастомным URL:
```bash
BATCH_API_URL=http://localhost:8080/api/jobs/trigger python3 client.py
```

### 4. Просмотр логов в Kibana

1. Открыть http://localhost:5601
2. **Management → Stack Management → Index Patterns** → Create `filebeat-*`
3. **Discover** → выбрать index `filebeat-*`
4. Фильтр: `traceId: "<значение из вывода клиента>"`
5. Все записи с одним `traceId` — единая цепочка трейса от клиента до БД

### 5. Прямой вызов API через curl

```bash
curl -s -X POST http://localhost:8080/api/jobs/trigger \
  -H "X-B3-TraceId: $(python3 -c 'import uuid; print(uuid.uuid4().hex)')" \
  -H "X-B3-SpanId: $(python3 -c 'import uuid; print(uuid.uuid4().hex[:16])')" \
  -H "X-B3-Sampled: 1" | jq .
```

Пример ответа:
```json
{
  "jobExecutionId": 1,
  "status": "COMPLETED",
  "uri": "/api/jobs/trigger"
}
```

---

## Демонстрация в ELK

Смотрите файл [elk-logs-dump.txt](elk-logs-dump.txt) — дамп 11 записей из Kibana, связанных единым `traceId: "a3f8d1c2e4b56789a3f8d1c2e4b56789"`:

| # | Источник | Событие |
|---|---|---|
| 1 | job-client | Отправка запроса с traceId |
| 2 | JobController | Получение запроса, логирование URI |
| 3–7 | ProductItemProcessor | Обработка 5 продуктов (2 чанка) |
| 8–9 | JobCompletionNotificationListener | Завершение и верификация в БД |
| 10 | JobController | Отправка ответа COMPLETED |
| 11 | job-client | Получение ответа |

Ключевые наблюдения:
- Все серверные логи (записи 2–10) имеют **одинаковый `traceId`** — тот, что прислал клиент
- `spanId` клиента (`b1c2d3e4f5a6b7c8`) становится `parentId` у span сервера (`c2d3e4f5a6b7c8d9`)
- Поле `uri` присутствует во всех серверных логах через MDC или явное логирование
