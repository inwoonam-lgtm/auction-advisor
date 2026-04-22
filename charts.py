# charts.py — Plotly 인터랙티브 차트
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

DARK = dict(
    paper_bgcolor='#0d1117',
    plot_bgcolor='#161b22',
    font_color='#e6edf3',
    gridcolor='#30363d',
)
SC_COLOR = {
    '낙관 (+12%)': '#10b981',
    '기준 (±0%)':  '#3b82f6',
    '비관 (-8%)':  '#ef4444',
}


def _base_layout(**kwargs) -> dict:
    return dict(
        paper_bgcolor=DARK['paper_bgcolor'],
        plot_bgcolor=DARK['plot_bgcolor'],
        font=dict(color=DARK['font_color'], family='Noto Sans KR, sans-serif', size=12),
        margin=dict(l=50, r=30, t=50, b=40),
        legend=dict(bgcolor='#1f2937', bordercolor='#30363d', borderwidth=1),
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
    fig.add_hline(y=0, line_dash='dash', line_color='#6e7681', opacity=0.6)
    fig.update_layout(
        **_base_layout(title='📈 보유기간별 세후 순수익'),
        xaxis=dict(title='보유기간 (년)', gridcolor=DARK['gridcolor'], tickvals=df['보유기간'].unique()),
        yaxis=dict(title='세후 순수익 (만원)', gridcolor=DARK['gridcolor']),
    )
    return fig


def chart_roi_bar(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    hold_vals = sorted(df['보유기간'].unique())
    for sc in df['시나리오'].unique():
        sub = df[df['시나리오'] == sc]
        fig.add_trace(go.Bar(
            x=[f"{int(h)}년" for h in sub['보유기간']],
            y=sub['연환산수익률'],
            name=sc,
            marker_color=SC_COLOR[sc],
            text=[f"{v:.1f}%" for v in sub['연환산수익률']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='연환산 %{y:.2f}%<extra>' + sc + '</extra>',
        ))
    fig.update_layout(
        **_base_layout(title='📊 연환산 수익률 비교', barmode='group'),
        xaxis=dict(title='보유기간', gridcolor=DARK['gridcolor']),
        yaxis=dict(title='연환산 수익률 (%)', gridcolor=DARK['gridcolor']),
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
    colors = ['#3b82f6'] + ['#ef4444'] * 7 + ['#10b981' if values[-1] >= 0 else '#ef4444']

    fig = go.Figure(go.Waterfall(
        name='비용 흐름',
        orientation='v',
        measure=measures,
        x=labels,
        y=[v / 10_000 for v in values],
        connector=dict(line=dict(color='#30363d', dash='dot')),
        increasing=dict(marker_color='#10b981'),
        decreasing=dict(marker_color='#ef4444'),
        totals=dict(marker_color='#3b82f6'),
        text=[f"{v/10_000:+,.0f}" for v in values],
        textposition='outside',
        textfont=dict(size=10),
    ))
    fig.update_layout(
        **_base_layout(title='💧 비용 흐름 (워터폴)'),
        yaxis=dict(title='금액 (만원)', gridcolor=DARK['gridcolor']),
        xaxis=dict(gridcolor=DARK['gridcolor']),
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
    fig.update_traces(
        hovertemplate='<b>%{customdata[0]|%Y-%m}</b><br>면적: %{x:.1f}㎡<br>'
                      '금액: %{y:,.0f}원<br>층: %{customdata[1]}<extra></extra>'
    )
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
            fill=None, mode='lines', line_color='rgba(59,130,246,0.3)', name='최고가',
        ),
        go.Scatter(
            x=monthly['deal_date'], y=monthly['min'] / 10_000,
            fill='tonexty', mode='lines', line_color='rgba(59,130,246,0.3)',
            fillcolor='rgba(59,130,246,0.08)', name='최저가',
        ),
        go.Scatter(
            x=monthly['deal_date'], y=monthly['mean'] / 10_000,
            mode='lines+markers', line=dict(color='#3b82f6', width=2.5),
            marker=dict(size=6), name='평균가',
            hovertemplate='%{x|%Y-%m}<br>평균: %{y:,.0f}만원<extra></extra>',
        ),
    ])
    fig.update_layout(
        **_base_layout(title='📉 월별 실거래가 추이'),
        xaxis=dict(title='거래월', gridcolor=DARK['gridcolor']),
        yaxis=dict(title='거래금액 (만원)', gridcolor=DARK['gridcolor']),
    )
    return fig
