import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests, time, random
import numpy as np

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
        series_id: str,
        column_name: str,
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
        series_id=series_id,
        start=st_kst_date,           # ← 문자열 'YYYY-MM-DD'
        end=et_kst_date,             # ← 문자열 'YYYY-MM-DD'
        api_key=api_key,
        limit=limit,
        max_retries=max_retries
    )
    # 스키마 표준화
    df = df_raw.rename(columns={series_id : column_name})
    # 데이터 수집 완료 로깅
    return df[[column_name]]

# 달러인덱스에 따른 원화인덱스 데이터 계산
def won_index_data_calculator(start: int | str, end: int | str, api_key):
    # ---------------------------
    # 0) 준비
    # ---------------------------
    result = pd.DataFrame()
    dfs = []

    sid = {
        "KRWUSD": "DEXKOUS",   # 1 USD = ? KRW
        "EURUSD": "DEXUSEU",   # USD/EUR → 역수 필요
        "USDJPY": "DEXJPUS",   # 1 USD = ? JPY
        "GBPUSD": "DEXUSUK",   # USD/GBP → 역수 필요
        "USDCAD": "DEXCAUS",   # 1 USD = ? CAD
        "USDSEK": "DEXSDUS",   # 1 USD = ? SEK
        "USDCHF": "DEXSZUS",   # 1 USD = ? CHF
        "DXY": "DTWEXBGS"      # Broad Dollar Index (2006=100)
    }

    # ---------------------------
    # 1) 데이터 수집
    # ---------------------------
    for col_name, series_id in sid.items():
        df_i = FRED_exchange_data_loader(
            series_id=series_id,
            column_name=col_name,
            start=start,
            end=end,
            api_key=api_key
        )
        if isinstance(df_i, pd.DataFrame) and not df_i.empty:
            dfs.append(df_i[[col_name]])

    if dfs:
        result = pd.concat(dfs, axis=1, join="outer").sort_index()
        result = result[~result.index.duplicated(keep="last")]
    else:
        return pd.DataFrame()

    # ---------------------------
    # 2) 환율 방향 보정
    # ---------------------------
    # FRED의 DEXUSEU(EUR/USD), DEXUSUK(GBP/USD)는 USD 기준이 아니라 반대방향이므로 역수 필요
    invert_cols = ["EURUSD", "GBPUSD"]
    for c in invert_cols:
        if c in result.columns:
            result[c] = 1.0 / result[c]

    # ---------------------------
    # 3) 데이터 정리 (숫자형 변환)
    # ---------------------------
    for c in result.columns:
        result[c] = pd.to_numeric(result[c], errors="coerce")
    result = result.replace([np.inf, -np.inf], np.nan)

    # ---------------------------
    # 4) 달러 인덱스 단순 리베이스
    # ---------------------------
    # DXY(=DTWEXBGS)는 2006=100 기준이므로 최근값이 120 근처 → 100 부근으로 맞춰주기 위해 리베이스
    if "DXY" in result.columns:
        # 최근 2년 평균을 100으로 맞추는 간단한 리베이스 예시
        recent = result["DXY"].dropna().tail(520)  # 약 2년치
        if not recent.empty:
            scale = 100.0 / recent.mean()
            result["DXY_rebased"] = result["DXY"] * scale
        else:
            result["DXY_rebased"] = result["DXY"]

    # ---------------------------
    # 5) 원화 인덱스 계산 (단순 정규화형)
    # ---------------------------
    if "KRWUSD" in result.columns:
        base_idx = result["KRWUSD"].dropna().index.min()
        if pd.notna(base_idx):
            base_val = result.at[base_idx, "KRWUSD"]
            result["KRW_INDEX"] = 100.0 * (base_val / result["KRWUSD"])

    # ---------------------------
    # 6) 원화 인덱스 (달러 절대강약 감안형)
    # ---------------------------
    if {"KRWUSD", "DXY_rebased"}.issubset(result.columns):
        df_reg = result[["KRWUSD", "DXY_rebased"]].dropna().copy()
        if len(df_reg) > 30:
            x = np.log(df_reg["DXY_rebased"].values)
            y = np.log(df_reg["KRWUSD"].values)
            beta = np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1)
            alpha = y.mean() - beta * x.mean()
            p_hat = np.exp(alpha + beta * np.log(result["DXY_rebased"]))
            result["KRW_STRENGTH"] = 100.0 * (p_hat / result["KRWUSD"])

    # β 추정 (선택: 없으면 1.0)
    df_reg = result[["KRWUSD", "DXY_rebased"]].dropna().copy()
    if len(df_reg) >= 60:  # 최소 샘플 보장
        x = np.log(df_reg["DXY_rebased"].values)   # 중립=100 기준이므로 100 부근
        y = np.log(df_reg["KRWUSD"].values)
        beta = np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1)
    else:
        beta = 1.0  # 보수적 기본값

    # USD-중립 조정 환율: P_adj = P / (U/100)^β
    P = result["KRWUSD"]
    U = result["DXY_rebased"]
    result["P_ADJ"] = P / np.power(U / 100.0, beta)

    # 베이스 선택: 첫 유효일(또는 최근 252거래일 중앙값 등으로 바꿔도 됨)
    base_idx = result["P_ADJ"].dropna().index.min()
    if pd.notna(base_idx):
        base_val = result.at[base_idx, "P_ADJ"]
        result["KRW_STRENGTH_NEUTRAL"] = 100.0 * (base_val / result["P_ADJ"])

    # ---------------------------
    # 7) 정리 후 반환
    # ---------------------------
    keep_cols = [
        "KRWUSD", "DXY_rebased", "KRW_STRENGTH"
    ]
    keep_cols = [c for c in keep_cols if c in result.columns]
    result = result[keep_cols]
    return result