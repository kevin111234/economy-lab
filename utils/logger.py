"""
logger.py
- 컨텍스트 바인딩(LoggerAdapter)
- 실행시간 측정 데코레이터(timeit)
- 외부 HTTP 요청 요약 로깅(log_request)
"""

from __future__ import annotations
import time
import logging
from typing import Any, Dict, Optional, Callable
from .logging_config import safe_params


# -------------------------------
# 컨텍스트 로거 (LoggerAdapter)
# -------------------------------
class ContextAdapter(logging.LoggerAdapter):
    """
    LoggerAdapter는 'extra' 컨텍스트를 모든 로그에 주입한다.
    텍스트 포맷(KeyValueFormatter)에서는 message 뒤에 key=value로 붙고,
    JSON 포맷(JSONFormatter)에서는 record.ctx 필드로 직렬화된다.
    """
    def process(self, msg, kwargs):
        # 기존 호출자가 extra를 같이 넘겨준 경우 병합
        ctx_existing: Dict[str, Any] = kwargs.pop("extra", {}) or {}
        merged = {**self.extra, **ctx_existing}
        # record.ctx로 전달하여 포맷터가 처리하게 함
        kwargs["extra"] = {"ctx": merged}
        return msg, kwargs


def with_context(logger: logging.Logger, **ctx) -> ContextAdapter:
    """
    예) log = with_context(get_logger(__name__), svc="fx-loader", env="dev")
    이후 log.info("start") → ctx가 자동으로 붙음.
    """
    return ContextAdapter(logger, ctx)


# -------------------------------
# 실행시간 측정 데코레이터
# -------------------------------
def timeit(logger: logging.Logger, label: str) -> Callable:
    """
    @timeit(log, "load_fx_bundle")
    def load_fx_bundle(...):
        ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            logger.debug(f"{label} start")
            try:
                return func(*args, **kwargs)
            finally:
                dt_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(f"{label} done", extra={"duration_ms": round(dt_ms, 2)})
        return wrapper
    return decorator


# -------------------------------
# HTTP 요청 요약 로깅
# -------------------------------
def log_request(
    logger: logging.Logger,
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    status: Optional[int] = None,
    attempt: Optional[int] = None,
    wait_s: Optional[float] = None,
    note: Optional[str] = None,
    level: str = "INFO",
) -> None:
    """
    외부 API 호출 전/후/재시도 시 공통적으로 쓰는 요약 로그.
    - 민감 값은 safe_params로 마스킹
    - level로 로그 레벨 선택

    예)
      log_request(log, "GET", url, params=p, level="INFO")
      log_request(log, "GET", url, status=429, attempt=1, wait_s=2.1, level="WARNING")
      log_request(log, "GET", url, status=200, note="200 rows")
    """
    payload = {
        "method": method,
        "url": url,
    }
    if params is not None:
        payload["params"] = safe_params(params)
    if status is not None:
        payload["status"] = status
    if attempt is not None:
        payload["attempt"] = attempt
    if wait_s is not None:
        payload["wait_s"] = round(wait_s, 3)
    if note:
        payload["note"] = note

    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger(logger.name).log(lvl, "http_call", extra=payload)
