"""
logger.py
=========
로깅 유틸리티 모음.

핵심 기능
- ContextAdapter / with_context(): 모든 로그에 공통 컨텍스트(ctx) 자동 부착
- timeit(): 함수 실행시간(ms) 로깅 데코레이터(성공/실패 여부 포함)
- log_request(): 외부 API 호출 요약(메서드/URL/상태/재시도/대기시간 등)
- sampled(): 샘플링 로깅(고트래픽 환경에서 로그량 제어)

설계 포인트
- 포맷터는 record.ctx 를 기준으로 동작(텍스트→key=value, JSON→ctx 필드)
- LoggerAdapter.process에서 extra 병합을 일괄 처리
- 타입 힌트(ParamSpec/TypeVar)로 데코레이터의 시그니처 보존
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, Optional, Callable, TypeVar

# Python 3.10+는 typing.ParamSpec, 그 이하 버전은 typing_extensions 사용
try:
    from typing import ParamSpec  # type: ignore
except ImportError:  # pragma: no cover - 구버전 호환
    from typing_extensions import ParamSpec  # type: ignore

from .logging_config import safe_params

P = ParamSpec("P")
T = TypeVar("T")


# -----------------------------------------------------------------------------
# 컨텍스트 로거
# -----------------------------------------------------------------------------
class ContextAdapter(logging.LoggerAdapter):
    """
    LoggerAdapter는 모든 로그 호출에 'extra'를 주입할 수 있는 래퍼입니다.
    여기서는 'ctx' 라는 키로 컨텍스트 딕셔너리를 밀어 넣습니다.

    예)
        base_logger = get_logger(__name__)
        log = ContextAdapter(base_logger, {"svc": "fx-loader", "env": "dev"})
        log.info("start")  # -> record.ctx = {"svc": "...", "env": "..."}
    """

    def process(self, msg, kwargs):
        # 호출자가 추가로 extra를 준 경우 병합한다.
        # kwargs["extra"]는 dict여야 하며, 여기서는 {"ctx": {...}} 형태로 강제한다.
        extra_existing: Dict[str, Any] = kwargs.pop("extra", {}) or {}
        base_ctx: Dict[str, Any] = self.extra or {}
        # 기존 ctx와 호출 측 extra가 섞여 들어오면 병합
        # (충돌 시 호출 측 값이 우선하도록 merge 순서를 조정)
        merged = {**base_ctx, **extra_existing}
        # 포맷터는 record.ctx만 본다(일관성). KeyValue/JSON formatter가 처리.
        kwargs["extra"] = {"ctx": merged}
        return msg, kwargs


def with_context(logger: logging.Logger, **ctx) -> ContextAdapter:
    """
    로거에 컨텍스트를 바인딩합니다.
    사용 예)
        log = with_context(get_logger(__name__), svc="fx-loader", env="dev")
        log.info("hello")  # -> ctx가 자동 부착
    """
    return ContextAdapter(logger, ctx)


# -----------------------------------------------------------------------------
# 실행시간 측정 데코레이터
# -----------------------------------------------------------------------------
def timeit(logger: logging.Logger, label: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    함수 실행시간(ms)을 로깅하는 데코레이터.
    - 시작 시 DEBUG 레벨로 'start' 로그
    - 종료 시 INFO 레벨로 'done' 로그 + duration_ms + success(True/False)

    사용 예)
        @timeit(log, "load_fx_bundle")
        def load_fx_bundle(...):
            ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            t0 = time.perf_counter()
            logger.debug(f"{label} start")
            success = True
            try:
                return func(*args, **kwargs)
            except Exception:
                success = False
                # 예외는 상위로 그대로 던진다(로깅은 finally에서)
                raise
            finally:
                dt_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(
                    f"{label} done",
                    # 여기서 extra는 ContextAdapter가 병합하여 record.ctx에 넣는다.
                    extra={"duration_ms": round(dt_ms, 2), "success": success},
                )
        return wrapper
    return decorator


# -----------------------------------------------------------------------------
# HTTP 요청 요약 로깅
# -----------------------------------------------------------------------------
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
    additional_sensitive_keys: Optional[set[str]] = None,
) -> None:
    """
    외부 API 호출 전/후/재시도 시 공통적으로 쓰는 요약 로그.

    Parameters
    ----------
    logger : logging.Logger
        사용할 로거(보통 ContextAdapter 또는 get_logger(__name__))
    method : str
        HTTP 메서드("GET", "POST", ...)
    url : str
        요청 URL
    params : dict | None
        로그에 남길 파라미터(민감키는 safe_params로 마스킹)
    status : int | None
        응답 상태코드(재시도/성공/실패 시점에 남김)
    attempt : int | None
        재시도 카운트(0부터)
    wait_s : float | None
        백오프 대기시간(초)
    note : str | None
        임의의 코멘트("ok", "200 rows" 등)
    level : str
        로그 레벨("INFO", "WARNING", "ERROR"...)
    additional_sensitive_keys : set[str] | None
        추가로 마스킹할 민감 키(런타임 확장)
    """
    payload = {"method": method, "url": url}

    if params is not None:
        payload["params"] = safe_params(params, additional_sensitive_keys)
    if status is not None:
        payload["status"] = status
    if attempt is not None:
        payload["attempt"] = attempt
    if wait_s is not None:
        payload["wait_s"] = round(wait_s, 3)
    if note:
        payload["note"] = note

    lvl = getattr(logging, level.upper(), logging.INFO)
    # 전달받은 logger 그대로 사용(컨텍스트/이름 유지)
    logger.log(lvl, "http_call", extra=payload)


# -----------------------------------------------------------------------------
# 샘플링 로깅 (선택)
# -----------------------------------------------------------------------------
def sampled(logger: logging.Logger, p: float, level: str, msg: str, **extra) -> None:
    """
    확률 p(0.0~1.0)로만 로그를 남깁니다. 고트래픽 환경에서 로그 폭주 방지용.

    사용 예)
        sampled(log, 0.1, "INFO", "tick_event", symbol="BTCUSDT", price=...)
    """
    p = max(0.0, min(1.0, p))
    if random.random() < p:
        logger.log(getattr(logging, level.upper(), logging.INFO), msg, extra=extra)
