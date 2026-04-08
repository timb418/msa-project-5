# Task 4 — Дамп реального запуска Spring Batch ETL

Все данные получены при живом запуске на локальной машине (WSL2, Docker).
Дата запуска: 2026-04-07.

---

## Шаг 1. Сборка JAR (gradle build)

```
$ docker run --rm -v "$(pwd)":/app -w /app gradle:8.8-jdk17 gradle build --no-daemon

To honour the JVM settings for this build a single-use Daemon process will be forked.
Daemon will be stopped at the end of the build

> Task :compileJava
> Task :processResources
> Task :classes
> Task :resolveMainClassName
> Task :bootJar
> Task :jar
> Task :assemble
> Task :compileTestJava NO-SOURCE
> Task :processTestResources NO-SOURCE
> Task :testClasses UP-TO-DATE
> Task :test NO-SOURCE
> Task :check UP-TO-DATE
> Task :build

Deprecated Gradle features were used in this build, making it incompatible with Gradle 9.0.

BUILD SUCCESSFUL in 48s
5 actionable tasks: 5 executed
```

---

## Шаг 2. Запуск docker-compose

```
$ docker-compose up --build -d

 Image batch-processing Building
 ...
 Image batch-processing Built
 Network complete_default Creating
 Network complete_default Created
 Container complete-postgresdb-1 Creating
 Container complete-postgresdb-1 Created
 Container complete-app-1 Creating
 Container complete-app-1 Created
 Container complete-postgresdb-1 Starting
 Container complete-postgresdb-1 Started
 Container complete-app-1 Starting
 Container complete-app-1 Started
```

---

## Шаг 3. Создание таблиц (schema-all.sql)

```
$ docker exec -i complete-postgresdb-1 psql -U postgres -d productsdb < schema-all.sql

CREATE TABLE
CREATE TABLE
```

Проверка списка таблиц (`\dt`):

```
                 List of relations
 Schema |             Name             | Type  |  Owner
--------+------------------------------+-------+----------
 public | batch_job_execution          | table | postgres
 public | batch_job_execution_context  | table | postgres
 public | batch_job_execution_params   | table | postgres
 public | batch_job_instance           | table | postgres
 public | batch_step_execution         | table | postgres
 public | batch_step_execution_context | table | postgres
 public | loyality_data                | table | postgres
 public | products                     | table | postgres
(8 rows)
```

> Таблицы `products` и `loyality_data` — созданы вручную из `schema-all.sql`.
> Таблицы `batch_*` — созданы автоматически Spring Batch при первом старте приложения.

---

## Шаг 4. Наполнение таблицы loyality_data

```sql
INSERT INTO loyality_data (productSku, loyalityData) VALUES
  (20001, 'Loyality_on'),
  (30001, 'Loyality_on'),
  (50001, 'Loyality_on'),
  (60001, 'Loyality_on');
```

```
INSERT 0 4
```

```sql
SELECT * FROM loyality_data;
```

```
 productsku | loyalitydata
------------+--------------
      20001 | Loyality_on
      30001 | Loyality_on
      50001 | Loyality_on
      60001 | Loyality_on
(4 rows)
```

---

## Шаг 5. Логи успешного запуска приложения (Spring Boot started)

```
  .   ____          _            __ _ _
 /\\ / ___'_ __ _ _(_)_ __  __ _ \ \ \ \
( ( )\___ | '_ | '_| | '_ \/ _` | \ \ \ \
 \\/  ___)| |_)| | | | | || (_| |  ) ) ) )
  '  |____| .__|_| |_|_| |_\__, | / / / /
 =========|_|==============|___/=/_/_/_/

 :: Spring Boot ::                (v3.5.3)

