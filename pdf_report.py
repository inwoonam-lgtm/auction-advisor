# pdf_report.py — ReportLab 기반 PDF 보고서 생성
import io
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 폰트 등록 ─────────────────────────────────────────────
FONT_PATHS = [
    ('/usr/share/fonts/truetype/nanum/NanumGothic.ttf',     'NanumGothic'),
    ('/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf', 'NanumGothicBold'),
]
_fonts_registered = False

def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    for path, name in FONT_PATHS:
        try:
            pdfmetrics.registerFont(TTFont(name, path))
        except Exception:
            pass
    _fonts_registered = True

# ── 색상 팔레트 ───────────────────────────────────────────
C_NAVY   = colors.HexColor('#0d2137')
C_BLUE   = colors.HexColor('#3b82f6')
C_GREEN  = colors.HexColor('#10b981')
C_RED    = colors.HexColor('#ef4444')
C_AMBER  = colors.HexColor('#f59e0b')
C_GRAY   = colors.HexColor('#6e7681')
C_LIGHT  = colors.HexColor('#f1f5f9')
C_BORDER = colors.HexColor('#e2e8f0')
C_WHITE  = colors.white
C_TEXT   = colors.HexColor('#1e293b')
C_TEXT2  = colors.HexColor('#475569')

SC_MPL = {'낙관 (+12%)': '#10b981', '기준 (±0%)': '#3b82f6', '비관 (-8%)': '#ef4444'}

W, H = A4
MARGIN = 18 * mm


# ── 유틸 ──────────────────────────────────────────────────
def fmt_won(v: float) -> str:
    if abs(v) >= 1_0000_0000:
        return f"{v/1_0000_0000:.2f}억원"
    return f"{int(v/10_000):,}만원"

def fmt_pct(v: float) -> str:
    return f"{v:+.1f}%"


# ── Matplotlib 차트 → bytes ────────────────────────────────
def _set_mpl_font():
    nanum_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
    try:
        fe = fm.FontEntry(fname=nanum_path, name='NanumGothic')
        fm.fontManager.ttflist.insert(0, fe)
        plt.rcParams['font.family'] = 'NanumGothic'
    except Exception:
        for f in fm.fontManager.ttflist:
            if 'Nanum' in f.name:
                plt.rcParams['font.family'] = f.name
                break
    plt.rcParams['axes.unicode_minus'] = False

def _fig_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return buf.read()

def _make_profit_chart(df: pd.DataFrame) -> bytes:
    _set_mpl_font()
    fig, ax = plt.subplots(figsize=(7, 3.2))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8fafc')

    for sc, grp in df.groupby('시나리오'):
        ax.plot(grp['보유기간'], grp['세후순수익']/10_000,
                marker='o', linewidth=2, markersize=6,
                color=SC_MPL[sc], label=sc)
        last = grp.iloc[-1]
        ax.annotate(f"{last['세후순수익']/10_000:,.0f}만",
                    xy=(last['보유기간'], last['세후순수익']/10_000),
                    xytext=(5, 2), textcoords='offset points',
                    fontsize=8, color=SC_MPL[sc])

    ax.axhline(0, color='#94a3b8', linewidth=1, linestyle='--')
    ax.set_xlabel('보유기간 (년)', fontsize=9, color='#475569')
    ax.set_ylabel('세후 순수익 (만원)', fontsize=9, color='#475569')
    ax.set_title('보유기간별 세후 순수익', fontsize=11, color='#0f172a', pad=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f'{x:,.0f}'))
    ax.tick_params(colors='#64748b', labelsize=8)
    for sp in ax.spines.values():
        sp.set_color('#e2e8f0')
    ax.grid(axis='y', color='#e2e8f0', alpha=0.8)
    ax.legend(fontsize=8, framealpha=0.9)
    plt.tight_layout()
    data = _fig_bytes(fig)
    plt.close(fig)
    return data

