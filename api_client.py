# api_client.py — 국토부 실거래가 공공API
import requests
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta


LAWD_CODES = {
    "서울 강남구": "11680", "서울 서초구": "11650", "서울 송파구": "11710",
    "서울 마포구": "11440", "서울 용산구": "11170", "서울 성동구": "11200",
    "서울 노원구": "11350", "서울 강동구": "11740", "서울 영등포구": "11560",
    "경기 성남 분당구": "41135", "경기 수원 영통구": "41117",
    "경기 용인 수지구": "41465", "경기 과천시": "41290",
    "경기 하남시": "41450", "경기 광명시": "41210",
    "인천 연수구": "22380", "인천 서구": "22390",
    "부산 해운대구": "26350", "대구 수성구": "27260",
}

BASE_URL = (
    "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev"
    "/getRTMSDataSvcAptTradeDev"
)


def fetch_trades(service_key: str, lawd_cd: str, months: int = 6) -> pd.DataFrame:
    frames = []
    today  = date.today()
    for i in range(months):
        ym = (today - relativedelta(months=i)).strftime("%Y%m")
        params = {
            "serviceKey": service_key,
            "LAWD_CD":    lawd_cd,
            "DEAL_YMD":   ym,
            "numOfRows":  100,
            "pageNo":     1,
            "_type":      "json",
        }
        try:
            r = requests.get(BASE_URL, params=params, timeout=8)
            body  = r.json().get("response", {}).get("body", {})
            items = body.get("items", {})
            if not items:
                continue
            rows = items.get("item", [])
            if isinstance(rows, dict):
                rows = [rows]
            frames.append(pd.DataFrame(rows))
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    # 정제
    df['deal_amount'] = (
        df['dealAmount'].astype(str).str.replace(',', '').str.strip().astype(float) * 10_000
    )
    df['area'] = pd.to_numeric(df['excluUseAr'], errors='coerce')
    df['deal_date'] = pd.to_datetime(
        df['dealYear'].astype(str) + df['dealMonth'].astype(str).str.zfill(2) + '01'
    )
    df['price_per_m2'] = df['deal_amount'] / df['area']
    df['apt_name']     = df.get('aptNm', '')
    df['floor']        = pd.to_numeric(df.get('floor', 0), errors='coerce')

    return df[['deal_date', 'apt_name', 'area', 'floor', 'deal_amount', 'price_per_m2']].dropna()
