# Верхнеуровневый план реализации — K8s CronJob для экспорта прайс-листов

## Обзор решения

Экспортный сервис реализуется как **Kubernetes CronJob**, который каждое утро в 06:00 запускает Pod с экспортным приложением. Приложение подключается к PostgreSQL, выполняет JOIN таблиц `products`, `categories`, `clients`, `client_prices`, формирует отдельный CSV-файл для каждого B2B-клиента и загружает результаты в объектное хранилище (GCS/S3).

**Компоненты решения:**
- Экспортное приложение на **Python** в Docker-контейнере
- Kubernetes манифесты: `CronJob`, `Secret`, `ConfigMap`
- Интеграция с объектным хранилищем (GCS или S3)
- Логирование через ELK и мониторинг через Prometheus + Grafana

## Предварительные условия

- Kubernetes-кластер с доступом к PostgreSQL из Pod
- Container Registry для хранения Docker-образа
- Объектное хранилище (GCS bucket или S3 bucket)
- Prometheus + Grafana + ELK уже развёрнуты в кластере (или планируются)
- PostgreSQL заполнен данными: таблицы `products`, `categories`, `clients`, `client_prices`

---

## Шаги реализации

### Шаг 0. Подготовка namespace и RBAC

**Цель:** создать изолированное пространство имён и минимальные права доступа для Job.

**Действия:**
- Создать файл `k8s/namespace.yaml`:
  ```yaml
  apiVersion: v1
  kind: Namespace
  metadata:
    name: price-export
  ---
  apiVersion: v1
  kind: ServiceAccount
  metadata:
    name: export-job-sa
    namespace: price-export
  ```
- Применить: `kubectl apply -f k8s/namespace.yaml`
- Убедиться что PostgreSQL доступен из namespace `price-export` (NetworkPolicy или shared namespace)

**Артефакт:** файл `k8s/namespace.yaml`.

---

### Шаг 1. Подготовка SQL-запроса экспорта

**Цель:** написать и проверить запрос, формирующий прайс-лист для конкретного клиента.

**Действия:**
- Написать параметризованный JOIN-запрос по четырём таблицам:
  ```sql
  SELECT
      p.sku          AS product_sku,
      p.name         AS product_name,
      cat.name       AS category,
      cp.price       AS client_price,
      cp.currency    AS currency
  FROM products p
  JOIN categories cat ON p.category_id = cat.id
  JOIN client_prices cp ON cp.product_id = p.id
  JOIN clients c ON cp.client_id = c.id
  WHERE c.id = :client_id
  ORDER BY cat.name, p.name;
  ```
- Проверить запрос на тестовых данных, убедиться в корректности JOIN
- Зафиксировать схему выходного CSV: заголовки столбцов, разделитель (`,`), кодировка UTF-8
- Написать запрос для получения списка всех активных B2B-клиентов (`SELECT id FROM clients WHERE active = true`)

**Артефакт:** SQL-файл `export_query.sql` с итоговым запросом.

---

### Шаг 2. Реализация экспортного приложения

**Цель:** создать минимальное приложение, выполняющее экспорт.

**Язык:** Python — минимальный overhead, нет JVM-старта, зависимости (`psycopg2`, `google-cloud-storage` или `boto3`) устанавливаются через `pip`. Для данного объёма данных (20K строк) производительность Python полностью достаточна.

**Действия:**
- Реализовать логику в одном модуле `export_job.py`:
  1. Получить список активных клиентов из БД
  2. Для каждого клиента: выполнить JOIN-запрос, записать результат во временный CSV (`/tmp/price_list_{client_id}.csv`)
  3. После успешной записи загрузить файл в Object Storage по пути `{STORAGE_BUCKET}/price-lists/{date}/price_list_{client_id}.csv` (атомарно — сначала `/tmp`, затем Storage)
  4. Завершить процесс с кодом `0` при успехе, `1` при ошибке
- Конфигурация через переменные окружения:
  - `DB_HOST`, `DB_PORT`, `DB_NAME` — параметры подключения к PostgreSQL
  - `DB_USER`, `DB_PASSWORD` — учётные данные БД
  - `STORAGE_BUCKET` — имя бакета GCS/S3
  - `EXPORT_DATE` — дата экспорта (по умолчанию текущая, формат `YYYY-MM-DD`)
- Логировать в stdout в формате JSON: `{"timestamp": "...", "level": "INFO", "client_id": 42, "rows": 1500, "duration_ms": 230}`

**Артефакт:** исходный код приложения `export_job.py`.

---

### Шаг 3. Контейнеризация — Dockerfile

**Цель:** создать минимальный Docker-образ для экспортного приложения.

**Действия:**
- Написать `Dockerfile` на базе минимального Python-образа:
  ```dockerfile
  FROM python:3.11-slim

  WORKDIR /app

  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  COPY export_job.py .

  ENTRYPOINT ["python", "export_job.py"]
  ```
