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
import requests, time, random

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

# request를 통해 Binance api와 연결
def get_api_data_binance(base_url: str, path: str, params: dict,
                          timeout: float = 10.0, max_retries: int = 3):
    # url 조합
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    with requests.Session() as s:
        for attempt in range(max_retries+1):
            try:
                # 요청 전송
                r = s.get(url, params=params, timeout=timeout)
                # 받은 요청 확인
                # status_code == 429 -> 레이트리밋
                if r.status_code == 429:
                    retry_after = r.headers.get("Retry-After")
                    if retry_after is not None:
                        try:
                            time.sleep(float(retry_after))
                        except ValueError:
                            time.sleep(2 ** attempt + random.uniform(0,0.25))
                    else:
                        time.sleep(2 ** attempt + random.uniform(0,0.25))
                    continue
                # 500 <= status_code < 600 -> server error
                elif 500 <= r.status_code < 600:
                    time.sleep(2 ** attempt + random.uniform(0,0.25))
                    continue
                else:
                    r.raise_for_status()
                    # json 형태로 데이터 받기
                    data = r.json()
                    if data == []:
                        print("empty dataframe")
                        empty_idx = pd.DatetimeIndex([], tz="Asia/Seoul", name="open_time")
                        empty_df = pd.DataFrame({
                            "open": pd.Series(dtype="float64"),
                            "high": pd.Series(dtype="float64"),
                            "low": pd.Series(dtype="float64"),
                            "close": pd.Series(dtype="float64"),
                            "volume": pd.Series(dtype="float64"),
                            "close_time": pd.Series(dtype="datetime64[ns, UTC]"),
                            "quote_volume": pd.Series(dtype="float64"),
                            "trades": pd.Series(dtype="Int64"),
                            "taker_buy_base": pd.Series(dtype="float64"),
                            "taker_buy_quote": pd.Series(dtype="float64"),
                        }, index=empty_idx)
                        return empty_df
                    else:
                        # 데이터프레임 만들기
                        COLUMNS = [
                            "open_time", "open", "high", "low", "close", "volume",
                            "close_time", "quote_volume", "trades", 
                            "taker_buy_base", "taker_buy_quote", "ignore"
                        ]
                        df = pd.DataFrame(data, columns=COLUMNS)
                        # 필요없는 열 제거
                        df = df.drop(columns=["ignore"])
                        # 데이터 타입 변환
                        NUMERIC_FLOAT = ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_base", "taker_buy_quote"]
                        df[NUMERIC_FLOAT] = df[NUMERIC_FLOAT].apply(pd.to_numeric, errors = "coerce")
                        df["trades"] = pd.to_numeric(df["trades"], errors="coerce").astype("Int64")
                        # 에포크 밀리초를 타임스템프(UTC)로 변환
                        df["open_time"]  = pd.to_datetime(df["open_time"], unit="ms", utc=True)
                        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
                        # open_time을 기준으로 정렬
                        df = df.set_index("open_time").sort_index()
                        df = df[~df.index.duplicated(keep="last")]
                        # 결측값 수 파악
                        na_count = df.isna().sum()
                        # 핵심 열의 결측값 제거
                        df = df.dropna(subset=["open","high","low","close","volume"])
                        return df

            except requests.exceptions.RequestException as e:
                if attempt >= max_retries:
                    raise RuntimeError(f"API 요청 실패: {e} (url={url}, params={params})")
            except ValueError as e:
                raise RuntimeError(f"JSON 파싱 실패: {e}")

# 함수 시작
def crypto_data_loader(
    symbol: str,
    interval: str,
    start_time: str | int,
    end_time: str | int,    # "2024-01-01" | epoch ms
    market: str = "spot",   # spot 기본값, futures로 전환 가능
    limit: int = None,      # 기본값 = 리미트 없음
    max_retries: int = 3,   # 재시도 횟수
    timeout: float = 10.0,
) -> pd.DataFrame:
    """
    암호화폐 데이터를 불러와 데이터프레임으로 반환\
    파라미터 입력:\
    symbol: 암호화폐 심볼 (예: BTCUSDT)\
    interval: 1m~1M까지 중 선택\
    start_time, end_time: 데이터를 불러올 기간\
    limit: 한번에 불러올 데이터의 개수(기본값= 1000, 최소 1, 최대 1000)\
    market: 현물 시장, 선물 시장(spot, futures)\
    max_retries: 재시도 횟수(api 에러 시)\
    timeout: api 접속 타임아웃
    """
    # Base URL 정의
    if market == "spot":
        Base_URL = "https://api.binance.com"
        path = "/api/v3/klines"
    elif market == "futures":
        Base_URL = "https://fapi.binance.com"
        path = "/fapi/v1/klines"
    else:
        raise ValueError(f"market must be 'spot' or 'futures', got {market!r}")
    # 파라미터 검증
    # interval이 유효한지(지정된 문자열 중 하나인지)
    ALLOWED = {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"}
    if interval not in ALLOWED:
        raise ValueError(f"interval must be one of {sorted(ALLOWED)}, got '{interval}'")
    # 시간 검증
    if start_time is not None and end_time is not None:
        st = time_parser(start_time)
        et = time_parser(end_time)
        if st > et:
            raise ValueError(f"start time can't be later than end time. start time:'{start_time}', end time:'{end_time}'")
    else:
        raise ValueError(f"start time and end time can't be None, got start_time:'{start_time}', end_time:'{end_time}'")
    # limit가 1 이상인지
    if limit is not None and limit < 1:
        raise ValueError(f"limit can't be less then 1, got '{limit}'")
    # 파라미터 지정
    params = {"symbol":symbol, "interval":interval, "startTime":st, "endTime":et}
    # limit가 none이면 파라미터에 추가 X
    if limit is not None:
        params["limit"] = limit
    # requests 통해서 데이터 받아오기
    result = get_api_data_binance(Base_URL, path=path, params=params)
    # 행 개수와 리미트 비교 검증
    # 반환
    return result

# 테스트용 코드
if __name__ == "__main__":
    result = crypto_data_loader("BTCUSDT", "5m", "2024-01-05", " 2025-08-18 16:54", "spot")
    print(result)