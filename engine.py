# engine.py — 비용 계산 & 시나리오 엔진
import pandas as pd


class CostEngine:

    @staticmethod
    def acquisition_tax(price: float, is_first_home: bool = False) -> float:
        if price < 6_0000_0000:
            rate = 0.01
        elif price < 9_0000_0000:
            rate = 0.02
        else:
            rate = 0.03
        tax = price * rate
        if is_first_home and price < 12_0000_0000:
            tax = max(0, tax - 2_000_000)
        return tax

    @staticmethod
    def _progressive_rate(gain: float) -> float:
        brackets = [
            (14_000_000,    0.06),
            (50_000_000,    0.15),
            (88_000_000,    0.24),
            (150_000_000,   0.35),
            (300_000_000,   0.38),
            (500_000_000,   0.40),
            (1_000_000_000, 0.42),
            (float('inf'),  0.45),
        ]
        tax, prev = 0, 0
        for limit, rate in brackets:
            if gain <= prev:
                break
            tax += (min(gain, limit) - prev) * rate
            prev = limit
        return tax

    @staticmethod
    def capital_gains_tax(
        cost_basis: float,
        sell_price: float,
        hold_years: float,
        is_one_household: bool = True,
        has_lived_2years: bool = False,
    ) -> float:
        gain = sell_price - cost_basis
        if gain <= 0:
            return 0
        if is_one_household and has_lived_2years and sell_price <= 12_0000_0000:
            return 0
        if hold_years < 1:
            return gain * 0.70
        if hold_years < 2:
            return gain * 0.60
        # 장기보유특별공제 (3년↑, 연 2%, 최대 30%)
        deduction = min(0.30, max(0, (hold_years - 2) * 0.02)) if hold_years >= 3 else 0
        taxable = gain * (1 - deduction)
        return CostEngine._progressive_rate(taxable)

    @staticmethod
    def brokerage_fee(sell_price: float) -> float:
        if sell_price < 5_000_0000:
            return sell_price * 0.006
        elif sell_price < 9_0000_0000:
            return sell_price * 0.005
        else:
            return min(sell_price * 0.009, 9_000_000)

    @staticmethod
    def loan_interest(loan: float, rate: float, years: float) -> float:
        return loan * rate * years


class ScenarioEngine:

    SCENARIO_MULT = {'낙관 (+12%)': 1.12, '기준 (±0%)': 1.00, '비관 (-8%)': 0.92}

    def __init__(self, inputs: dict):
        self.i = inputs
        self.ce = CostEngine()

    def buy_costs(self) -> dict:
        i = self.i
        acq = self.ce.acquisition_tax(i['bid_price'], i.get('is_first_home', False))
        legal  = i.get('legal_fee', 400_000)
        evict  = i.get('eviction_cost', 1_500_000)
        repair = i.get('repair_cost', 2_000_000)
        stamp  = i.get('stamp_tax', 150_000)
        total_extra = acq + legal + evict + repair + stamp
        return {
            '낙찰가':      i['bid_price'],
            '취득세':      acq,
            '법무비용':    legal,
            '명도비용':    evict,
            '수리비':      repair,
            '인지세':      stamp,
            '기타비용합계': total_extra,
            '총투입원가':  i['bid_price'] + total_extra,
            '자기자본':    i['bid_price'] - i.get('loan_amount', 0) + total_extra,
        }

    def run(self) -> pd.DataFrame:
        i   = self.i
        buy = self.buy_costs()
        records = []

        for sc_label, mult in self.SCENARIO_MULT.items():
            sell_price = i['market_price'] * mult
            for hy in i['hold_years_list']:
                interest = self.ce.loan_interest(
                    i.get('loan_amount', 0), i.get('loan_rate', 0.04), hy)
                broker = self.ce.brokerage_fee(sell_price)
                cgt    = self.ce.capital_gains_tax(
                    buy['총투입원가'], sell_price, hy,
                    i.get('is_one_household', True),
                    i.get('has_lived_2years', False))
                total_cost = buy['기타비용합계'] + interest + broker + cgt
                net_profit = sell_price - i['bid_price'] - total_cost
                equity = buy['자기자본']
                roi    = (net_profit / equity * 100) if equity > 0 else 0
                annual_roi = roi / hy if hy > 0 else 0

                records.append({
                    '시나리오':       sc_label,
                    '보유기간':       hy,
                    '예상매도가':     sell_price,
                    '이자비용':       interest,
                    '중개수수료':     broker,
                    '양도소득세':     cgt,
                    '총부대비용':     total_cost,
                    '세후순수익':     net_profit,
                    '투자수익률':     roi,
                    '연환산수익률':   annual_roi,
                })

        return pd.DataFrame(records), buy
