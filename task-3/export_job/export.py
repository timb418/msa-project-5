import csv
import logging
import os
import sys
from datetime import date

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
TABLE_NAME = os.environ.get("TABLE_NAME", "shipments")
EXPORT_DIR = os.environ.get("EXPORT_DIR", "/data/exports")


def export_table():
    os.makedirs(EXPORT_DIR, exist_ok=True)

    filename = f"{TABLE_NAME}_{date.today().isoformat()}.csv"
    filepath = os.path.join(EXPORT_DIR, filename)

    logger.info("Connecting to PostgreSQL at %s:%s/%s", DB_HOST, DB_PORT, DB_NAME)
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    try:
        with conn.cursor() as cur:
            logger.info("Running SELECT * FROM %s", TABLE_NAME)
            cur.execute(f"SELECT * FROM {TABLE_NAME}")  # noqa: S608
            rows = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]

        logger.info("Exporting %d rows to %s", len(rows), filepath)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(col_names)
            writer.writerows(rows)

        logger.info("Export completed successfully: %s", filepath)
    finally:
        conn.close()


if __name__ == "__main__":
    export_table()
