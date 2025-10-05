# 로거 적용 방법 개요

## 🧭 1단계: 초기화 — 프로그램 시작 시 단 한 번

보통 `main.py`, `app.py`, 혹은 패키지의 엔트리포인트에서 **맨 위에** 실행

```python
# main.py
from src.utils.logging_config import setup_logging

setup_logging(
    log_path="logs/app.log",   # None이면 파일 저장 안 함(콘솔만)
    level="INFO",              # 개발 중엔 "DEBUG"
    json_format=False,         # 프로덕션 수집/분석은 True
    rotate=True,               # 로그 파일 회전 활성화
)
```

> ✅ 반드시 한 번만 호출
> (테스트 중 여러 번 바꿔야 한다면 `force_reconfigure=True` 옵션을 추가)

---

## 🧩 2단계: 모듈별 로거 준비

각 모듈 파일 맨 위에 아래 코드 삽입

```python
# fx_loader.py, crypto_loader.py 등
from src.utils.logging_config import get_logger
from src.utils.logger import with_context

log = with_context(get_logger(__name__), svc="fx-loader", env="dev")
```

이제 이 파일 안의 모든 함수에서 `log.info()`, `log.warning()` 등을 그대로 사용하면
자동으로 `svc=fx-loader env=dev` 컨텍스트가 함께 붙는다.

---

## 🧪 3단계: 함수 실행시간 측정(`@timeit`)

긴 처리나 파이프라인 함수에 한 줄만 추가

```python
from src.utils.logger import timeit

@timeit(log, "load_fx_bundle")
def load_fx_bundle():
    # 데이터 수집/가공 코드
    ...
    return df
```

로그 예시:

```
2025-10-05T05:12:45.321 | INFO | fx_loader | load_fx_bundle done | svc=fx-loader env=dev duration_ms=1584.12 success=True
```

> ⚙️ `success=False`는 예외가 발생한 경우 자동으로 찍힘

---

## 🌐 4단계: 외부 API 호출(`log_request`)

HTTP 요청 전후에 **log_request()**를 추가
- 데이터 소스 크롤링에 쓰기 좋음

```python
from src.utils.logger import log_request
import requests, time, random

def fetch_fx(symbol="USD/KRW"):
    url = "https://api.example.com/fx"
    params = {"symbol": symbol, "api_key": "SECRET"}

    for attempt in range(3):
        try:
            # 요청 직전
            log_request(log, "GET", url, params=params, level="INFO")

            r = requests.get(url, params=params, timeout=5)
            r.raise_for_status()

            # 요청 성공
            log_request(log, "GET", url, status=r.status_code, note="ok", level="INFO")
            return r.json()

        except requests.HTTPError as e:
            if r.status_code == 429:  # 레이트리밋
                wait = 2 ** attempt + random.random() * 0.3
                log_request(log, "GET", url, status=429, attempt=attempt, wait_s=wait, level="WARNING")
                time.sleep(wait)
                continue

            log.error("http_error", exc_info=True)
            raise

        except requests.ConnectionError as e:
            log.warning("network_error", extra={"attempt": attempt, "err": repr(e)})
            time.sleep(1)
        except Exception as e:
            log.error("unexpected_error", exc_info=True)
            raise
```

출력 예시:

```
2025-10-05T05:14:18.120 | INFO | fx_loader | http_call | svc=fx-loader env=dev method=GET url=https://api.example.com/fx params={'symbol': 'USD/KRW', 'api_key': '***'}
2025-10-05T05:14:18.454 | INFO | fx_loader | http_call | svc=fx-loader env=dev method=GET url=https://api.example.com/fx status=200 note=ok
```

---

## 🔄 5단계: 상위 루틴(파이프라인)에 통합

예를 들어 “하루치 환율 + 달러지수 + USDT 가격”을 한 번에 불러오는 함수를 만든다면:

```python
@timeit(log, "load_all_markets")
def load_all_markets():
    fx = fetch_fx("USD/KRW")
    dxy = fetch_fx("DXY")
    usdt = fetch_fx("USDT/KRW")
    return {"fx": fx, "dxy": dxy, "usdt": usdt}
```

---

## 📁 6단계: 모듈 간 로그 분리 (선택)

서비스가 커지면 로거 이름을 통해 로그를 분리할 수 있음

| 모듈    | 로거 이름           | 로그파일                | 예시 명령                          |
| ----- | --------------- | ------------------- | ------------------------------ |
| 환율 수집 | `fx_loader`     | `logs/fx.log`       | `setup_logging("logs/fx.log")` |
| 암호화폐  | `crypto_loader` | `logs/crypto.log`   | ...                            |
| 백테스터  | `backtester`    | `logs/backtest.log` | ...                            |

혹은 한 파일로 두고, `ctx.svc` 필드로 구분해도 충분

---

## 🧩 7단계: 실시간 확인용

개발 중에는 **콘솔 + 파일** 같이 쓰면 좋음
실시간 로그는 `tail -f logs/app.log`로 확인,
JSON 포맷으로 바꾸면 `jq`로 파이프 가능:

```bash
python app.py | jq .
```

---

## 🚦 8단계: 빠른 체크리스트

| 확인 항목                                                    | 결과 |
| -------------------------------------------------------- | -- |
| `setup_logging` 호출은 한 번만 되었는가?                           | ✅  |
| 모든 모듈에서 `log = with_context(get_logger(__name__))`을 썼는가? | ✅  |
| 주요 함수에 `@timeit(log, "name")` 붙였는가?                      | ✅  |
| 외부 요청부에 `log_request()` 추가했는가?                           | ✅  |
| 예외가 발생했을 때 `exc_info=True`가 찍히는가?                        | ✅  |
| 로그 폴더(`logs/`)가 자동 생성되는가?                                | ✅  |
