#!/usr/bin/env python3
"""
Клиент для запуска Spring Batch ETL-задачи через REST API.
Реализует логирование с трейсингом (traceId, spanId, URI) в формате JSON.
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

import requests

# ─── Конфигурация ────────────────────────────────────────────────────────────

API_URL = os.getenv("BATCH_API_URL", "http://localhost:8080/api/jobs/trigger")

# ─── JSON-логгер с трейсингом ─────────────────────────────────────────────────

class JsonTraceFormatter(logging.Formatter):
    """Форматирует записи лога в JSON с полями traceId, spanId, uri."""

    def __init__(self, trace_id: str, span_id: str, uri: str):
        super().__init__()
        self.trace_id = trace_id
        self.span_id = span_id
        self.uri = uri

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "uri": self.uri,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log_entry["stack"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def build_logger(name: str, trace_id: str, span_id: str, uri: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonTraceFormatter(trace_id, span_id, uri))
        logger.addHandler(handler)
    return logger


# ─── Основная логика ──────────────────────────────────────────────────────────

def trigger_batch_job() -> None:
    # Генерация trace context в формате B3 (Zipkin)
    trace_id = uuid.uuid4().hex  # 128-bit hex
    span_id = uuid.uuid4().hex[:16]  # 64-bit hex

    logger = build_logger("job-client", trace_id, span_id, API_URL)

    # Заголовки с B3-трейсингом для пропагации контекста на сервер
    headers = {
        "Content-Type": "application/json",
        "X-B3-TraceId": trace_id,
        "X-B3-SpanId": span_id,
        "X-B3-Sampled": "1",
    }

    logger.info(
        "Отправка запроса на запуск Batch-задачи | method=POST url=%s traceId=%s spanId=%s",
        API_URL, trace_id, span_id,
    )

    try:
        response = requests.post(API_URL, headers=headers, timeout=120)
        response.raise_for_status()

        body = response.json()
        logger.info(
            "Batch-задача успешно запущена | status=%s jobExecutionId=%s jobStatus=%s",
            response.status_code,
            body.get("jobExecutionId"),
            body.get("status"),
        )

        # Вывод полного ответа в виде JSON для наглядности
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceId": trace_id,
            "spanId": span_id,
            "uri": API_URL,
            "httpStatus": response.status_code,
            "response": body,
        }, indent=2, ensure_ascii=False))

    except requests.exceptions.ConnectionError as e:
        logger.error("Не удалось подключиться к серверу: %s", e)
        sys.exit(1)
    except requests.exceptions.Timeout:
        logger.error("Превышено время ожидания ответа от сервера (120 сек)")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        logger.error(
            "Сервер вернул ошибку | status=%s body=%s",
            e.response.status_code, e.response.text,
        )
        sys.exit(1)


if __name__ == "__main__":
    trigger_batch_job()
