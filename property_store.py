# property_store.py — 물건 저장 & 비교 관리
import json
import os
from datetime import datetime
from typing import Optional
import pandas as pd

STORE_PATH = os.path.join(os.path.dirname(__file__), 'saved_properties.json')


def _load() -> list:
    if not os.path.exists(STORE_PATH):
        return []
    try:
        with open(STORE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def _save(data: list):
    with open(STORE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_property(name: str, inputs: dict, buy: dict, df_records: list) -> str:
    """물건 저장 → ID 반환"""
    props = _load()
    prop_id = datetime.now().strftime('%Y%m%d%H%M%S')
    entry = {
        'id':         prop_id,
        'name':       name,
        'saved_at':   datetime.now().strftime('%Y-%m-%d %H:%M'),
        'inputs':     inputs,
        'buy':        buy,
        'df_records': df_records,
    }
    props.append(entry)
    _save(props)
    return prop_id


def load_all() -> list:
    return _load()


def delete_property(prop_id: str):
    props = [p for p in _load() if p['id'] != prop_id]
    _save(props)


def get_property(prop_id: str) -> Optional[dict]:
    for p in _load():
        if p['id'] == prop_id:
            return p
    return None


def compare_df(selected_ids: list) -> pd.DataFrame:
    """선택된 물건들의 비교 DataFrame 생성"""
    rows = []
    for p in _load():
        if p['id'] not in selected_ids:
            continue
        df = pd.DataFrame(p['df_records'])
        inp = p['inputs']
        buy = p['buy']

        # 기준 시나리오 2년 보유(또는 가장 가까운) 기준으로 대표값 추출
        target_hy = 2 if 2 in df['보유기간'].values else df['보유기간'].min()
        base = df[df['시나리오'].str.contains('기준') & (df['보유기간'] == target_hy)]
        opt  = df[df['시나리오'].str.contains('낙관') & (df['보유기간'] == target_hy)]
        pes  = df[df['시나리오'].str.contains('비관')  & (df['보유기간'] == target_hy)]

        def v(sub, col, default=0):
            return sub.iloc[0][col] if not sub.empty else default

        rows.append({
            '물건명':           p['name'],
            '저장일':           p['saved_at'],
            '낙찰가':           inp['bid_price'],
            '시세':             inp['market_price'],
            '낙찰가율(%)':      inp['bid_price'] / inp['market_price'] * 100,
            '대출금액':         inp.get('loan_amount', 0),
            '대출금리(%)':      inp.get('loan_rate', 0.04) * 100,
            '자기자본':         buy['자기자본'],
            '취득비용':         buy['기타비용합계'],
            '기준_순수익':      v(base, '세후순수익'),
            '기준_연환산(%)':   v(base, '연환산수익률'),
            '낙관_순수익':      v(opt,  '세후순수익'),
            '낙관_연환산(%)':   v(opt,  '연환산수익률'),
            '비관_순수익':      v(pes,  '세후순수익'),
            '비관_연환산(%)':   v(pes,  '연환산수익률'),
            '_id':              p['id'],
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()
