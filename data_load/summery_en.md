# 🇺🇸 English Version — Binance Crypto Data Loader

## Data Schema (returned `DataFrame`)

* **Index** – `open_time` (KST, tz-aware)
* **Columns** – `open, high, low, close, volume, close_time (KST), quote_volume, trades (Int64), taker_buy_base, taker_buy_quote`
* **Order / Duplicates** – Sorted ascending by time, duplicate indices removed
* **Missing Values** – Rows with missing core fields (`open, high, low, close, volume`) are dropped

---

## Module Structure & Function Usage

### 1  `time_parser(time: str | int) → int`

**Purpose** – Parses a timestamp (string or epoch ms) as **KST**, then converts it to **UTC epoch milliseconds**.

**Input Formats**

* `"YYYY-MM-DD HH:MM"` or `"YYYY-MM-DD"` (defaults to `00:00` if time omitted)
* `int` (only epoch milliseconds accepted)

**Raises** – `ValueError` or `TypeError` for invalid type/format, negative or epoch seconds.

**Example**

```python
st = time_parser("2024-01-05 00:00")   # KST → UTC ms
et = time_parser("2025-08-18 16:54")   # KST → UTC ms
```

---

### 2  `get_api_data_binance(base_url: str, path: str, params: dict, timeout=10.0, max_retries=3) → pd.DataFrame`

**Purpose** – Fetches and normalizes **one page** of Klines data from Binance, returning a DataFrame.

**Key Behaviors**

* Implements **exponential back-off retries** on HTTP 429/5xx/network errors; honors `Retry-After` header
* If response `[]`, returns an **empty DF** with the proper KST schema
* Converts numeric strings → floats, parses `open_time/close_time` to UTC timestamps, sets index & sorts, drops duplicates and missing core rows

**Returns** – A single-page DataFrame with UTC index (later converted to KST by caller) or an empty DF with matching schema.

---

### 3  `pagination(base_url, path, symbol, interval, st, et, limit) → pd.DataFrame`

**Purpose** – Collects an entire date range by splitting it into multiple pages and merging all DataFrames.

**Main Logic**

* Maps `interval_ms` for minutes/hours/days/weeks (`1M` excluded)
* **Boundary snap** → `first = ceil(start, k)`, `last = floor(end, k)`
* Calculates **expected rows** and logs summary
* Advances `current = last_page_open + k` safely; applies **stall guard** (`last_open_ms ≤ current`)
* Concatenates pages → `sort_index` → remove duplicates
* Drops records beyond `end` (“inclusive” policy)
* Converts both `open_time` index and `close_time` column to **KST** for consistent output

**Parameters**

* `interval` ∈ `{1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w}`
* `limit` – if None, defaults to 1000 (page size)
* `st`, `et` – UTC milliseconds from `time_parser`

**Returns** – Merged DataFrame for the full period, KST-indexed with unified schema.

---

### 4  `crypto_data_loader(symbol, interval, start_time, end_time, market="spot", limit=None, max_retries=3, timeout=10.0) → pd.DataFrame`

**Purpose (top-level API)** – Validates parameters → selects endpoint (Spot/Futures) → parses times → runs pagination → returns final DataFrame.

**Validation**

* `market`: `'spot' | 'futures'`
* `interval`: allowed set (excludes monthly `1M`)
* `limit`: `1 – 1000` (None → 1000)
* `start_time ≤ end_time`

**Returns** – Standardized DataFrame with KST index.

**Example**

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
