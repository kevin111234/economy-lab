import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests, time, random

# --- logging utils ---
from utils.logging_config import get_logger, setup_logging
from utils.logger import with_context, timeit, log_request
# --- time utils ---
from utils.api_utils import time_parser

log = with_context(get_logger(__name__), svc="exchange-official-loader", env="dev")

# FRED API 연결 유틸(requests)
def get_api_data_FRED(series_id: str, start: str, end: str, api_key: str,
                      limit: int = 1000, offset: int = 0, max_retries: int = 3
                      )-> pd.DataFrame:
    # url 설정
    url = "https://api.stlouisfed.org/fred/series/observations"
    # 파라미터 설정
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
        "observation_end": end,
        "limit": limit,
        "offset": offset,
        "sort_order": "asc"
    }
    all_obs = []
    # 파라미터 검증
    if not api_key:
        raise ValueError("FRED API key is required. Set it via environment variable.")
    # 데이터 수집 루프 (페이지네이션 적용)
    while True:
        for attempt in range(max_retries):
            try:
                # 파라미터 정보 로그에 저장
                log_request(log, "GET", url, params=params, level="DEBUG")
                # 요청 전송
                r = requests.get(url, params=params, timeout=10)
                # 받은 요청 확인
                # status_code == 429 -> 레이트리밋
                if r.status_code == 429:
                    retry_after = r.headers.get("Retry-After")
                    if retry_after is not None:
                        try:
                            wait = float(retry_after)
                        except ValueError:
                            wait = 2 ** attempt + random.uniform(0,0.25)
                    else:
                        wait = 2 ** attempt + random.uniform(0,0.25)
                    # 에러 로깅 적용
                    log_request(log, "GET", url, status=429, attempt=attempt, wait_s=wait, level="WARNING")
                    time.sleep(wait)
                    continue
                # 500 <= status_code < 600 -> server error
                elif 500 <= r.status_code < 600:
                    wait = 2 ** attempt + random.uniform(0,0.25)
                    # 에러 로깅 적용
                    log_request(log, "GET", url, status=r.status_code, attempt=attempt, wait_s=wait, level="WARNING")
                    time.sleep(wait)
                    continue
                else: break
            except requests.exceptions.RequestException as e:
                # 최종 실패 직전 로그
                if attempt == max_retries - 1:
                    log.error("request_exception_final", exc_info=True,
                              extra={"url": url, "params": params})
                    raise RuntimeError(f"API 요청 실패: {e} (url={url}, params={params})")
                else:
                    log.warning("request_exception_retry", extra={"attempt": attempt, "err": repr(e)})
                    time.sleep(2 ** attempt + random.uniform(0, 0.25))
                    continue
            except ValueError as e:
                log.error("json_parse_error", exc_info=True, extra={"url": url})
                raise RuntimeError(f"JSON 파싱 실패: {e}")
        r.raise_for_status()
        # json 형태로 데이터 받기
        data = r.json()
        # 데이터 중 필요한 부분 추출(안전성 강화)
        obs = data.get("observations", [])
        all_obs.extend(obs)
        # 데이터가 없는 경우 처리
        if not obs:
            break
        # 데이터 수가 limit보다 작은 경우 처리
        if len(obs) < params["limit"]:
            break
        params["offset"] += params["limit"]
    # 데이터 전체가 비어있는 경우 처리
    if not all_obs:
        return pd.DataFrame(columns=[series_id])
    # 데이터 정규화(데이터프레임으로 변환)
    df = pd.DataFrame(all_obs)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])  # naive UTC
    # 인덱스 열 설정
    df = df.set_index("date").sort_index()
    # 결측값 체크
    na_count = df.isna().sum().iloc[0]
    if na_count > 0:
        log.warning("fred_missing_values", extra={"na_rows": int(na_count), "total": len(df)})
    # 타임존 변환
    # FRED date는 'YYYY-MM-DD' 문자열이므로, KST 자정으로 로컬라이즈
    df.index = df.index.tz_localize("Asia/Seoul")
    # 데이터 수집 성공 시 로깅
    log.info("fred_load_done", extra={"rows": len(df), 
                                      "pages": max(1, params["offset"] // limit + 1)})
    return df[["value"]].rename(columns={"value": series_id})

# 원/달러 환율 불러오기(FRED api)
def FRED_exchange_data_loader(
        start: str | int,
        end: str | int,
        *,
        api_key: str,
        limit: int = 1000,
        max_retries: int = 3,
        timeout: float = 10.0
    ) -> pd.DataFrame:
    # 파라미터 검증
    if not api_key:
        raise ValueError("FRED API key is required. Set it via environment variable.")
    if limit < 1 or limit > 1000:
        raise ValueError(f"limit can't be upper than 1000, lower than 1. got {limit}")
    # 시간 검증
    if start is not None and end is not None:
        st = time_parser(start)
        et = time_parser(end)
        if st > et:
            # 시간 설정 오류 로깅
            log.error("invalid_time_range", extra={"st": st, "et": et})
            raise ValueError(f"start time can't be later than end time. start time:'{start}', end time:'{end}'")
    else:
        # time error 로깅
        log.error("time_none", extra={"start_time": start, "end_time": end})
        raise ValueError(f"start time and end time can't be None, got start_time:'{start}', end_time:'{end}'")
    # 에포크 밀리초를 타임스템프로 변환
    KST = ZoneInfo("Asia/Seoul")
    # epoch ms → UTC → KST로 변환 후, KST '자정 스냅'의 'YYYY-MM-DD' 문자열로
    st_kst_date = datetime.fromtimestamp(st/1000, tz=timezone.utc).astimezone(KST).date().isoformat()
    et_kst_date = datetime.fromtimestamp(et/1000, tz=timezone.utc).astimezone(KST).date().isoformat()

    df_raw = get_api_data_FRED(
        series_id="DEXKOUS",
        start=st_kst_date,           # ← 문자열 'YYYY-MM-DD'
        end=et_kst_date,             # ← 문자열 'YYYY-MM-DD'
        api_key=api_key,
        limit=limit,
        max_retries=max_retries
    )
    # 스키마 표준화
    df = df_raw.rename(columns={"DEXKOUS": "KRW_per_USD"})
    df["source"] = "fred"
    # 데이터 수집 완료 로깅
    return df[["KRW_per_USD", "source"]]

# 달러인덱스 불러오기(FRED api)
def FRED_dollar_index_data_loader():
    # 파라미터 검증
    # 데이터 수집 시작 로깅
    # 페이지네이션
    # 데이터 수집 완료 로깅
    return

# 달러인덱스에 따른 원화인덱스 데이터 계산
def won_index_data_calculator(exchange_df, dollar_index_df):
    # 파라미터 검증
    # 데이터 계산식 적용
    # 데이터 계산 완료 로깅
    # 3가지 데이터 병합 후 반환
    return