2026-04-07T20:40:13.859Z  INFO 1 --- [           main] c.e.b.BatchProcessingApplication         : Starting BatchProcessingApplication v0.0.1-SNAPSHOT using Java 17.0.11 with PID 1 (/app/app.jar started by root in /app)
2026-04-07T20:40:13.864Z  INFO 1 --- [           main] c.e.b.BatchProcessingApplication         : No active profile set, falling back to 1 default profile: "default"
2026-04-07T20:40:14.552Z  INFO 1 --- [           main] com.zaxxer.hikari.HikariDataSource       : HikariPool-1 - Starting...
2026-04-07T20:40:14.713Z  INFO 1 --- [           main] com.zaxxer.hikari.pool.HikariPool        : HikariPool-1 - Added connection org.postgresql.jdbc.PgConnection@50194e8d
2026-04-07T20:40:14.714Z  INFO 1 --- [           main] com.zaxxer.hikari.HikariDataSource       : HikariPool-1 - Start completed.
2026-04-07T20:40:15.003Z  INFO 1 --- [           main] c.e.b.BatchProcessingApplication         : Started BatchProcessingApplication in 1.563 seconds (process running for 1.971)
```

---

## Шаг 6. Запуск Spring Batch Job

```
2026-04-07T20:40:15.007Z  INFO 1 --- [           main] o.s.b.a.b.JobLauncherApplicationRunner   : Running default command line with: []
2026-04-07T20:40:15.067Z  INFO 1 --- [           main] o.s.b.c.l.s.TaskExecutorJobLauncher      : Job: [SimpleJob: [name=importProductJob]] launched with the following parameters: [{}]
2026-04-07T20:40:15.099Z  INFO 1 --- [           main] o.s.batch.core.job.SimpleStepHandler     : Executing step: [step1]
```

---

## Шаг 7. Логи трансформации (ProductItemProcessor)

```
2026-04-07T20:40:15.126Z  INFO 1 --- [           main] c.e.b.ProductItemProcessor               : Transforming (Product[productId=1, productSku=20001, productName=hammer, productAmount=45, productData=Loyality_off]) into (Product[productId=1, productSku=20001, productName=hammer, productAmount=45, productData=Loyality_on])
2026-04-07T20:40:15.134Z  INFO 1 --- [           main] c.e.b.ProductItemProcessor               : Transforming (Product[productId=2, productSku=30001, productName=sink, productAmount=20, productData=Loyality_off]) into (Product[productId=2, productSku=30001, productName=sink, productAmount=20, productData=Loyality_on])
2026-04-07T20:40:15.136Z  INFO 1 --- [           main] c.e.b.ProductItemProcessor               : Transforming (Product[productId=3, productSku=40001, productName=roof_shell, productAmount=256, productData=Loyality_on]) into (Product[productId=3, productSku=40001, productName=roof_shell, productAmount=256, productData=Loyality_on])
2026-04-07T20:40:15.152Z  INFO 1 --- [           main] c.e.b.ProductItemProcessor               : Transforming (Product[productId=4, productSku=50001, productName=priming, productAmount=67, productData=Loyality_off]) into (Product[productId=4, productSku=50001, productName=priming, productAmount=67, productData=Loyality_on])
2026-04-07T20:40:15.154Z  INFO 1 --- [           main] c.e.b.ProductItemProcessor               : Transforming (Product[productId=5, productSku=60001, productName=clapboard, productAmount=120, productData=Loyality_on]) into (Product[productId=5, productSku=60001, productName=clapboard, productAmount=120, productData=Loyality_on])
```

> `hammer` (SKU 20001): Loyality_off → Loyality_on (найден в loyality_data)
> `sink` (SKU 30001): Loyality_off → Loyality_on (найден в loyality_data)
> `roof_shell` (SKU 40001): без изменений — SKU отсутствует в loyality_data
> `priming` (SKU 50001): Loyality_off → Loyality_on (найден в loyality_data)
> `clapboard` (SKU 60001): без изменений — уже Loyality_on

---

## Шаг 8. Завершение Job (JobCompletionNotificationListener)

```
2026-04-07T20:40:15.160Z  INFO 1 --- [           main] o.s.batch.core.step.AbstractStep         : Step: [step1] executed in 60ms
2026-04-07T20:40:15.169Z  INFO 1 --- [           main] c.e.b.JobCompletionNotificationListener  : !!! JOB FINISHED! Time to verify the results
2026-04-07T20:40:15.172Z  INFO 1 --- [           main] c.e.b.JobCompletionNotificationListener  : Transformed <Product[productId=1, productSku=20001, productName=hammer, productAmount=45, productData=Loyality_on]> in the database.
2026-04-07T20:40:15.172Z  INFO 1 --- [           main] c.e.b.JobCompletionNotificationListener  : Transformed <Product[productId=2, productSku=30001, productName=sink, productAmount=20, productData=Loyality_on]> in the database.
2026-04-07T20:40:15.172Z  INFO 1 --- [           main] c.e.b.JobCompletionNotificationListener  : Transformed <Product[productId=3, productSku=40001, productName=roof_shell, productAmount=256, productData=Loyality_on]> in the database.
2026-04-07T20:40:15.173Z  INFO 1 --- [           main] c.e.b.JobCompletionNotificationListener  : Transformed <Product[productId=4, productSku=50001, productName=priming, productAmount=67, productData=Loyality_on]> in the database.
2026-04-07T20:40:15.173Z  INFO 1 --- [           main] c.e.b.JobCompletionNotificationListener  : Transformed <Product[productId=5, productSku=60001, productName=clapboard, productAmount=120, productData=Loyality_on]> in the database.
2026-04-07T20:40:15.180Z  INFO 1 --- [           main] o.s.b.c.l.s.TaskExecutorJobLauncher      : Job: [SimpleJob: [name=importProductJob]] completed with the following parameters: [{}] and the following status: [COMPLETED] in 93ms
2026-04-07T20:40:15.185Z  INFO 1 --- [           main] com.zaxxer.hikari.HikariDataSource       : HikariPool-1 - Shutdown initiated...
2026-04-07T20:40:15.197Z  INFO 1 --- [           main] com.zaxxer.hikari.HikariDataSource       : HikariPool-1 - Shutdown completed.
```

---

## Шаг 9. Данные в таблице products после ETL

```sql
SELECT * FROM products ORDER BY productid;
```

```
 productid | productsku | productname | productamount | productdata
