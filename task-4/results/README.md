# Task 4 — Реализация ETL с использованием Spring Batch

## Состав результатов

| Файл | Описание |
|------|----------|
| `ADR.md` | Архитектурное решение (ADR): обоснование выбора Spring Batch, функциональные и нефункциональные требования, сравнение с альтернативами, риски |
| `c4-diagram-tobe.drawio` | C4-диаграмма архитектуры To Be с внедрённым компонентом Spring Batch. Открывать в [draw.io](https://app.diagrams.net/) |
| `screenshots-guide.md` | Пошаговое руководство по воспроизведению и скриншотированию работы решения |

## Ссылки на реализацию

Исходный код Spring Batch-приложения находится в директории `../complete/`:

```
task-4/complete/
├── docker-compose.yml                   — запуск PostgreSQL + приложения
├── Dockerfile                           — сборка Docker-образа
├── src/main/java/com/example/batchprocessing/
│   ├── BatchConfiguration.java          — конфигурация Job, Step, Reader, Writer
│   ├── ProductItemProcessor.java        — логика обогащения (Transform)
│   ├── JobCompletionNotificationListener.java — логирование результата
│   ├── Product.java                     — модель товара
│   └── Loyality.java                    — модель данных лояльности
└── src/main/resources/
    ├── product-data.csv                 — входные данные (5 товаров)
    ├── loyality_data.csv                — данные программы лояльности
    └── schema-all.sql                   — DDL для создания таблиц вручную
```

## Быстрый старт

```bash
cd task-4/complete
./gradlew build
docker-compose up --build
```

Перед первым запуском вручную создай таблицы через psql, используя `schema-all.sql`,
и наполни `loyality_data` данными из `loyality_data.csv`.
Подробные шаги — в `screenshots-guide.md`.