- Файл `requirements.txt`:
  ```
  psycopg2-binary==2.9.9
  google-cloud-storage==2.16.0
  # для S3: boto3==1.34.0
  ```
- Убедиться что образ не содержит секретов, `.env`-файлов или тестовых данных (добавить `.dockerignore`)
- Проверить локальный запуск: `docker run --env-file .env export-job:latest`

**Артефакт:** `Dockerfile` в корне проекта.

---

### Шаг 4. CI/CD — сборка и публикация образа

**Цель:** автоматизировать сборку и публикацию Docker-образа.

**Действия:**
- Настроить pipeline (GitHub Actions / GitLab CI):
  - `docker build -t export-job:${GIT_SHA} .`
  - Сканировать образ на уязвимости: `trivy image --exit-code 1 --severity HIGH,CRITICAL export-job:${GIT_SHA}`
  - `docker push registry.example.com/export-job:${GIT_SHA}`
  - Тег `latest` обновлять только при merge в `main`
- Использовать тег по git-SHA (`export-job:abc1234`) для трассируемости в K8s
- Настроить аутентификацию в Container Registry через OIDC (GitHub Actions) или deploy token (GitLab) — не хранить статические ключи в CI

**Артефакт:** файл `.github/workflows/build.yml` или `.gitlab-ci.yml`.

---

### Шаг 5. Kubernetes-манифесты

**Цель:** создать K8s-объекты для запуска CronJob.

**Действия:**

Создать `k8s/secret.yaml` — учётные данные (значения в base64):
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: export-job-secret
  namespace: price-export
type: Opaque
data:
  db-password: <base64>
  storage-key: <base64>
```

Создать `k8s/configmap.yaml` — параметры подключения:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: export-job-config
  namespace: price-export
data:
  DB_URL: "jdbc:postgresql://postgres-service:5432/pricelist"
  DB_USER: "export_user"
  STORAGE_BUCKET: "my-bucket-price-lists"
```

Создать `k8s/cronjob.yaml` — основной манифест:
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: export-price-lists
  namespace: price-export
spec:
  schedule: "0 6 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 7
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 3
      activeDeadlineSeconds: 1800
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: export-job
            image: registry.example.com/export-job:latest
            envFrom:
            - configMapRef:
                name: export-job-config
            env:
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: export-job-secret
                  key: db-password
            resources:
              requests:
                cpu: 100m
                memory: 256Mi
              limits:
                cpu: 500m
                memory: 512Mi
```

**Артефакт:** директория `k8s/` с тремя YAML-файлами.

---

### Шаг 6. Интеграция с облачным хранилищем

**Цель:** настроить безопасный доступ Pod к GCS или S3 без статических ключей.

---

**Вариант A: GCS — Workload Identity (GKE)**

- Создать Google Service Account (GSA) с ролью `roles/storage.objectAdmin` на бакет:
  ```bash
  gcloud iam service-accounts create export-job-gsa \
    --display-name "Export Price Lists Job"
  gsutil iam ch serviceAccount:export-job-gsa@PROJECT.iam.gserviceaccount.com:objectAdmin \
    gs://my-bucket-price-lists
  ```
- Привязать GSA к Kubernetes ServiceAccount через Workload Identity:
  ```bash
  gcloud iam service-accounts add-iam-policy-binding \
    export-job-gsa@PROJECT.iam.gserviceaccount.com \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:PROJECT.svc.id.goog[price-export/export-job-sa]"
  ```
- Добавить аннотацию к K8s ServiceAccount в `k8s/namespace.yaml`:
  ```yaml
  annotations:
    iam.gke.io/gcp-service-account: export-job-gsa@PROJECT.iam.gserviceaccount.com
  ```
- Статические JSON-ключи не использовать — аутентификация через метадата-сервер GKE

---

**Вариант B: S3 — IRSA (EKS)**

- Создать IAM Policy с правами `s3:PutObject`, `s3:GetObject` на бакет:
  ```json
  {
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
    "Resource": ["arn:aws:s3:::my-bucket-price-lists/*"]
  }
  ```
- Создать IAM Role с trust policy для EKS OIDC-провайдера и привязать её к K8s ServiceAccount:
  ```bash
  eksctl create iamserviceaccount \
    --name export-job-sa \
    --namespace price-export \
    --cluster my-cluster \
    --attach-policy-arn arn:aws:iam::ACCOUNT:policy/ExportJobS3Policy \
    --approve
  ```
- Pod автоматически получит временные AWS-credentials через IRSA — `AWS_ACCESS_KEY_ID` и `AWS_SECRET_ACCESS_KEY` вручную не задавать

---

**Артефакт:** обновлённые `k8s/namespace.yaml` с аннотацией ServiceAccount; IAM-конфигурация в облаке.

---

### Шаг 7. Логирование — ELK интеграция

**Цель:** обеспечить централизованный сбор логов из Job Pod.

**Действия:**
- Убедиться, что приложение пишет логи в stdout в формате JSON (без файлов)
- Filebeat DaemonSet подхватывает stdout всех контейнеров автоматически — конфигурация не требуется, если Filebeat уже настроен в кластере
- Настроить Logstash-фильтр для парсинга JSON-логов и добавления поля `job: export-price-lists`
- В Kibana создать Index Pattern `filebeat-*` и сохранённый поиск по `kubernetes.labels.job-name: export-price-lists*`

**Артефакт:** Kibana Saved Search для фильтрации логов экспортного Job.

---

### Шаг 8. Мониторинг и алертинг

**Цель:** отслеживать успешность ежедневного экспорта и получать уведомления при сбоях.

**Действия:**

Grafana-дашборд (4 панели):
- Последнее время запуска CronJob: `kube_cronjob_status_last_schedule_time`
- Количество успешных Job за 7 дней: `sum(kube_job_status_succeeded) by (job_name)`
- Количество неуспешных Job за 7 дней: `sum(kube_job_status_failed) by (job_name)`
- Время выполнения: `kube_job_completion_time - kube_job_start_time`

Prometheus Alert Rule:
```yaml
groups:
- name: export-price-lists
  rules:
  - alert: ExportPriceListFailed
    expr: kube_job_status_failed{job_name=~"export-price-lists.*"} > 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Экспорт прайс-листов завершился с ошибкой"
      description: "Job {{ $labels.job_name }} завершился неуспешно"

  - alert: ExportPriceListNotRun
    expr: time() - kube_cronjob_status_last_schedule_time{cronjob="export-price-lists"} > 90000
    labels:
      severity: warning
    annotations:
      summary: "Экспорт прайс-листов не запускался более 25 часов"
