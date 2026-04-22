# app.py — 경매 아파트 매도 시나리오 분석 Streamlit 앱
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from engine import ScenarioEngine
from charts import (
    chart_profit_line, chart_roi_bar,
    chart_cost_waterfall, chart_realdata_scatter, chart_price_trend,
)
from api_client import fetch_trades, LAWD_CODES
from pdf_report import build_pdf
from property_store import (
    save_property, load_all, delete_property, compare_df
)

# ── 페이지 설정 ────────────────────────────────────────────
st.set_page_config(
    page_title="경매 AI 어드바이저",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 글로벌 CSS ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif !important; }

/* 메트릭 카드 */
[data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 12px 16px !important;
}
[data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 700; }

/* 탭 */
[data-testid="stTabs"] button { font-size: 13px; }
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #3b82f6 !important;
    border-bottom: 2px solid #3b82f6;
}

/* 사이드바 */
[data-testid="stSidebar"] { background: #0d1117; }
[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

/* 경고/성공 배너 */
.stAlert { border-radius: 8px !important; }

/* 테이블 */
.dataframe th { background: #1f2937 !important; color: #8b949e !important; }
.dataframe td { font-size: 12.5px !important; }

/* 구분선 */
hr { border-color: #30363d !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 유틸
# ══════════════════════════════════════════════════════════════
def fmt_won(v: float) -> str:
    if abs(v) >= 1_0000_0000:
        return f"{v/1_0000_0000:.2f}억원"
    return f"{int(v/10_000):,}만원"

def fmt_pct(v: float) -> str:
    return f"{v:+.1f}%"

def delta_color(v: float) -> str:
    return "normal" if v >= 0 else "inverse"


# ══════════════════════════════════════════════════════════════
# 사이드바 — 입력 패널
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🏠 물건 정보 입력")
    st.markdown("---")

    st.markdown("#### 💰 가격 정보")
    bid_price    = st.number_input("낙찰가 (만원)", min_value=1000, max_value=200000,
                                   value=25000, step=500) * 10_000
    market_price = st.number_input("주변 시세 (만원)", min_value=1000, max_value=200000,
                                   value=32000, step=500) * 10_000
    bid_rate     = bid_price / market_price * 100

    col1, col2 = st.columns(2)
    col1.metric("낙찰가율", f"{bid_rate:.1f}%",
                delta=f"{'저가' if bid_rate < 85 else '적정' if bid_rate < 95 else '고가'}")

    st.markdown("#### 🏦 대출 정보")
    loan_amount = st.number_input("대출 금액 (만원)", min_value=0, max_value=150000,
                                  value=15000, step=500) * 10_000
    loan_rate   = st.slider("대출 금리 (%)", 2.0, 8.0, 4.0, 0.1) / 100
    ltv         = loan_amount / bid_price * 100 if bid_price > 0 else 0
    st.caption(f"LTV: **{ltv:.1f}%** | 자기자본: **{fmt_won(bid_price - loan_amount + bid_price*0.015)}**")

    st.markdown("#### 🔧 부대비용")
    evict_cost  = st.number_input("명도비용 (만원)", 0, 5000, 150, 50) * 10_000
    repair_cost = st.number_input("수리비 (만원)", 0, 10000, 200, 100) * 10_000
    legal_fee   = st.number_input("법무비용 (만원)", 0, 500, 40, 10) * 10_000

    st.markdown("#### ⚖️ 세금 조건")
    is_first_home    = st.checkbox("생애최초 주택 취득", False)
    is_one_household = st.checkbox("1가구 1주택", True)
    has_lived_2years = st.checkbox("2년 이상 거주 예정", False)
    if has_lived_2years:
        st.success("✅ 1가구 1주택 비과세 조건 충족 가능 (12억 이하)")

    st.markdown("#### 📅 분석 보유기간")
    hold_options = st.multiselect(
        "보유기간 선택 (복수)",
        [0.5, 1, 1.5, 2, 3, 5, 7, 10],
        default=[1, 2, 3, 5],
        format_func=lambda x: f"{x}년"
    )
    if not hold_options:
        st.warning("보유기간을 1개 이상 선택하세요.")
        hold_options = [1, 2, 3, 5]

    st.markdown("---")
    st.markdown("#### 🔌 공공 API 연동 (선택)")
    api_key    = st.text_input("공공데이터포털 서비스키", type="password",
                               placeholder="발급받은 API 키 입력")
    lawd_label = st.selectbox("지역 선택", list(LAWD_CODES.keys()), index=9)
    fetch_btn  = st.button("📡 실거래가 조회", use_container_width=True,
                           disabled=not bool(api_key))


# ══════════════════════════════════════════════════════════════
# 계산 실행
# ══════════════════════════════════════════════════════════════
inputs = dict(
    bid_price=bid_price, market_price=market_price,
    loan_amount=loan_amount, loan_rate=loan_rate,
    eviction_cost=evict_cost, repair_cost=repair_cost,
    legal_fee=legal_fee, stamp_tax=150_000,
    is_first_home=is_first_home, is_one_household=is_one_household,
    has_lived_2years=has_lived_2years, hold_years_list=hold_options,
)
engine = ScenarioEngine(inputs)
df, buy = engine.run()


# ══════════════════════════════════════════════════════════════
# 헤더
# ══════════════════════════════════════════════════════════════
st.markdown("# 🏠 경매 아파트 매도 시나리오 분석")
st.markdown(f"낙찰가 **{fmt_won(bid_price)}** | 시세 **{fmt_won(market_price)}** | "
            f"낙찰가율 **{bid_rate:.1f}%** | 대출 **{fmt_won(loan_amount)}** ({loan_rate*100:.1f}%)")
st.markdown("---")


# ══════════════════════════════════════════════════════════════
# 탭 구성
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 시나리오 분석", "💧 비용 흐름", "🏗️ 취득비용 상세",
    "📡 실거래 데이터", "💾 물건 저장·비교", "📄 PDF 보고서"
])


# ────────────────────────────────────────────────────────────
# TAB 1 — 시나리오 분석
# ────────────────────────────────────────────────────────────
with tab1:
    st.markdown("### 핵심 지표 요약")

    # 기준 시나리오, 첫 번째 hold_years 기준 KPI
    base_row = df[(df['시나리오'].str.contains('기준')) & (df['보유기간'] == min(hold_options))]
    if not base_row.empty:
        base_row = base_row.iloc[0]
        opt_row  = df[(df['시나리오'].str.contains('낙관')) & (df['보유기간'] == min(hold_options))].iloc[0]
        pes_row  = df[(df['시나리오'].str.contains('비관')) & (df['보유기간'] == min(hold_options))].iloc[0]

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("🎯 기준 순수익", fmt_won(base_row['세후순수익']),
                    delta=fmt_pct(base_row['연환산수익률']) + " (연환산)")
        kpi2.metric("🟢 낙관 순수익", fmt_won(opt_row['세후순수익']),
                    delta=fmt_pct(opt_row['연환산수익률']) + " (연환산)")
        kpi3.metric("🔴 비관 순수익", fmt_won(pes_row['세후순수익']),
                    delta=fmt_pct(pes_row['연환산수익률']) + " (연환산)",
                    delta_color=delta_color(pes_row['세후순수익']))
        kpi4.metric("💵 자기자본", fmt_won(buy['자기자본']),
                    delta=f"LTV {ltv:.1f}%")

    st.markdown("---")

    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(chart_profit_line(df), use_container_width=True)
    with col_r:
        st.plotly_chart(chart_roi_bar(df), use_container_width=True)

    st.markdown("### 전체 시나리오 테이블")

    # 표시용 DataFrame 가공
    display_df = df.copy()
    display_df['예상매도가']    = display_df['예상매도가'].apply(fmt_won)
    display_df['세후순수익']    = display_df['세후순수익'].apply(fmt_won)
    display_df['양도소득세']    = display_df['양도소득세'].apply(fmt_won)
    display_df['이자비용']      = display_df['이자비용'].apply(fmt_won)
    display_df['투자수익률']    = display_df['투자수익률'].apply(fmt_pct)
    display_df['연환산수익률']  = display_df['연환산수익률'].apply(fmt_pct)
    display_df['보유기간']      = display_df['보유기간'].apply(lambda x: f"{x}년")

    show_cols = ['시나리오','보유기간','예상매도가','이자비용','양도소득세','세후순수익','투자수익률','연환산수익률']
    st.dataframe(display_df[show_cols], hide_index=True, use_container_width=True)

    # 손익분기 계산
    be = df[df['세후순수익'] >= 0]
    if not be.empty:
        be_first = be.sort_values('보유기간').iloc[0]
        st.success(
            f"✅ **손익분기점**: {be_first['시나리오']} 기준 "
            f"**{be_first['보유기간']}년 보유** 시 세후 {fmt_won(be_first['세후순수익'])} 순수익"
        )
    else:
        st.error("⚠️ 모든 시나리오에서 손실이 발생합니다. 낙찰가 재검토가 필요합니다.")


# ────────────────────────────────────────────────────────────
# TAB 2 — 비용 흐름 워터폴
# ────────────────────────────────────────────────────────────
with tab2:
    st.markdown("### 비용 흐름 분석 (워터폴)")
    st.caption("선택한 시나리오·보유기간의 매도가에서 각 비용이 차감되는 흐름을 시각화합니다.")

    c1, c2 = st.columns(2)
    sc_select  = c1.selectbox("시나리오", df['시나리오'].unique(), index=1)
    hy_select  = c2.selectbox("보유기간", sorted(df['보유기간'].unique()),
                               index=min(1, len(df['보유기간'].unique())-1),
                               format_func=lambda x: f"{x}년")

    sel_row = df[(df['시나리오'] == sc_select) & (df['보유기간'] == hy_select)]
    if not sel_row.empty:
        st.plotly_chart(chart_cost_waterfall(buy, sel_row.iloc[0]), use_container_width=True)

        # 비용 상세 표
        r = sel_row.iloc[0]
        cost_detail = {
            '항목': ['낙찰가', '취득세', '법무·인지세', '명도비용', '수리비',
                    '이자비용', '중개수수료', '양도소득세', '▶ 세후 순수익'],
            '금액': [
                fmt_won(buy['낙찰가']),
                fmt_won(buy['취득세']),
                fmt_won(buy['법무비용'] + buy['인지세']),
                fmt_won(buy['명도비용']),
                fmt_won(buy['수리비']),
                fmt_won(r['이자비용']),
                fmt_won(r['중개수수료']),
                fmt_won(r['양도소득세']),
                fmt_won(r['세후순수익']),
            ]
        }
        st.dataframe(pd.DataFrame(cost_detail), hide_index=True, use_container_width=False)


# ────────────────────────────────────────────────────────────
# TAB 3 — 취득비용 상세
# ────────────────────────────────────────────────────────────
with tab3:
    st.markdown("### 취득비용 상세 내역")
    equity = buy['자기자본']

    m1, m2, m3 = st.columns(3)
    m1.metric("총 투입원가", fmt_won(buy['총투입원가']))
    m2.metric("기타비용 합계", fmt_won(buy['기타비용합계']),
              delta=f"취득가의 {buy['기타비용합계']/bid_price*100:.1f}%")
    m3.metric("실투자 자기자본", fmt_won(equity))

    st.markdown("---")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.markdown("#### 항목별 내역")
        items = [
            ("낙찰가",    buy['낙찰가']),
            ("취득세",    buy['취득세']),
            ("법무비용",  buy['법무비용']),
            ("인지세",    buy['인지세']),
            ("명도비용",  buy['명도비용']),
            ("수리비",    buy['수리비']),
        ]
        for name, val in items:
            pct = val / buy['총투입원가'] * 100
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;"
                f"padding:8px 0;border-bottom:1px solid #30363d;font-size:13px'>"
                f"<span style='color:#8b949e'>{name}</span>"
                f"<span><b>{fmt_won(val)}</b> <span style='color:#6e7681;font-size:11px'>({pct:.1f}%)</span></span>"
                f"</div>",
                unsafe_allow_html=True
            )
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"padding:12px 0;font-size:15px;font-weight:700;color:#3b82f6'>"
            f"<span>총 투입원가</span><span>{fmt_won(buy['총투입원가'])}</span></div>",
            unsafe_allow_html=True
        )

    with col_b:
        import plotly.graph_objects as go
        labels = ['취득세', '법무·인지세', '명도비용', '수리비']
        values = [buy['취득세'], buy['법무비용']+buy['인지세'],
                  buy['명도비용'], buy['수리비']]
        fig_pie = go.Figure(go.Pie(
            labels=labels, values=values,
            hole=0.5,
            marker_colors=['#3b82f6','#6366f1','#f59e0b','#10b981'],
            textinfo='label+percent',
            textfont=dict(size=12, color='#e6edf3'),
        ))
        fig_pie.update_layout(
            paper_bgcolor='#0d1117', font=dict(color='#e6edf3'),
            title='부대비용 구성', margin=dict(t=40, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # 취득세 계산 근거
    with st.expander("📋 취득세 계산 근거"):
        if bid_price < 6_0000_0000:
            tax_rate, tier = "1.0%", "6억 미만"
        elif bid_price < 9_0000_0000:
            tax_rate, tier = "2.0%", "6억~9억"
        else:
            tax_rate, tier = "3.0%", "9억 초과"
        st.markdown(f"""
        - 낙찰가 구간: **{tier}** → 세율 **{tax_rate}**
        - 취득세 산출액: {fmt_won(bid_price)} × {tax_rate} = **{fmt_won(buy['취득세'])}**
        - 생애최초 감면: {'✅ 적용 (최대 200만원 감면)' if is_first_home else '❌ 미적용'}
        - ※ 농어촌특별세(0.2%) 및 지방교육세(0.1%)는 별도 부과될 수 있습니다.
        """)


# ────────────────────────────────────────────────────────────
# TAB 4 — 실거래 데이터
# ────────────────────────────────────────────────────────────
with tab4:
    st.markdown("### 📡 국토부 실거래가 데이터")

    # 세션 상태에 API 데이터 보관
    if 'api_df' not in st.session_state:
        st.session_state.api_df = pd.DataFrame()

    if fetch_btn and api_key:
        with st.spinner(f"'{lawd_label}' 최근 6개월 실거래 데이터 조회 중..."):
            lawd_cd = LAWD_CODES[lawd_label]
            try:
                st.session_state.api_df = fetch_trades(api_key, lawd_cd, months=6)
                if st.session_state.api_df.empty:
                    st.warning("해당 지역·기간의 실거래 데이터가 없습니다.")
            except Exception as e:
                st.error(f"API 오류: {e}")

    api_df = st.session_state.api_df

    if api_df.empty:
        st.info("""
        **공공데이터포털 API키를 사이드바에 입력하면 실거래 데이터가 표시됩니다.**
        
        📌 발급 방법:
        1. [data.go.kr](https://www.data.go.kr) 접속 → 회원가입
        2. `아파트매매 실거래자료` 검색 → 활용신청
        3. 발급된 서비스키를 사이드바에 입력
        """)
    else:
        avg_price = api_df['deal_amount'].mean()
        med_price = api_df['deal_amount'].median()
        avg_m2    = api_df['price_per_m2'].mean()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("조회 건수", f"{len(api_df):,}건")
        m2.metric("평균 거래가", fmt_won(avg_price))
        m3.metric("중위 거래가", fmt_won(med_price))
        m4.metric("㎡당 평균가", f"{avg_m2/10_000:.0f}만원/㎡")

        col_l, col_r = st.columns(2)
        with col_l:
            st.plotly_chart(chart_price_trend(api_df), use_container_width=True)
        with col_r:
            st.plotly_chart(chart_realdata_scatter(api_df), use_container_width=True)

        st.markdown("#### 최근 실거래 목록")
        display_api = api_df.sort_values('deal_date', ascending=False).head(30).copy()
        display_api['거래월']    = display_api['deal_date'].dt.strftime('%Y-%m')
        display_api['거래금액']  = display_api['deal_amount'].apply(fmt_won)
        display_api['㎡당가격']  = display_api['price_per_m2'].apply(
            lambda x: f"{x/10_000:.0f}만/㎡")
        display_api['전용면적']  = display_api['area'].apply(lambda x: f"{x:.1f}㎡")
        st.dataframe(
            display_api[['거래월','apt_name','전용면적','floor','거래금액','㎡당가격']]
            .rename(columns={'apt_name':'단지명','floor':'층'}),
            hide_index=True, use_container_width=True
        )

        if st.button("📥 CSV 저장"):
            csv = api_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("⬇ 다운로드", csv, "실거래데이터.csv", "text/csv")



# ────────────────────────────────────────────────────────────
# TAB 5 — 물건 저장 & 비교
# ────────────────────────────────────────────────────────────
with tab5:
    st.markdown("### 💾 물건 저장 & 비교")
    st.caption("현재 입력된 물건을 저장하고, 여러 물건을 한눈에 비교할 수 있습니다.")

    # ── 저장 폼 ──────────────────────────────────────────
    with st.expander("📌 현재 물건 저장하기", expanded=True):
        prop_name = st.text_input("물건 이름 (예: 천안 두정동 OO아파트 101동)", placeholder="물건 이름 입력")
        if st.button("💾 저장", use_container_width=False, disabled=not bool(prop_name)):
            save_property(
                name=prop_name,
                inputs=inputs,
                buy=buy,
                df_records=df.to_dict('records'),
            )
            st.success(f"✅ '{prop_name}' 저장 완료!")
            st.rerun()

    st.markdown("---")

    # ── 저장된 물건 목록 ──────────────────────────────────
    all_props = load_all()
    if not all_props:
        st.info("저장된 물건이 없습니다. 위에서 현재 물건을 저장해보세요.")
    else:
        st.markdown(f"#### 저장된 물건 ({len(all_props)}건)")

        # 목록 + 삭제
        for p in all_props:
            inp_p = p['inputs']
            bid_r = inp_p['bid_price'] / inp_p['market_price'] * 100
            col_name, col_info, col_del = st.columns([3, 5, 1])
            col_name.markdown(f"**{p['name']}**  \n<span style='color:#6e7681;font-size:11px'>{p['saved_at']}</span>",
                              unsafe_allow_html=True)
            col_info.markdown(
                f"낙찰가 **{int(inp_p['bid_price']/10000):,}만** | "
                f"시세 **{int(inp_p['market_price']/10000):,}만** | "
                f"낙찰가율 **{bid_r:.1f}%** | "
                f"대출 **{int(inp_p.get('loan_amount',0)/10000):,}만**"
            )
            if col_del.button("🗑️", key=f"del_{p['id']}", help="삭제"):
                delete_property(p['id'])
                st.rerun()

        st.markdown("---")

        # ── 비교 분석 ─────────────────────────────────────
        st.markdown("#### 📊 물건 비교 분석")
        compare_names = {p['name']: p['id'] for p in all_props}
        selected_names = st.multiselect(
            "비교할 물건 선택 (2개 이상 권장)",
            list(compare_names.keys()),
            default=list(compare_names.keys())[:min(3, len(compare_names))],
        )

        if selected_names:
            selected_ids = [compare_names[n] for n in selected_names]
            cdf = compare_df(selected_ids)

            if not cdf.empty:
                def fw(v): return f"{int(v/10000):,}만원"
                def fp(v): return f"{v:+.1f}%"

                # KPI 비교 메트릭
                st.markdown("##### 핵심 지표 비교 (기준 시나리오 · 2년 보유)")
                metric_cols = st.columns(len(cdf))
                for col, (_, row) in zip(metric_cols, cdf.iterrows()):
                    col.metric(
                        row['물건명'][:10],
                        fw(row['기준_순수익']),
                        delta=fp(row['기준_연환산(%)']) + " 연환산",
                    )

                # 비교 테이블
                st.markdown("##### 전체 비교표")
                show = cdf[[
                    '물건명','낙찰가','시세','낙찰가율(%)','자기자본',
                    '기준_순수익','기준_연환산(%)','낙관_연환산(%)','비관_연환산(%)'
                ]].copy()
                show['낙찰가']        = show['낙찰가'].apply(fw)
                show['시세']          = show['시세'].apply(fw)
                show['낙찰가율(%)']   = show['낙찰가율(%)'].apply(lambda x: f"{x:.1f}%")
                show['자기자본']      = show['자기자본'].apply(fw)
                show['기준_순수익']   = show['기준_순수익'].apply(fw)
                show['기준_연환산(%)']= show['기준_연환산(%)'].apply(fp)
                show['낙관_연환산(%)']= show['낙관_연환산(%)'].apply(fp)
                show['비관_연환산(%)']= show['비관_연환산(%)'].apply(fp)
                st.dataframe(show, hide_index=True, use_container_width=True)

                # 레이더 차트 (수익률 비교)
                if len(cdf) >= 2:
                    st.markdown("##### 🕸️ 수익률 레이더 비교")
                    categories = ['낙관 연환산', '기준 연환산', '비관 연환산',
                                  '낙찰가율(역산)', '자기자본 효율']
                    fig_radar = go.Figure()
                    for _, row in cdf.iterrows():
                        # 낙찰가율은 낮을수록 좋으니 역산 (100-낙찰가율)
                        bid_score  = max(0, 100 - row['낙찰가율(%)'])
                        eq_eff = row['기준_순수익'] / row['자기자본'] * 100 if row['자기자본'] > 0 else 0
                        vals = [
                            max(0, row['낙관_연환산(%)']),
                            max(0, row['기준_연환산(%)']),
                            max(0, row['비관_연환산(%)']),
                            bid_score,
                            max(0, eq_eff),
                        ]
                        fig_radar.add_trace(go.Scatterpolar(
                            r=vals + [vals[0]],
                            theta=categories + [categories[0]],
                            fill='toself', opacity=0.5,
                            name=row['물건명'][:12],
                        ))
                    fig_radar.update_layout(
                        paper_bgcolor='#0d1117',
                        polar=dict(
                            bgcolor='#161b22',
                            radialaxis=dict(visible=True, color='#6e7681'),
                            angularaxis=dict(color='#8b949e'),
                        ),
                        font=dict(color='#e6edf3', family='Noto Sans KR'),
                        legend=dict(bgcolor='#1f2937', bordercolor='#30363d'),
                        margin=dict(t=40, b=20),
                        height=400,
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)

                # CSV 내보내기
                csv_bytes = cdf.drop(columns=['_id']).to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 비교표 CSV 저장", csv_bytes, "물건비교.csv", "text/csv")


# ────────────────────────────────────────────────────────────
# TAB 6 — PDF 보고서 출력
# ────────────────────────────────────────────────────────────
with tab6:
    st.markdown("### 📄 PDF 보고서 출력")
    st.caption("현재 분석 결과를 A4 PDF 보고서로 저장합니다.")

    col_a, col_b = st.columns([2, 1])
    pdf_name = col_a.text_input(
        "보고서 제목 (물건명)",
        placeholder="예: 천안 두정동 OO아파트 101동",
        value=""
    )

    include_chart = col_b.checkbox("차트 포함", value=True)

    st.markdown("#### 미리보기 — 포함 내용")
    preview_cols = st.columns(4)
    preview_cols[0].success("✅ 입력 정보 요약")
    preview_cols[1].success("✅ 취득비용 상세")
    preview_cols[2].success("✅ 시나리오 분석표")
    preview_cols[3].success("✅ 수익률 차트" if include_chart else "☑️ 차트 제외")

    st.markdown("---")

    if st.button("📄 PDF 생성 및 다운로드", use_container_width=True, type="primary"):
        with st.spinner("PDF 생성 중..."):
            try:
                pdf_bytes = build_pdf(
                    inputs=inputs,
                    df=df,
                    buy=buy,
                    prop_name=pdf_name if pdf_name else "경매 아파트 매도 시나리오 분석 보고서",
                )
                file_name = f"{pdf_name or '경매분석보고서'}.pdf"
                st.download_button(
                    label="⬇️ PDF 다운로드",
                    data=pdf_bytes,
                    file_name=file_name,
                    mime="application/pdf",
                    use_container_width=True,
                )
                st.success(f"✅ PDF 생성 완료! 위 버튼을 클릭해 다운로드하세요.")
            except Exception as e:
                st.error(f"PDF 생성 오류: {e}")

    st.markdown("---")
    st.markdown("#### 📋 보고서 구성")
    st.markdown("""
    | 섹션 | 내용 |
    |---|---|
    | 헤더 배너 | 물건명 + 생성일시 |
    | KPI 카드 | 낙찰가 / 시세 / 기준 순수익 / 낙관 순수익 |
    | 1. 물건 정보 | 가격·대출·세금조건 요약표 |
    | 2. 취득비용 | 취득세·법무·명도·수리비 내역 |
    | 3. 시나리오 분석 | 낙관/기준/비관 × 보유기간 전체표 |
    | 4. 시각화 | 순수익 꺾은선 + 연환산 막대 차트 |
    | 5. 투자 포인트 | 최고 수익률·손익분기 자동 해석 |
    """)


# ── 푸터 ──────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#6e7681;font-size:11px'>"
    "⚠️ 본 분석은 참고용이며 실제 세금은 개인 상황에 따라 다릅니다. "
    "투자 전 세무사 확인을 권장합니다."
    "</div>",
    unsafe_allow_html=True,
)
