"""
logging_config.py
=================
프로세스 전역 로깅 설정을 담당합니다.

핵심 기능
- setup_logging(): 루트 로거에 콘솔/파일 핸들러를 장착하고 포맷(텍스트/JSON)을 결정
- KeyValueFormatter: 텍스트 기반 '시간 | 레벨 | 로거명 | 메시지 | key=value ...'
- JSONFormatter: 한 줄 JSON 라인 로깅(ELK/CloudWatch 적재 편리)
- safe_params(): 로그에 남기기 전 민감 키 자동 마스킹
- get_logger(): 모듈/패키지 단위 로거 획득

설계 포인트
- '한 번만' 초기화되도록 _initialized 플래그로 중복 방지
- JSON 포맷 시 공통 메타(host, pid, thread)를 자동 포함
- record.ctx 만 사용(포맷터 일관성)
"""

from __future__ import annotations

import json
import logging
import os
import socket
from logging import Logger
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional, Set


# -----------------------------------------------------------------------------
# 내부 상태: 중복 초기화 방지 플래그
# -----------------------------------------------------------------------------
_initialized = False


# -----------------------------------------------------------------------------
# 레벨 문자열 → 숫자 매핑
# -----------------------------------------------------------------------------
_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _to_level(level: str | int) -> int:
    """
    레벨을 숫자형으로 변환합니다.
    - 숫자를 그대로 주면 그대로 반환
    - 문자열이면 대문자로 바꿔 매핑 테이블 조회
    - 매핑 실패 시 INFO 기본값
    """
    if isinstance(level, int):
        return level
    return _LEVELS.get(str(level).upper(), logging.INFO)


# -----------------------------------------------------------------------------
# 민감정보 마스킹
# -----------------------------------------------------------------------------
# 기본적으로 마스킹할 키(대소문자 무시): 필요 시 setup_logging(extra_sensitive_keys=...)로 확장 가능
_SENSITIVE_KEYS_DEFAULT: Set[str] = {
    "api_key", "apikey", "apisecret", "secret",
    "token", "authorization", "password", "passwd",
    "x-api-key", "x-auth-token",
}


