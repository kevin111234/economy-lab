from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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