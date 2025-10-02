"""
입력 데이터: 거래소, 엔드포인트, 
            파라미터(symbol, interval, start_time, end_time, limit)
출력 데이터: pandas.DataFrame
            column(open, high, low, close, volume)
            가격, 거래량은 float64, 시간오름차순 정렬, 중복없음
"""
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests, time

# 시간 검증 유틸
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

# 함수 시작
def crypto_data_loader(
    symbol: str,
    interval: str,
    start_time: str | int,
    end_time: str | int,    # "2024-01-01" | epoch ms
    market: str = "spot",   # spot 기본값, future로 전환 가능
    limit: int = None,      # 기본값 = 리미트 없음
    max_retries: int = 3,   # 재시도 횟수
    timeout: float = 10.0,
) -> pd.DataFrame:
    # Base URL 정의
    if market == "spot":
        Base_URL = "https://api.binance.com"
    elif market == "future":
        Base_URL = "https://fapi.binance.com"
    else:
        raise ValueError("{market} is not used keyword. use 'spot' or 'future'")
    # 파라미터 검증
    # interval이 유효한지(지정된 문자열 중 하나인지)
    ALLOWED = {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"}
    if interval not in ALLOWED:
        raise ValueError(f"interval must be one of {sorted(ALLOWED)}, got '{interval}'")
    # 시간 검증
    st = time_parser(start_time)
    et = time_parser(end_time)
    if st > et:
        raise ValueError(f"start time can't be later then end time. start time:'{start_time}', end time:'{end_time}'")
    # limit가 1 이상인지
    if limit is not None and limit < 1:
        raise ValueError(f"limit can't be less then 1, got '{limit}'")
    # request - 아래와 같은 주소 생성(BTC 5m 1000개 로딩)
    # https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=1000
    # 응답 받기(JSON 형식)
    # 데이터프레임으로 변환
    # 필요한 칼럼만 추출
    # 중복 체크, 시간오름차순 정렬
    # 행 개수와 리미트 비교 검증
    # 반환
    return

# 테스트용 코드
if __name__ == "__main__":
    crypto_data_loader("BTCUSDT", "5m", "2024-01-05", " 2025-08-18 16:54", "spot")