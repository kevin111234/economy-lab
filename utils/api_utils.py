from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os, re
from pathlib import Path

def time_parser(time: str | int): # 입력: YYYY-MM-DD HH:MM 또는 YYYY-MM-DD
    KST = ZoneInfo("Asia/Seoul")
    # 타입 체크
    if isinstance(time, bool): # bool 타입이면 int로 인식될 수도 있음!
        raise TypeError("time must not be bool")
    if isinstance(time, int):
        if time < 0: # int 타입이지만 음수인 경우
            raise ValueError(f"timestamp must be >= 0 ms, got {time}")
        if time < 1_000_000_000_000: # int 타입이지만 초 단위까지 포함한 경우
            raise ValueError(f"timestamp must be epoch milliseconds, got {time}")
        return time
    if not isinstance(time, str): # 타입이 str, int 모두 아닌 경우
        raise TypeError(f"time must be str or int(ms), got {type(time).__name__}")
    # 문자열 정리 및 형식 보완
    t = time.strip()
    if len(t) == 10: # YYYY-MM-DD인 경우 길이가 10
        t = t + " 00:00"
    # KST로 해석, UTC로 변환
    try:
        dt = datetime.strptime(t, "%Y-%m-%d %H:%M")
    except ValueError as e:
        raise ValueError(f"invalid datetime: {t!r} (expected 'YYYY-MM-DD[ HH:MM]')") from e
    dt = dt.replace(tzinfo=KST)
    # 에포크 밀리초로 변환
    return int(dt.astimezone(timezone.utc).timestamp()*1000)

def load_env(path: str | os.PathLike = ".env", override: bool = False) -> int:
    """
    .env 파일을 읽어 os.environ에 주입한다.
    KEY=VALUE, 따옴표('"...") 허용, # 주석/빈줄 무시.
    return: 로드한 키 개수
    """
    p = Path(path)
    if not p.exists():
        return 0
    n = 0
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if (len(v) >= 2) and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        if override or (k not in os.environ):
            os.environ[k] = v
            n += 1
    return n

def get_required(key: str) -> str:
    v = os.getenv(key)
    if not v:
        raise RuntimeError(f"환경변수 {key!r} 가 설정되지 않았습니다.")
    return v