def _make_roi_chart(df: pd.DataFrame) -> bytes:
    _set_mpl_font()
    fig, ax = plt.subplots(figsize=(7, 3.2))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8fafc')

    hold_vals = sorted(df['보유기간'].unique())
    width = 0.25
    offsets = [-1, 0, 1]
    sc_list  = list(SC_MPL.keys())

    for offset, sc in zip(offsets, sc_list):
        sub = df[df['시나리오'] == sc].sort_values('보유기간')
        bars = ax.bar([h + offset*width for h in sub['보유기간']],
                      sub['연환산수익률'], width=width*0.9,
                      color=SC_MPL[sc], alpha=0.85, label=sc, zorder=3)
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x()+bar.get_width()/2, h+0.2,
                    f'{h:.1f}%', ha='center', va='bottom',
                    fontsize=7, color=SC_MPL[sc])

    ax.axhline(0, color='#94a3b8', linewidth=1)
    ax.set_xticks(hold_vals)
    ax.set_xticklabels([f'{int(h)}년' for h in hold_vals], fontsize=8)
    ax.set_ylabel('연환산 수익률 (%)', fontsize=9, color='#475569')
    ax.set_title('연환산 수익률 비교', fontsize=11, color='#0f172a', pad=8)
    ax.tick_params(colors='#64748b', labelsize=8)
    for sp in ax.spines.values():
        sp.set_color('#e2e8f0')
    ax.grid(axis='y', color='#e2e8f0', alpha=0.8, zorder=0)
    ax.legend(fontsize=8, framealpha=0.9)
    plt.tight_layout()
    data = _fig_bytes(fig)
    plt.close(fig)
    return data


