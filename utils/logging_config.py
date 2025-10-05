"""
logging_config.py
프로세스 전역 로깅 설정/초기화를 담당합니다.
- 콘솔/파일 핸들러
- 텍스트/JSON 포맷
- 회전(rotate) 파일 핸들러
- 민감정보 필터(safe_params)
"""

from __future__ import annotations
import logging
from logging import Logger
from logging.handlers import RotatingFileHandler
import os
import json
from typing import Any, Dict, Optional


# -------------------------------
# 유틸: 문자열 레벨 → 숫자 레벨
# -------------------------------
_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

def _to_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    return _LEVELS.get(level.upper(), logging.INFO)


# -------------------------------
# 포맷터: 텍스트 / JSON
# -------------------------------
class KeyValueFormatter(logging.Formatter):
    """
    기본 텍스트 포맷터.
    record.extra(dict) 또는 LoggerAdapter의 extra로 들어온 값을
    'key=value key=value' 형태로 메시지 뒤에 붙여준다.
    """
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        # LoggerAdapter 또는 extra로 들어온 컨텍스트
        extras = getattr(record, "ctx", None) or getattr(record, "extra", None)
        if isinstance(extras, dict) and extras:
            kv = " ".join(f"{k}={v}" for k, v in extras.items())
            return f"{base} | {kv}"
        return base


class JSONFormatter(logging.Formatter):
    """
    JSON 라인 로깅 포맷터.
    모든 로그를 JSON 한 줄로 직렬화하여 ELK, CloudWatch 등에 바로 태울 수 있다.
    """
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # 컨텍스트(있으면)
        ctx = getattr(record, "ctx", None) or getattr(record, "extra", None)
        if isinstance(ctx, dict) and ctx:
            payload["ctx"] = ctx
        # 예외 정보(있으면)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


# -------------------------------
# 민감정보 필터링
# -------------------------------
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "apiSecret",
    "secret",
    "token",
    "authorization",
    "password",
    "passwd",
}

def safe_params(params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    쿼리/바디 등 로그에 남길 때 민감 키는 마스킹한다.
    """
    if not isinstance(params, dict):
        return params
    redacted = {}
    for k, v in params.items():
        if k.lower() in _SENSITIVE_KEYS:
            redacted[k] = "***"
        else:
            redacted[k] = v
    return redacted


# -------------------------------
# 메인: 로깅 초기화
# -------------------------------
def setup_logging(
    log_path: Optional[str] = "logs/app.log",
    level: str | int = "INFO",
    json_format: bool = False,
    rotate: bool = True,
    max_bytes: int = 5_000_000,
    backup_count: int = 3,
    propagate_root: bool = False,
) -> None:
    """
    애플리케이션 시작 시 '한 번만' 호출하세요.
    - 콘솔 + (선택) 파일 핸들러를 장착합니다.
    - 중복 초기화를 방지합니다.

    Args:
        log_path: 로그 파일 경로. None이면 파일 핸들러를 추가하지 않습니다.
        level: 로그 레벨 ("INFO", "DEBUG" 등 또는 숫자)
        json_format: True면 JSON 라인 포맷, False면 텍스트 포맷
        rotate: 파일 회전 사용 여부
        max_bytes: 회전 파일 최대 크기
        backup_count: 회전 파일 백업 개수
        propagate_root: 루트 로거 상위 전파(default False)
    """
    root = logging.getLogger()
    if root.handlers:
        # 이미 설정되어 있으면 두 번 하지 않음
        return

    root.setLevel(_to_level(level))
    root.propagate = propagate_root

    # 포맷터 선택
    if json_format:
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = KeyValueFormatter(fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    # 콘솔 핸들러
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    root.addHandler(sh)

    # 파일 핸들러(선택)
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if rotate:
            fh = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        else:
            fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(formatter)
        root.addHandler(fh)


# -------------------------------
# 로거 생성 헬퍼
# -------------------------------
def get_logger(name: str) -> Logger:
    """
    모듈/패키지 단위로 로거를 얻는다.
    핸들러는 루트에만 달려 있으므로 여기선 핸들러를 추가하지 않는다.
    """
    logger = logging.getLogger(name)
    return logger
