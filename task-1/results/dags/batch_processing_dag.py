"""
Batch Processing DAG — Apache Airflow POC
=========================================
Демонстрирует:
  1. Чтение данных из CSV-файла
  2. Анализ данных и ветвление пайплайна по условию
  3. Retry-политику для шагов обработки
  4. Email-уведомление при успешном и неуспешном завершении
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_DIR = Path("/opt/airflow/data")
PRODUCT_CSV = DATA_DIR / "product-data.csv"
LOYALITY_CSV = DATA_DIR / "loyality_data.csv"

# Threshold for branching: if record count > LARGE_DATASET_THRESHOLD
# we treat the dataset as "large" and use chunked processing
LARGE_DATASET_THRESHOLD = 3

DB_CONFIG = {
    "host": "postgres",
    "port": 5432,
    "dbname": "productsdb",
    "user": "postgres",
    "password": "123456",
}

NOTIFICATION_EMAIL = ["admin@example.com"]  # replace with real address

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Callbacks for email notifications
# ---------------------------------------------------------------------------

def on_failure_callback(context):
    """Called when any task in the DAG fails."""
    dag_id = context["dag"].dag_id
    task_id = context["task_instance"].task_id
    execution_date = context["execution_date"]
    log.error(
        "DAG '%s', task '%s' failed at %s. "
        "Check Airflow UI for details.",
        dag_id, task_id, execution_date,
    )
    # When SMTP is configured in .env, Airflow sends email automatically
    # because email_on_failure=True is set on the DAG.


# ---------------------------------------------------------------------------
# Task functions
# ---------------------------------------------------------------------------

def read_csv(**context):
    """Read product-data.csv and push records + count to XCom."""
    records = []
    with PRODUCT_CSV.open(newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:  # skip empty lines
                records.append(row)

    log.info("Прочитано %d записей из %s", len(records), PRODUCT_CSV)
    context["ti"].xcom_push(key="records", value=records)
    context["ti"].xcom_push(key="record_count", value=len(records))


def analyze_data(**context):
    """Log basic stats about the dataset."""
    records = context["ti"].xcom_pull(key="records", task_ids="read_csv")
    count = context["ti"].xcom_pull(key="record_count", task_ids="read_csv")
    log.info("=== Анализ данных ===")
    log.info("Всего записей: %d", count)
    for row in records:
        log.info("  product_id=%s, sku=%s, name=%s, amount=%s", *row[:4])


def branch_on_count(**context):
    """
    Ветвление пайплайна по количеству записей:
      - > LARGE_DATASET_THRESHOLD  → process_large
      - иначе                      → process_small
    """
    count = context["ti"].xcom_pull(key="record_count", task_ids="read_csv")
    log.info("Количество записей: %d (порог: %d)", count, LARGE_DATASET_THRESHOLD)
    if count > LARGE_DATASET_THRESHOLD:
        log.info("Переход на ветку: process_large")
        return "process_large"
    log.info("Переход на ветку: process_small")
    return "process_small"


def _load_loyality_map() -> dict[str, str]:
    """Helper: load loyalty data from CSV into a dict {sku: loyality_status}."""
    loyality = {}
    with LOYALITY_CSV.open(newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                loyality[row[0].strip()] = row[1].strip()
    return loyality


def _upsert_products(records: list, loyality: dict[str, str]) -> int:
    """Insert/update products in PostgreSQL. Returns number of rows inserted."""
    conn = psycopg2.connect(**DB_CONFIG)
    inserted = 0
    try:
        with conn:
            with conn.cursor() as cur:
                for row in records:
                    product_id, sku, name, amount, data = (
                        int(row[0]), row[1].strip(), row[2].strip(),
                        int(row[3]), row[4].strip(),
                    )
                    # Enrich with loyalty data
                    enriched_data = loyality.get(sku, data)
                    cur.execute(
                        """
                        INSERT INTO products (product_id, product_sku, product_name,
                                             product_amount, product_data)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (product_id) DO UPDATE
                          SET product_sku    = EXCLUDED.product_sku,
                              product_name   = EXCLUDED.product_name,
                              product_amount = EXCLUDED.product_amount,
                              product_data   = EXCLUDED.product_data;
                        """,
                        (product_id, sku, name, amount, enriched_data),
                    )
                    inserted += 1
        log.info("Загружено %d записей в таблицу products", inserted)
    finally:
        conn.close()
    return inserted


def process_large(**context):
    """
    Обработка большого датасета — чанковая запись в PostgreSQL.
    Retry: 3 раза с задержкой 1 мин.
    """
    records = context["ti"].xcom_pull(key="records", task_ids="read_csv")
    loyality = _load_loyality_map()
    log.info("[process_large] Обрабатываем %d записей чанками", len(records))
    chunk_size = 2
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        _upsert_products(chunk, loyality)
        log.info("  Обработан чанк %d-%d", i, i + len(chunk) - 1)


def process_small(**context):
    """
    Обработка малого датасета — одиночная запись в PostgreSQL.
    Retry: 3 раза с задержкой 1 мин.
    """
    records = context["ti"].xcom_pull(key="records", task_ids="read_csv")
    loyality = _load_loyality_map()
    log.info("[process_small] Обрабатываем %d записей", len(records))
    _upsert_products(records, loyality)


def notify_success(**context):
    """Log success message. Email sent automatically by Airflow (email_on_success=True)."""
    count = context["ti"].xcom_pull(key="record_count", task_ids="read_csv")
    log.info(
        "=== Пайплайн завершён успешно === "
        "Обработано записей: %d. Дата запуска: %s",
        count, context["execution_date"],
    )


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

default_args = {
    "owner": "tradeware",
    "depends_on_past": False,
    "email": NOTIFICATION_EMAIL,
    "email_on_failure": True,    # email при падении задачи
    "email_on_retry": True,      # email при retry
    "email_on_success": False,   # успех обрабатываем отдельной задачей
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "on_failure_callback": on_failure_callback,
}

with DAG(
    dag_id="batch_processing_dag",
    description="POC: пакетная обработка данных с ветвлением, retry и уведомлениями",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["poc", "batch", "tradeware"],
) as dag:

    # Step 1: Read CSV
    t_read = PythonOperator(
        task_id="read_csv",
        python_callable=read_csv,
    )

    # Step 2: Analyze
    t_analyze = PythonOperator(
        task_id="analyze_data",
        python_callable=analyze_data,
    )

    # Step 3: Branch
    t_branch = BranchPythonOperator(
        task_id="branch_on_count",
        python_callable=branch_on_count,
    )

    # Step 4a: Large dataset path
    t_large = PythonOperator(
        task_id="process_large",
        python_callable=process_large,
        retries=3,
        retry_delay=timedelta(minutes=1),
    )

    # Step 4b: Small dataset path
    t_small = PythonOperator(
        task_id="process_small",
        python_callable=process_small,
        retries=3,
        retry_delay=timedelta(minutes=1),
    )

    # Step 5: Join point after branching
    t_join = EmptyOperator(
        task_id="load_complete",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # Step 6: Success notification
    t_success = PythonOperator(
        task_id="notify_success",
        python_callable=notify_success,
    )

    # ---------------------------------------------------------------------------
    # Pipeline topology
    # ---------------------------------------------------------------------------
    t_read >> t_analyze >> t_branch
    t_branch >> t_large >> t_join
    t_branch >> t_small >> t_join
    t_join >> t_success
