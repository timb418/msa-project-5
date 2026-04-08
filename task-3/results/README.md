# Задание 3. Distributed Scheduling с k8s CronJob

## Описание решения

Для ежедневной выгрузки аналитических данных по перевозкам выбран **k8s CronJob** — нативный механизм Kubernetes для запуска задач по расписанию. Задача запускается каждый день в **20:00 UTC** и экспортирует таблицу `shipments` из PostgreSQL в CSV-файл.

### Архитектура (To Be)

```
┌─────────────────────────────────────────────────────┐
│                    Kubernetes (Minikube)             │
│                                                     │
│  ┌──────────────────────┐                           │
│  │  БД аналитики по     │                           │
│  │  перевозкам          │                           │
│  │  [PostgreSQL]        │                           │
│  │  Данные за день      │                           │
│  └──────────┬───────────┘                           │
│             │                                       │
│             ▼                                       │
│  ┌──────────────────────┐                           │
│  │  Задача по выгрузке  │                           │
│  │  данных              │                           │
│  │  [k8s CronJob]       │                           │
│  │  Ежедневно в 20:00   │                           │
│  └──────────┬───────────┘                           │
│             │                                       │
└─────────────┼───────────────────────────────────────┘
              ▼
         CSV files
   (PersistentVolumeClaim)
```

### Компоненты

| Компонент | Описание |
|-----------|----------|
| `export_job/export.py` | Python-скрипт: подключается к PostgreSQL, экспортирует таблицу `shipments` в CSV |
| `export_job/Dockerfile` | Docker-образ на базе `python:3.11-slim` |
| `k8s/namespace.yaml` | Namespace `logistics` |
| `k8s/postgres-secret.yaml` | Учётные данные PostgreSQL (base64) |
| `k8s/postgres-configmap.yaml` | Конфигурация подключения и init.sql |
| `k8s/postgres-pvc.yaml` | PVC 1Gi для данных PostgreSQL |
| `k8s/postgres-deployment.yaml` | Deployment PostgreSQL 15 |
| `k8s/postgres-service.yaml` | ClusterIP-сервис для PostgreSQL |
| `k8s/export-pvc.yaml` | PVC 1Gi для сохранения CSV-файлов |
| `k8s/cronjob.yaml` | CronJob с расписанием `0 20 * * *` |

---

## Предварительные требования

