# charts.py — Plotly 인터랙티브 차트 (라이트 테마)
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

LIGHT = dict(
    paper_bgcolor='#ffffff',
    plot_bgcolor='#f8fafc',
    font_color='#1e293b',
    gridcolor='#e2e8f0',
)
SC_COLOR = {
    '낙관 (+12%)': '#059669',
    '기준 (±0%)':  '#2563eb',
    '비관 (-8%)':  '#dc2626',
}


def _base_layout(**kwargs) -> dict:
    return dict(
        paper_bgcolor=LIGHT['paper_bgcolor'],
        plot_bgcolor=LIGHT['plot_bgcolor'],
        font=dict(color=LIGHT['font_color'], family='Noto Sans KR, sans-serif', size=12),
        margin=dict(l=50, r=30, t=50, b=40),
        legend=dict(bgcolor='#f1f5f9', bordercolor='#e2e8f0', borderwidth=1),
        **kwargs,
    )


def chart_profit_line(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for sc, grp in df.groupby('시나리오'):
        fig.add_trace(go.Scatter(
            x=grp['보유기간'], y=grp['세후순수익'] / 10_000,
            mode='lines+markers+text',
            name=sc,
            line=dict(color=SC_COLOR[sc], width=2.5),
            marker=dict(size=8),
            text=[f"{v/10_000:,.0f}만" for v in grp['세후순수익']],
            textposition='top center',
            textfont=dict(size=10, color=SC_COLOR[sc]),
            hovertemplate='%{y:,.0f}만원<extra>' + sc + '</extra>',
        ))
    fig.add_hline(y=0, line_dash='dash', line_color='#94a3b8', opacity=0.6)
    fig.update_layout(
        **_base_layout(title='📈 보유기간별 세후 순수익'),
        xaxis=dict(title='보유기간 (년)', gridcolor=LIGHT['gridcolor'], tickvals=df['보유기간'].unique()),
        yaxis=dict(title='세후 순수익 (만원)', gridcolor=LIGHT['gridcolor']),
    )
    return fig


def chart_roi_bar(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for sc in df['시나리오'].unique():
        sub = df[df['시나리오'] == sc]
        fig.add_trace(go.Bar(
            x=[f"{int(h)}년" for h in sub['보유기간']],
            y=sub['연환산수익률'],
            name=sc,
            marker_color=SC_COLOR[sc],
            text=[f"{v:.1f}%" for v in sub['연환산수익률']],
            textposition='outside',
            textfont=dict(size=10, color=SC_COLOR[sc]),
            hovertemplate='연환산 %{y:.2f}%<extra>' + sc + '</extra>',
        ))
    fig.update_layout(
        **_base_layout(title='📊 연환산 수익률 비교', barmode='group'),
        xaxis=dict(title='보유기간', gridcolor=LIGHT['gridcolor']),
        yaxis=dict(title='연환산 수익률 (%)', gridcolor=LIGHT['gridcolor']),
    )
    return fig


def chart_cost_waterfall(buy: dict, scenario_row: pd.Series) -> go.Figure:
    labels = ['낙찰가', '취득세', '법무·인지세', '명도비용', '수리비',
              '이자비용', '중개수수료', '양도소득세', '세후 순수익']
    values = [
        buy['낙찰가'],
        -buy['취득세'],
        -(buy['법무비용'] + buy['인지세']),
        -buy['명도비용'],
        -buy['수리비'],
        -scenario_row['이자비용'],
        -scenario_row['중개수수료'],
        -scenario_row['양도소득세'],
        scenario_row['세후순수익'],
    ]
    measures = ['absolute'] + ['relative'] * 7 + ['total']

    fig = go.Figure(go.Waterfall(
        name='비용 흐름',
        orientation='v',
        measure=measures,
        x=labels,
        y=[v / 10_000 for v in values],
        connector=dict(line=dict(color='#cbd5e1', dash='dot')),
        increasing=dict(marker_color='#059669'),
        decreasing=dict(marker_color='#dc2626'),
        totals=dict(marker_color='#2563eb'),
        text=[f"{v/10_000:+,.0f}" for v in values],
        textposition='outside',
        textfont=dict(size=10, color='#1e293b'),
    ))
    fig.update_layout(
        **_base_layout(title='💧 비용 흐름 (워터폴)'),
        yaxis=dict(title='금액 (만원)', gridcolor=LIGHT['gridcolor']),
        xaxis=dict(gridcolor=LIGHT['gridcolor']),
    )
    return fig


def chart_realdata_scatter(api_df: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        api_df,
        x='area', y='deal_amount',
        color='apt_name',
        size='price_per_m2',
        hover_data=['deal_date', 'floor'],
        labels={'area': '전용면적(㎡)', 'deal_amount': '거래금액(원)', 'apt_name': '단지명'},
        title='🔍 실거래 데이터 (면적 vs 거래금액)',
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(**_base_layout())
    return fig


def chart_price_trend(api_df: pd.DataFrame) -> go.Figure:
    monthly = (
        api_df.groupby('deal_date')['deal_amount']
        .agg(['mean', 'min', 'max'])
        .reset_index()
    )
    fig = go.Figure([
        go.Scatter(
            x=monthly['deal_date'], y=monthly['max'] / 10_000,
            fill=None, mode='lines',
            line_color='rgba(37,99,235,0.25)', name='최고가',
        ),
        go.Scatter(
            x=monthly['deal_date'], y=monthly['min'] / 10_000,
            fill='tonexty', mode='lines',
            line_color='rgba(37,99,235,0.25)',
            fillcolor='rgba(37,99,235,0.07)', name='최저가',
        ),
        go.Scatter(
            x=monthly['deal_date'], y=monthly['mean'] / 10_000,
            mode='lines+markers',
            line=dict(color='#2563eb', width=2.5),
            marker=dict(size=6), name='평균가',
            hovertemplate='%{x|%Y-%m}<br>평균: %{y:,.0f}만원<extra></extra>',
        ),
    ])
    fig.update_layout(
        **_base_layout(title='📉 월별 실거래가 추이'),
        xaxis=dict(title='거래월', gridcolor=LIGHT['gridcolor']),
        yaxis=dict(title='거래금액 (만원)', gridcolor=LIGHT['gridcolor']),
    )
    return fig