```

**Артефакт:** `prometheus/rules/export-alerts.yaml` и JSON-экспорт Grafana-дашборда.

---

### Шаг 9. Тестирование и валидация

**Цель:** убедиться в корректности работы всей цепочки до вывода в продакшн.

**Действия:**
- Ручной запуск Job без ожидания расписания:
  ```bash
  kubectl create job --from=cronjob/export-price-lists manual-test-001 -n price-export
  ```
- Проверить статус выполнения:
  ```bash
  kubectl get job manual-test-001 -n price-export
  kubectl logs job/manual-test-001 -n price-export
  ```
- Проверить результат в Object Storage:
  - Наличие CSV-файла для каждого активного клиента
  - Корректность заголовков и количества строк
  - Кодировка UTF-8, разделитель `,`
- Проверить появление логов в Kibana (поиск по `job: export-price-lists`)
- Убедиться что метрики `kube_job_status_succeeded` обновились в Prometheus
- Проверить что Grafana-дашборд отображает результат последнего запуска

**Performance baseline — нагрузочная проверка:**
- Наполнить тестовую БД данными близкими к продакшн-объёму (10K строк в `products`, 20K в `client_prices`, 500 клиентов):
  ```bash
  kubectl exec -it postgres-pod -n price-export -- psql -U export_user -d pricelist \
    -c "INSERT INTO products SELECT generate_series(1,10000), ..."
  ```
- Запустить Job и замерить время:
  ```bash
  kubectl create job --from=cronjob/export-price-lists perf-test -n price-export
  kubectl logs job/perf-test -n price-export | grep '"level":"INFO"' | tail -1
  # Ожидаемый вывод: "duration_ms": <значение>
  ```
- Убедиться что суммарное время выполнения значительно меньше `activeDeadlineSeconds: 1800` (30 мин). Для 500 клиентов × 20 строк ожидается ~30–60 секунд
- Если время > 5 мин — рассмотреть параллелизацию (`parallelism` в Job spec) или переход на Spring Batch

**Артефакт:** отчёт о тестировании со скриншотами логов Kibana, Grafana-дашборда и результатами performance baseline.

---

## Ожидаемый результат

После реализации всех шагов:
- Каждое утро в 06:00 в Object Storage появляются CSV-файлы формата `price_list_{client_id}_{date}.csv`
- При сбое Job автоматически перезапускается (до 3 раз), команда получает alert в Alertmanager
- Логи каждого запуска доступны в Kibana с фильтрацией по Job
- Grafana-дашборд отображает историю и статус ежедневных запусков

## Риски и ограничения

| Риск | Митигация |
|------|-----------|
| PostgreSQL недоступен в момент запуска | `backoffLimit: 3` + alert при failed Job |
| Время выполнения > 30 мин при росте данных | `activeDeadlineSeconds: 1800`, мониторинг времени выполнения, при необходимости — переход на Spring Batch с чанкингом |
| Частичный экспорт (упал после нескольких клиентов) | Атомарная загрузка файлов — сначала в `/tmp`, затем в Storage; при повторном запуске файлы перезаписываются |
| Утечка учётных данных | Workload Identity вместо статических ключей; Secret не логируется |
