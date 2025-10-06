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
def get_api_data_FRED():
    return

# pagination
def pagination_exchange_Fred():
    return

# 원/달러 환율 불러오기(FRED api)
def FRED_exchange_data_loader():
    return

# 달러인덱스 불러오기(FRED api)
def FRED_dollar_index_data_loader():
    return

# 달러인덱스에 따른 원화인덱스 데이터 계산
def won_index_data_calculator():
    return

# 2개 데이터 통합(일단위 환율, 달러인덱스, 달러인덱스에 따른 원화인덱스 데이터)
def integrative_FRED_exchange_data():
    return