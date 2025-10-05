# 🇺🇸 English Version — Logger Integration Guide

## 🧭 Step 1: Initialization — Call Once at Program Startup

Typically executed at the very top of `main.py`, `app.py`, or your package entry point.

```python
# main.py
from src.utils.logging_config import setup_logging

setup_logging(
    log_path="logs/app.log",   # None → console only
    level="INFO",              # "DEBUG" during development, "INFO" in production
    json_format=False,         # True for structured log collection/analysis
    rotate=True,               # enable log rotation
)
```

**Level Guide**

| Log Level | Description                               |
| --------- | ----------------------------------------- |
| DEBUG     | Detailed debugging information            |
| INFO      | General progress information              |
| WARNING   | Potential issue or performance risk       |
| ERROR     | Failure or exception occurred             |
| CRITICAL  | Critical error requiring immediate action |

* Setting level = `DEBUG` prints everything.
* Setting level = `INFO` prints all except DEBUG.

> ✅ Must be called **only once**.
> (Use `force_reconfigure=True` if you need to re-initialize during testing.)

---

## 🧩 Step 2: Prepare a Logger per Module

Insert this snippet at the top of each module:

```python
# fx_loader.py, crypto_loader.py, etc.
from src.utils.logging_config import get_logger
from src.utils.logger import with_context

log = with_context(get_logger(__name__), svc="fx-loader", env="dev")
```

Now any call such as `log.info()` or `log.warning()` inside this file
will automatically include contextual tags like `svc=fx-loader env=dev`.

---

## 🧪 Step 3: Measure Function Runtime (`@timeit`)

Add one decorator line to any long-running or pipeline function:

```python
from src.utils.logger import timeit

@timeit(log, "load_fx_bundle")
def load_fx_bundle():
    # data fetch or transformation
    ...
    return df
```

**Example Output**

```
2025-10-05T05:12:45.321 | INFO | fx_loader | load_fx_bundle done | svc=fx-loader env=dev duration_ms=1584.12 success=True
```

> ⚙️ `success=False` is automatically logged if an exception is raised.

---

## 🌐 Step 4: Log External API Calls (`log_request`)

Add **`log_request()`** before and after HTTP requests.
Ideal for REST data fetches or crawling tasks.

```python
from src.utils.logger import log_request
import requests, time, random

def fetch_fx(symbol="USD/KRW"):
    url = "https://api.example.com/fx"
    params = {"symbol": symbol, "api_key": "SECRET"}

    for attempt in range(3):
        try:
            # before request
            log_request(log, "GET", url, params=params, level="INFO")

            r = requests.get(url, params=params, timeout=5)
            r.raise_for_status()

            # success
            log_request(log, "GET", url, status=r.status_code, note="ok", level="INFO")
            return r.json()

        except requests.HTTPError as e:
            if r.status_code == 429:  # rate limit
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

**Sample Output**

```
2025-10-05T05:14:18.120 | INFO | fx_loader | http_call | svc=fx-loader env=dev method=GET url=https://api.example.com/fx params={'symbol': 'USD/KRW', 'api_key': '***'}
2025-10-05T05:14:18.454 | INFO | fx_loader | http_call | svc=fx-loader env=dev method=GET url=https://api.example.com/fx status=200 note=ok
```

---

## 🔄 Step 5: Integrate into a Higher-Level Pipeline

Example: a function that loads daily FX, DXY, and USDT data together.

```python
@timeit(log, "load_all_markets")
def load_all_markets():
    fx = fetch_fx("USD/KRW")
    dxy = fetch_fx("DXY")
    usdt = fetch_fx("USDT/KRW")
    return {"fx": fx, "dxy": dxy, "usdt": usdt}
```

---

## 📁 Step 6: Separate Logs per Module (optional)

When the project grows, you can separate logs by module name.

| Module        | Logger name     | Log file            | Example                        |
| ------------- | --------------- | ------------------- | ------------------------------ |
| FX Loader     | `fx_loader`     | `logs/fx.log`       | `setup_logging("logs/fx.log")` |
| Crypto Loader | `crypto_loader` | `logs/crypto.log`   | ...                            |
| Backtester    | `backtester`    | `logs/backtest.log` | ...                            |

Or simply keep one file and distinguish by `ctx.svc`.

---

## 🧩 Step 7: Real-time Monitoring

During development, use both console + file outputs.
Tail the file in real time:

```bash
tail -f logs/app.log
```

If using JSON format, pipe it into `jq` for pretty printing:

```bash
python app.py | jq .
```

---

## 🚦 Step 8: Quick Checklist

| Check Item                                                      | Status |
| --------------------------------------------------------------- | ------ |
| Was `setup_logging` called only once?                           | ✅      |
| Did each module use `log = with_context(get_logger(__name__))`? | ✅      |
| Did major functions use `@timeit(log, "name")`?                 | ✅      |
| Did API calls include `log_request()`?                          | ✅      |
| Are exceptions logged with `exc_info=True`?                     | ✅      |
| Is the `logs/` directory auto-created?                          | ✅      |