- [Minikube](https://minikube.sigs.k8s.io/docs/start/) v1.30+
- [kubectl](https://kubernetes.io/docs/tasks/tools/) v1.27+
- [Docker](https://docs.docker.com/get-docker/) v24+
- (Опционально) [Docker Compose](https://docs.docker.com/compose/) v2+ — для локального тестирования

---

## Часть 1: Локальное тестирование (Docker Compose)

Перед деплоем в Minikube можно убедиться, что скрипт работает корректно.

```bash
# Из корня task-3/
cd task-3

# Запускаем PostgreSQL + выполняем экспорт
docker compose up --build

# Ожидаемый вывод export_job:
# ... [INFO] Connecting to PostgreSQL at postgres:5432/logistics_db
# ... [INFO] Running SELECT * FROM shipments
# ... [INFO] Exporting 20 rows to /data/exports/shipments_2026-04-07.csv
# ... [INFO] Export completed successfully: /data/exports/shipments_2026-04-07.csv

# Остановка
docker compose down -v
```

---

## Часть 2: Деплой в Minikube

### Шаг 1. Запуск Minikube

```bash
minikube start --driver=docker
```

Проверить статус:

```bash
minikube status
```

Ожидаемый вывод:
```
minikube
type: Control Plane
host: Running
kubelet: Running
apiserver: Running
kubeconfig: Configured
```

### Шаг 2. Настройка Docker на Minikube

Чтобы собранный образ был доступен внутри кластера без push в registry:

```bash
# Linux / macOS
eval $(minikube docker-env)

# Windows (PowerShell)
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
```

> **Важно:** все последующие команды `docker build` нужно выполнять в том же терминале.

### Шаг 3. Сборка Docker-образа

```bash
# Из корня task-3/
docker build -t logistics-export:1.0 ./export_job/
```

Проверить, что образ появился в Minikube:

```bash
docker images | grep logistics-export
```

Ожидаемый вывод:
```
logistics-export   1.0   abc123def456   ...   ...
```

### Шаг 4. Применение манифестов Kubernetes

Сначала создаём namespace — он должен существовать до применения остальных ресурсов:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
```

Ожидаемый вывод второй команды:
```
namespace/logistics unchanged
secret/postgres-secret created
configmap/postgres-config created
configmap/postgres-init-sql created
persistentvolumeclaim/postgres-pvc created
deployment.apps/postgres created
service/postgres created
persistentvolumeclaim/export-pvc created
cronjob.batch/shipments-export created
```

### Шаг 5. Ожидание готовности PostgreSQL

```bash
kubectl rollout status deployment/postgres -n logistics
```

Ожидаемый вывод:
```
deployment "postgres" successfully rolled out
```

Дополнительная проверка:

```bash
kubectl get pods -n logistics
```

Ожидаемый вывод (STATUS = Running):
```
NAME                        READY   STATUS    RESTARTS   AGE
postgres-7d8b9f6c5d-xk2pq   1/1     Running   0          45s
```

---

## Часть 3: Проверка работы CronJob

### Просмотр CronJob

```bash
kubectl get cronjob -n logistics
```

Ожидаемый вывод:
```
NAME               SCHEDULE    SUSPEND   ACTIVE   LAST SCHEDULE   AGE
shipments-export   0 20 * * *  False     0        <none>          1m
```

### Ручной запуск для тестирования

Не дожидаясь расписания, запускаем Job вручную:

```bash
kubectl create job --from=cronjob/shipments-export manual-test-01 -n logistics
```

Наблюдаем за выполнением:

```bash
# Статус Job
kubectl get jobs -n logistics -w

# Дождаться COMPLETIONS = 1/1:
# NAME              COMPLETIONS   DURATION   AGE
# manual-test-01    1/1           8s         15s
```

### Просмотр логов

```bash
kubectl logs -l job-name=manual-test-01 -n logistics
```

Ожидаемый вывод:
```
2026-04-07 20:00:01,234 [INFO] Connecting to PostgreSQL at postgres:5432/logistics_db
2026-04-07 20:00:01,456 [INFO] Running SELECT * FROM shipments
2026-04-07 20:00:01,512 [INFO] Exporting 20 rows to /data/exports/shipments_2026-04-07.csv
2026-04-07 20:00:01,534 [INFO] Export completed successfully: /data/exports/shipments_2026-04-07.csv
```

### Проверка CSV-файла

Запускаем временный Pod, который монтирует тот же PVC:

```bash
kubectl run csv-reader \
  --image=busybox \
  --restart=Never \
  --rm -it \
  -n logistics \
  --overrides='{
    "spec": {
      "volumes": [{"name": "export-data", "persistentVolumeClaim": {"claimName": "export-pvc"}}],
      "containers": [{
        "name": "csv-reader",
        "image": "busybox",
        "command": ["sh"],
        "stdin": true,
        "tty": true,
        "volumeMounts": [{"name": "export-data", "mountPath": "/data/exports"}]
      }]
    }
  }'
```

Внутри контейнера:

```sh
ls /data/exports/
cat /data/exports/shipments_$(date +%Y-%m-%d).csv
exit
```

Ожидаемый вывод `ls`:
```
shipments_2026-04-07.csv
```

Ожидаемый вывод `cat` (первые строки):
```
id,shipment_date,origin,destination,driver_id,vehicle_id,client_id,status,weight_kg,created_at
1,2026-04-01,Москва,Санкт-Петербург,1,101,201,delivered,1250.00,2026-04-07 ...
2,2026-04-01,Екатеринбург,Новосибирск,2,102,202,delivered,870.50,2026-04-07 ...
...
```

---

## Часть 4: Проверка БД через psql

```bash
# Получить имя пода PostgreSQL
POSTGRES_POD=$(kubectl get pod -n logistics -l app=postgres -o jsonpath='{.items[0].metadata.name}')

# Подключиться к psql
kubectl exec -it $POSTGRES_POD -n logistics -- psql -U logistics -d logistics_db

# Внутри psql:
\dt
SELECT count(*) FROM shipments;
SELECT * FROM shipments LIMIT 5;
\q
```

---

## Очистка ресурсов

```bash
# Удалить все ресурсы namespace
kubectl delete namespace logistics

# Остановить Minikube (данные сохраняются)
minikube stop

# Полное удаление Minikube (если нужно)
minikube delete
```
