# tests/test_logging_basic.py
from utils.logging_config import setup_logging, get_logger
from utils.logger import with_context
import logging

def test_setup_once(monkeypatch):
    setup_logging(log_path=None, level="INFO")
    root = logging.getLogger()
    first = len(root.handlers)
    setup_logging(log_path=None, level="INFO")
    second = len(root.handlers)
    assert first == second  # 중복 초기화 X

def test_context_binding(caplog):
    setup_logging(log_path=None, level="INFO")
    log = with_context(get_logger(__name__), svc="unittest")
    with caplog.at_level(logging.INFO):
        log.info("hello", extra={"req_id":"abc"})
    # caplog.text 에 'svc=unittest' 또는 JSON ctx에 포함되어야 함
    assert "unittest" in caplog.text
    assert "req_id" in caplog.text
