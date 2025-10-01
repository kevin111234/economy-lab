"""
입력 데이터: 거래소, 엔드포인트, 
            파라미터(symbol, interval, start_time, end_time, limit)
출력 데이터: pandas.DataFrame
            column(open, high, low, close, volume)
            가격, 거래량은 float64, 시간오름차순 정렬, 중복없음
"""
import pandas as pd

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
        # 문자열 정리
        # 형식 보완
        # KST로 해석
        # UTC로 변환
        # 에포크 밀리초로 변환
      # limit가 1 이상인지
    # 비어있는 데이터프레임 생성
    # request - 아래와 같은 주소 생성(BTC 5m 1000개 로딩)
    # https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=1000
    # 응답 받기(JSON 형식)
    # 데이터프레임으로 변환
    # 필요한 칼럼만 추출
    # 중복 체크, 시간오름차순 정렬
    # 행 개수와 리미트 비교 검증
    # 반환
    return