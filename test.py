from datetime import date, timedelta
from data_load.exchange_official import get_api_data_FRED
from pathlib import Path
from utils.api_utils import load_env, get_required

ROOT = Path(__file__).resolve().parent   # test.py와 .env가 같은 폴더면 parent == 루트
loaded = load_env(ROOT / ".env", override=True)

API_KEY = get_required("FRED_API_KEY")

def main():
    assert API_KEY, "환경변수 FRED_API_KEY 가 필요합니다."
    start = "2024-10-01"
    end   = (date.today() - timedelta(days=2)).isoformat()
    df = get_api_data_FRED("DEXKOUS", start, end, API_KEY)
    print(df.tail())

if __name__ == "__main__":
    main()
