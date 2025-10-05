# Binance Crypto Data Loader (crypto.py)

## 데이터 스키마(반환 DataFrame)

* **인덱스**: `open_time` (KST, tz-aware)
* **칼럼**: `open, high, low, close, volume, close_time(KST), quote_volume, trades(Int64), taker_buy_base, taker_buy_quote`
* **정렬/중복**: 시간 오름차순, 중복 인덱스 제거
* **결측 처리**: 핵심 열(`open, high, low, close, volume`) 결측 행 드롭 

---

## 모듈 구성과 함수별 사용법

### 1 `time_parser(time: str | int) -> int`

**역할**: 입력 시간(문자열 또는 epoch ms)을 **KST로 해석**한 뒤 **UTC epoch ms**로 변환.
**입력 형식**:

* `"YYYY-MM-DD HH:MM"` 또는 `"YYYY-MM-DD"`(시·분 미지정 시 `00:00` 보정)
* `int`(밀리초 단위 epoch만 허용)
  **예외**: 타입/형식 오류, 음수·초 단위(epoch s) 입력 시 `ValueError/TypeError`. 

**예**

```python
st = time_parser("2024-01-05 00:00")   # KST → UTC ms
et = time_parser("2025-08-18 16:54")   # KST → UTC ms
```

---

### 2 `get_api_data_binance(base_url: str, path: str, params: dict, timeout=10.0, max_retries=3) -> pd.DataFrame`

**역할**: **한 페이지**의 klines 데이터를 요청·수신·정규화하여 DataFrame으로 반환.
**핵심 처리**:

* 429/5xx/네트워크 오류 시 **지수 백오프 재시도**, `Retry-After` 헤더 지원
* 빈 응답 `[]`이면 **KST 인덱스 스키마**의 **빈 DF** 반환
* 문자열 숫자 → 수치형 변환, `open_time/close_time` UTC 파싱 → 인덱스 설정·정렬·중복 제거 → 핵심 결측 행 드롭 

**반환**: 한 페이지 분량의 **UTC 인덱스 DF**(상위에서 KST로 변환됨) 또는 스키마 일치 빈 DF. 

---

### 3 `pagination(base_url, path, symbol, interval, st, et, limit) -> pd.DataFrame`

**역할**: 기간 전체를 **여러 페이지로 나눠 수집**하고, 최종 DataFrame으로 병합.
**주요 로직**:

* `interval_ms` 매핑(분·시간·일·주; `1M` 제외)
* **경계 스냅**: `first=ceil(start, k)`, `last=floor(end, k)`
* **기대 행수** 계산 → 정보 출력
* `current`를 `last_page_open + k`로 **안전 전진**, **스톨 가드**(`last_open_ms <= current`) 적용
* 각 페이지 DF를 리스트에 누적 → `concat → sort_index → duplicated 제거`
* `end` 초과분 드롭(끝 포함 정책)
* **반환 직전** `open_time` 인덱스와 `close_time` 컬럼을 **KST로 tz 변환**하여 일관 출력 

**파라미터**:

* `interval`: `{1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w}`
* `limit`: `None`이면 1000 사용(페이지 크기)
* `st, et`: `time_parser`로 얻은 **UTC ms**
  **반환**: 전체 기간의 **KST 인덱스 DF** (스키마 통일) 

---

### 4 `crypto_data_loader(symbol, interval, start_time, end_time, market="spot", limit=None, max_retries=3, timeout=10.0) -> pd.DataFrame`

**역할(최상위 API)**: 파라미터 검증 → 엔드포인트 선택(Spot/Futures) → 기간 파싱 → **페이지네이션 호출** → 최종 DF 반환.
**검증**:

* `market`: `'spot' | 'futures'`
* `interval`: 허용 집합(주·월 중 **월 1M 제외**)
* `limit`: `1~1000` (None → 1000)
* `start_time ≤ end_time`
  **반환**: KST 인덱스의 표준화된 DataFrame. 

**예**

```python
df = crypto_data_loader(
    symbol="BTCUSDT",
    interval="5m",
    start_time="2024-01-05 00:00",  # KST
    end_time="2025-08-18 16:54",    # KST
    market="spot",
    limit=None  # → 1000
)
```

---