# ══════════════════════════════════════════════════════════════
# PDF 빌더
# ══════════════════════════════════════════════════════════════
def build_pdf(inputs: dict, df: pd.DataFrame, buy: dict,
              prop_name: str = "") -> bytes:
    _register_fonts()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=15*mm, bottomMargin=15*mm,
        title="경매 아파트 매도 시나리오 분석 보고서",
    )

    # ── 스타일 ────────────────────────────────────────────
    base = 'NanumGothic'
    bold = 'NanumGothicBold'

    def S(name, font=None, **kw):
        return ParagraphStyle(name, fontName=font or base, **kw)

    sty = {
        'h1':    S('h1', font=bold, fontSize=18, textColor=C_NAVY,
                   spaceAfter=2*mm, leading=24),
        'h2':    S('h2', font=bold, fontSize=12, textColor=C_NAVY,
                   spaceBefore=5*mm, spaceAfter=2*mm, leading=16),
        'h3':    S('h3', font=bold, fontSize=10, textColor=C_TEXT2,
                   spaceBefore=3*mm, spaceAfter=1*mm),
        'body':  S('body', fontSize=9, textColor=C_TEXT, leading=14),
        'small': S('small', fontSize=8, textColor=C_GRAY, leading=12),
        'kpi_v': S('kpi_v', font=bold, fontSize=14, textColor=C_BLUE, leading=18),
        'kpi_l': S('kpi_l', fontSize=8, textColor=C_GRAY, leading=11),
        'notice':S('notice', fontSize=8, textColor=C_GRAY, leading=12,
                   borderPadding=3),
    }

    story = []

    # ══ 헤더 배너 ══════════════════════════════════════════
    title_text = prop_name if prop_name else "경매 아파트 매도 시나리오 분석 보고서"
    banner_data = [[Paragraph(f'<font color="white"><b>{title_text}</b></font>', sty['h1']),
                    Paragraph(f'<font color="#94d3f7" size="8">생성: {datetime.now().strftime("%Y-%m-%d %H:%M")}</font>',
                              sty['small'])]]
    banner = Table(banner_data, colWidths=[W - 2*MARGIN - 30*mm, 30*mm])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_NAVY),
        ('TOPPADDING',    (0,0), (-1,-1), 5*mm),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5*mm),
        ('LEFTPADDING',   (0,0), (-1,-1), 5*mm),
        ('RIGHTPADDING',  (0,0), (-1,-1), 3*mm),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',  (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(banner)
    story.append(Spacer(1, 5*mm))

    # ══ KPI 카드 4개 ═══════════════════════════════════════
    base_rows = df[df['시나리오'].str.contains('기준')]
    first_hy  = min(df['보유기간'])
    b1 = base_rows[base_rows['보유기간'] == first_hy].iloc[0]
    opt_row = df[df['시나리오'].str.contains('낙관') & (df['보유기간'] == first_hy)].iloc[0]
    pes_row = df[df['시나리오'].str.contains('비관') & (df['보유기간'] == first_hy)].iloc[0]

    def kpi_cell(label, value, color=C_BLUE):
        return [
            Paragraph(label, sty['kpi_l']),
            Paragraph(f'<font color="{color.hexval() if hasattr(color,"hexval") else "#3b82f6"}">{value}</font>',
                      sty['kpi_v']),
        ]

    kpi_table = Table([
        [
            Table([kpi_cell('낙찰가',    fmt_won(inputs['bid_price']))],    colWidths=[40*mm]),
            Table([kpi_cell('주변 시세', fmt_won(inputs['market_price']))], colWidths=[40*mm]),
            Table([kpi_cell('기준 순수익 (첫 보유기간)',
                            fmt_won(b1['세후순수익']), C_BLUE)],            colWidths=[50*mm]),
            Table([kpi_cell('낙관 순수익', fmt_won(opt_row['세후순수익']), C_GREEN)],
                  colWidths=[40*mm]),
        ]
    ], colWidths=[42*mm, 42*mm, 54*mm, 42*mm])
    kpi_table.setStyle(TableStyle([
        ('BOX',        (0,0), (0,0), 0.5, C_BORDER),
        ('BOX',        (1,0), (1,0), 0.5, C_BORDER),
        ('BOX',        (2,0), (2,0), 0.5, C_BORDER),
        ('BOX',        (3,0), (3,0), 0.5, C_BORDER),
        ('BACKGROUND', (0,0), (1,0), C_LIGHT),
        ('BACKGROUND', (2,0), (2,0), colors.HexColor('#eff6ff')),
        ('BACKGROUND', (3,0), (3,0), colors.HexColor('#f0fdf4')),
        ('TOPPADDING',    (0,0), (-1,-1), 3*mm),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3*mm),
        ('LEFTPADDING',   (0,0), (-1,-1), 3*mm),
        ('ROUNDEDCORNERS', [3]),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 5*mm))

    # ══ 섹션 1: 입력 정보 요약 ══════════════════════════════
    story.append(Paragraph('1. 물건 정보 요약', sty['h2']))
    story.append(HRFlowable(width='100%', thickness=1, color=C_BORDER))
    story.append(Spacer(1, 2*mm))

    info_data = [
        ['항목', '내용', '항목', '내용'],
        ['낙찰가',    fmt_won(inputs['bid_price']),
         '주변 시세', fmt_won(inputs['market_price'])],
        ['대출 금액', fmt_won(inputs.get('loan_amount', 0)),
         '대출 금리', f"{inputs.get('loan_rate',0.04)*100:.1f}%"],
        ['낙찰가율',  f"{inputs['bid_price']/inputs['market_price']*100:.1f}%",
         '자기자본',  fmt_won(buy['자기자본'])],
        ['1가구1주택', '✓' if inputs.get('is_one_household') else '✗',
         '2년 거주',  '✓' if inputs.get('has_lived_2years') else '✗'],
    ]
    info_tbl = Table(info_data, colWidths=[30*mm, 45*mm, 30*mm, 45*mm])
    info_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_NAVY),
        ('TEXTCOLOR',  (0,0), (-1,0), C_WHITE),
        ('FONTNAME',   (0,0), (-1,0), bold),
        ('FONTSIZE',   (0,0), (-1,-1), 9),
        ('FONTNAME',   (0,1), (0,-1), bold),
        ('FONTNAME',   (2,1), (2,-1), bold),
        ('TEXTCOLOR',  (0,1), (0,-1), C_TEXT2),
        ('TEXTCOLOR',  (2,1), (2,-1), C_TEXT2),
        ('BACKGROUND', (0,1), (-1,-1), C_WHITE),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [C_WHITE, C_LIGHT]),
        ('GRID',       (0,0), (-1,-1), 0.5, C_BORDER),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 2.5*mm),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5*mm),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 5*mm))

    # ══ 섹션 2: 취득비용 ════════════════════════════════════
    story.append(Paragraph('2. 취득비용 상세', sty['h2']))
    story.append(HRFlowable(width='100%', thickness=1, color=C_BORDER))
    story.append(Spacer(1, 2*mm))

    cost_items = [
        ('낙찰가',    buy['낙찰가'],    False),
        ('취득세',    buy['취득세'],    False),
        ('법무비용',  buy['법무비용'],  False),
        ('인지세',    buy['인지세'],    False),
        ('명도비용',  buy['명도비용'],  False),
        ('수리비',    buy['수리비'],    False),
        ('총 투입원가', buy['총투입원가'], True),
    ]
    cost_data = [['항목', '금액', '비율']]
    for name, val, is_total in cost_items:
        pct = val / buy['총투입원가'] * 100
        cost_data.append([name, fmt_won(val), f'{pct:.1f}%'])

    cost_tbl = Table(cost_data, colWidths=[50*mm, 60*mm, 40*mm])
    cost_style = [
        ('BACKGROUND', (0,0), (-1,0), C_NAVY),
        ('TEXTCOLOR',  (0,0), (-1,0), C_WHITE),
        ('FONTNAME',   (0,0), (-1,0), bold),
        ('FONTSIZE',   (0,0), (-1,-1), 9),
        ('GRID',       (0,0), (-1,-1), 0.5, C_BORDER),
        ('ALIGN',      (1,0), (-1,-1), 'RIGHT'),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [C_WHITE, C_LIGHT]),
        ('TOPPADDING',    (0,0), (-1,-1), 2*mm),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2*mm),
        ('LEFTPADDING',   (0,0), (-1,-1), 3*mm),
        # 합계행
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#eff6ff')),
        ('FONTNAME',   (0,-1), (-1,-1), bold),
        ('TEXTCOLOR',  (0,-1), (-1,-1), C_BLUE),
        ('LINEABOVE',  (0,-1), (-1,-1), 1, C_BLUE),
    ]
    cost_tbl.setStyle(TableStyle(cost_style))
    story.append(cost_tbl)
    story.append(Spacer(1, 5*mm))

    # ══ 섹션 3: 시나리오 분석표 ═════════════════════════════
    story.append(Paragraph('3. 보유기간별 시나리오 분석', sty['h2']))
    story.append(HRFlowable(width='100%', thickness=1, color=C_BORDER))
    story.append(Spacer(1, 2*mm))

    sc_headers = ['시나리오', '보유기간', '예상 매도가', '이자비용',
                  '양도소득세', '세후 순수익', '수익률', '연환산']
    sc_data = [sc_headers]
    sc_colors_map = {
        '낙관 (+12%)': colors.HexColor('#f0fdf4'),
        '기준 (±0%)':  colors.HexColor('#eff6ff'),
        '비관 (-8%)':  colors.HexColor('#fff1f2'),
    }
    sc_text_map = {
        '낙관 (+12%)': C_GREEN,
        '기준 (±0%)':  C_BLUE,
        '비관 (-8%)':  C_RED,
    }

    row_colors = []
    for _, row in df.iterrows():
        sc_data.append([
            row['시나리오'],
            f"{row['보유기간']}년",
            fmt_won(row['예상매도가']),
            fmt_won(row['이자비용']),
            fmt_won(row['양도소득세']),
            fmt_won(row['세후순수익']),
            fmt_pct(row['투자수익률']),
            fmt_pct(row['연환산수익률']),
        ])
        row_colors.append(sc_colors_map.get(row['시나리오'], C_WHITE))

    cw = [32*mm, 18*mm, 25*mm, 22*mm, 22*mm, 24*mm, 16*mm, 16*mm]
    sc_tbl = Table(sc_data, colWidths=cw, repeatRows=1)
    sc_style_cmds = [
        ('BACKGROUND', (0,0), (-1,0), C_NAVY),
        ('TEXTCOLOR',  (0,0), (-1,0), C_WHITE),
        ('FONTNAME',   (0,0), (-1,0), bold),
        ('FONTSIZE',   (0,0), (-1,-1), 8.5),
        ('GRID',       (0,0), (-1,-1), 0.4, C_BORDER),
        ('ALIGN',      (1,0), (-1,-1), 'RIGHT'),
        ('ALIGN',      (0,0), (0,-1), 'LEFT'),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 2*mm),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2*mm),
        ('LEFTPADDING',   (0,0), (-1,-1), 2*mm),
    ]
    for i, bg in enumerate(row_colors, start=1):
        sc_style_cmds.append(('BACKGROUND', (0,i), (-1,i), bg))
    sc_tbl.setStyle(TableStyle(sc_style_cmds))
    story.append(sc_tbl)
    story.append(Spacer(1, 5*mm))

    # ══ 섹션 4: 차트 ════════════════════════════════════════
    story.append(Paragraph('4. 시각화', sty['h2']))
    story.append(HRFlowable(width='100%', thickness=1, color=C_BORDER))
    story.append(Spacer(1, 2*mm))

    chart_w = (W - 2*MARGIN - 4*mm) / 2

    profit_bytes = _make_profit_chart(df)
    roi_bytes    = _make_roi_chart(df)

    profit_img = RLImage(io.BytesIO(profit_bytes), width=chart_w, height=chart_w*0.46)
    roi_img    = RLImage(io.BytesIO(roi_bytes),    width=chart_w, height=chart_w*0.46)

    chart_tbl = Table([[profit_img, roi_img]],
                      colWidths=[chart_w, chart_w])
    chart_tbl.setStyle(TableStyle([
        ('ALIGN',  (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',  (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 2*mm),
    ]))
    story.append(chart_tbl)
    story.append(Spacer(1, 5*mm))

    # ══ 섹션 5: 투자 포인트 ═════════════════════════════════
    story.append(Paragraph('5. 투자 포인트 요약', sty['h2']))
    story.append(HRFlowable(width='100%', thickness=1, color=C_BORDER))
    story.append(Spacer(1, 2*mm))

    best = df.loc[df['연환산수익률'].idxmax()]
    be   = df[df['세후순수익'] >= 0]
    be_text = (f"손익분기: {be.sort_values('보유기간').iloc[0]['시나리오']} 기준 "
               f"{be.sort_values('보유기간').iloc[0]['보유기간']}년 보유"
               if not be.empty else "모든 시나리오에서 손실 가능성 있음")

    tips = [
        f"▶ 최고 연환산 수익률: {best['시나리오']} / {best['보유기간']}년 보유 → {fmt_pct(best['연환산수익률'])}",
        f"▶ {be_text}",
        f"▶ 낙찰가율 {inputs['bid_price']/inputs['market_price']*100:.1f}% — "
        + ("시세 대비 충분한 안전마진 확보" if inputs['bid_price']/inputs['market_price'] < 0.88
           else "적정 수준의 낙찰" if inputs['bid_price']/inputs['market_price'] < 0.95
           else "고가 낙찰 — 수익 실현까지 장기 보유 필요"),
    ]
    for tip in tips:
        story.append(Paragraph(tip, sty['body']))
        story.append(Spacer(1, 1.5*mm))

    story.append(Spacer(1, 5*mm))

    # ══ 면책 고지 ═══════════════════════════════════════════
    notice = Table([[
        Paragraph('⚠️  본 보고서는 참고용이며, 세금(취득세·양도세)은 개인 상황에 따라 달라집니다. '
                  '실제 투자 전 세무사 확인을 권장합니다. 분석 기준: 2024년 세법',
                  sty['notice'])
    ]], colWidths=[W - 2*MARGIN])
    notice.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fefce8')),
        ('BOX',        (0,0), (-1,-1), 0.5, C_AMBER),
        ('TOPPADDING',    (0,0), (-1,-1), 2*mm),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2*mm),
        ('LEFTPADDING',   (0,0), (-1,-1), 3*mm),
    ]))
    story.append(notice)

    # ── 빌드 ──────────────────────────────────────────────
    def _add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('NanumGothic', 8)
        canvas.setFillColor(C_GRAY)
        canvas.drawRightString(W - MARGIN, 8*mm,
                               f"{doc.page} / {doc.page}")
        canvas.drawString(MARGIN, 8*mm, "경매 아파트 매도 시나리오 분석 보고서")
        canvas.restoreState()

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    return buf.getvalue()