def safe_params(
    params: Optional[Dict[str, Any]],
    additional_keys: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    요청 파라미터(쿼리/바디)를 로그로 남기기 전에 민감 키를 *** 로 마스킹합니다.

    Parameters
    ----------
    params : dict | None
        로그로 남길 딕셔너리(보통 요청 파라미터)
    additional_keys : set[str] | None
        런타임에 추가로 마스킹하고 싶은 키들(대소문자 무시)

    Returns
    -------
    dict | None
        마스킹된 새 딕셔너리. dict가 아니면 원본 그대로 반환.
    """
    if not isinstance(params, dict):
        return params

    # 민감 키 집합 구성(기본 + 추가)
    sensitive = {k.lower() for k in _SENSITIVE_KEYS_DEFAULT}
    if additional_keys:
        sensitive |= {k.lower() for k in additional_keys}

    redacted: Dict[str, Any] = {}
    for k, v in params.items():
        redacted[k] = "***" if k.lower() in sensitive else v
    return redacted


# -----------------------------------------------------------------------------
# 포맷터: 텍스트 / JSON
# -----------------------------------------------------------------------------
class KeyValueFormatter(logging.Formatter):
    """
    텍스트 포맷터.
    - 기본 포맷: "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    - record.ctx(dict)가 있으면 message 뒤에 'key=value key=value ...'를 덧붙임
    """

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        ctx = getattr(record, "ctx", None)

        if not (isinstance(ctx, dict) and ctx):
            return base

        # 스택트레이스가 포함된 경우 base는 여러 줄입니다.
        lines = base.splitlines()
        head = lines[0]
        tail = lines[1:]

        # 첫 줄에만 ctx를 key=value로 부착
        kv = " ".join(f"{k}={v}" for k, v in ctx.items())
        head_with_ctx = f"{head} | {kv}"

        return "\n".join([head_with_ctx, *tail]) if tail else head_with_ctx

class JSONFormatter(logging.Formatter):
    """
    JSON 라인 포맷터.
    - 모든 로그를 한 줄 JSON으로 직렬화
    - 공통 메타(호스트명/프로세스ID/스레드명) 자동 포함
    - record.ctx(dict)가 있으면 'ctx' 필드에 포함
    - 예외가 있으면 'exc_info'에 스택 문자열 포함
    """
    _host = socket.gethostname()

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),  # ISO가 필요하면 datefmt/Converter 커스텀
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "host": self._host,
            "pid": record.process,
            "thread": record.threadName,
        }
        ctx = getattr(record, "ctx", None)
        if isinstance(ctx, dict) and ctx:
            payload["ctx"] = ctx
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


# -----------------------------------------------------------------------------
# 로깅 초기화: 애플리케이션 시작 시 '한 번만' 호출
# -----------------------------------------------------------------------------
def setup_logging(
    log_path: Optional[str] = "logs/app.log",
    level: str | int = "INFO",
    json_format: bool = False,
    rotate: bool = True,
    max_bytes: int = 5_000_000,
    backup_count: int = 3,
    propagate_root: bool = False,
    # ↓ 추가 민감 키를 설정에서 주입할 수 있게 함
    extra_sensitive_keys: Optional[Set[str]] = None,
) -> None:
    """
    루트 로거에 콘솔/파일 핸들러를 장착하고, 포맷(텍스트/JSON)을 설정합니다.

    Parameters
    ----------
    log_path : str | None
        파일 로깅 경로. None이면 파일 핸들러를 추가하지 않음(콘솔만).
    level : str | int
        로그 레벨("INFO", "DEBUG", ...) 또는 숫자 상수(logging.INFO 등)
    json_format : bool
        True면 JSON 라인 로깅, False면 텍스트 포맷
    rotate : bool
        True면 회전 파일 핸들러(RotatingFileHandler) 사용
    max_bytes : int
        회전 파일 용량(바이트)
    backup_count : int
        회전 파일 백업 개수
    propagate_root : bool
        루트 로거를 상위 로거에 전파할지 여부(일반적으로 False 권장)
    extra_sensitive_keys : set[str] | None
        마스킹 대상 민감 키를 런타임에 추가 확장
    """
    global _initialized, _SENSITIVE_KEYS_DEFAULT

    # 중복 초기화 방지: 핸들러 존재 여부가 아니라 '우리 의도' 플래그로 제어
    if _initialized:
        return
    _initialized = True

    # 민감 키 확장(대소문자 무시)
    if extra_sensitive_keys:
        _SENSITIVE_KEYS_DEFAULT |= {k.lower() for k in extra_sensitive_keys}

    root = logging.getLogger()
    root.setLevel(_to_level(level))
    root.propagate = propagate_root  # 일반적으로 False: 상위 로거로 중복 전파 방지

    # 포맷터 선택(텍스트 / JSON)
    if json_format:
        formatter = JSONFormatter()  # ← JSON 라인 포맷
    else:
        formatter = KeyValueFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        # 텍스트일 때만 ISO8601 포맷 지정
        formatter.default_time_format = "%Y-%m-%dT%H:%M:%S"
        formatter.default_msec_format = "%s.%03d"

    # 콘솔 핸들러
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    root.addHandler(sh)

    # 파일 핸들러(선택)
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if rotate:
            fh = RotatingFileHandler(
                log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
        else:
            from logging import FileHandler
            fh = FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(formatter)
        root.addHandler(fh)


def get_logger(name: str) -> Logger:
    """
    모듈/패키지 단위 로거를 반환합니다.
    - 핸들러는 루트 로거에만 달려 있으므로, 여기서는 핸들러를 추가하지 않습니다.
    - 로거 이름은 일반적으로 __name__ 을 전달합니다.
    """
    return logging.getLogger(name)