-----------+------------+-------------+---------------+-------------
         1 |      20001 | hammer      |            45 | Loyality_on
         2 |      30001 | sink        |            20 | Loyality_on
         3 |      40001 | roof_shell  |           256 | Loyality_on
         4 |      50001 | priming     |            67 | Loyality_on
         5 |      60001 | clapboard   |           120 | Loyality_on
(5 rows)
```

Все 5 записей из `product-data.csv` успешно загружены. Поле `productdata` обновлено данными из `loyality_data`.

---

## Шаг 10. Метаданные Job в таблицах Spring Batch

```sql
SELECT job_execution_id, job_instance_id, create_time, start_time, end_time, status, exit_code
FROM batch_job_execution
ORDER BY create_time;
```

```
 job_execution_id | job_instance_id |        create_time         |         start_time         |          end_time          |  status   | exit_code
------------------+-----------------+----------------------------+----------------------------+----------------------------+-----------+-----------
                1 |               1 | 2026-04-07 20:38:42.991392 | 2026-04-07 20:38:43.012337 | 2026-04-07 20:38:43.087413 | FAILED    | FAILED
                2 |               1 | 2026-04-07 20:40:15.057842 | 2026-04-07 20:40:15.076496 | 2026-04-07 20:40:15.169796 | COMPLETED | COMPLETED
(2 rows)
```

> Первый запуск (execution_id=1) завершился с FAILED — таблицы ещё не были созданы.
> Второй запуск (execution_id=2) завершился с COMPLETED после создания таблиц и наполнения loyality_data.

```sql
SELECT step_execution_id, step_name, start_time, end_time, status, read_count, write_count, exit_code
FROM batch_step_execution
ORDER BY start_time;
```

```
 step_execution_id | step_name |         start_time         |          end_time          |  status   | read_count | write_count | exit_code
-------------------+-----------+----------------------------+----------------------------+-----------+------------+-------------+-----------
                 1 | step1     | 2026-04-07 20:38:43.029103 | 2026-04-07 20:38:43.075928 | FAILED    |          3 |           0 | FAILED
                 2 | step1     | 2026-04-07 20:40:15.100049 | 2026-04-07 20:40:15.160640 | COMPLETED |          5 |           5 | COMPLETED
(2 rows)
```

> `read_count=5` — прочитано 5 строк из CSV.
> `write_count=5` — записано 5 строк в таблицу `products`.
> Время выполнения step1: ~60ms.
