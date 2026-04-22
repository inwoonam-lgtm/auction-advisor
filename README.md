# 🏠 경매 아파트 매도 시나리오 분석기 v4 (Streamlit)

## 실행 방법

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 앱 실행
streamlit run app.py
```
→ 브라우저에서 http://localhost:8501 자동 열림

---

## 파일 구조
```
auction_streamlit/
├── app.py              # Streamlit 메인 앱 (6탭)
├── engine.py           # 비용 계산 & 시나리오 엔진
├── charts.py           # Plotly 인터랙티브 차트
├── api_client.py       # 국토부 실거래가 공공API
├── pdf_report.py       # ReportLab PDF 보고서 생성
├── property_store.py   # 물건 저장/비교 (JSON 로컬 저장)
├── requirements.txt
└── .streamlit/
    └── config.toml     # 다크 테마
```

---

## 탭 구성 (6탭)
| 탭 | 내용 |
|---|---|
| 📊 시나리오 분석 | KPI + 꺾은선/막대 차트 + 전체 테이블 |
| 💧 비용 흐름 | 워터폴 차트 (시나리오·보유기간 선택) |
| 🏗️ 취득비용 상세 | 항목별 내역 + 도넛 차트 + 취득세 근거 |
| 📡 실거래 데이터 | 국토부 API 실거래 조회 + CSV 저장 |
| 💾 물건 저장·비교 | 물건 저장/삭제 + 레이더 차트 비교 |
| 📄 PDF 보고서 | A4 PDF 다운로드 (한글 폰트 NanumGothic) |

---

## PDF 한글 폰트
- Linux: `apt install fonts-nanum` (자동 감지)
- Windows: NanumGothic 설치 후 경로를 pdf_report.py에서 수정
- Mac: `/Library/Fonts/NanumGothic.ttf` 경로 수정

## 공공 API 연동
1. data.go.kr → `아파트매매 실거래자료` 활용신청
2. 발급 서비스키 → 사이드바 입력
3. 지역 선택 → 📡 실거래가 조회

⚠️ 세금 계산은 참고용, 실제 투자 전 세무사 확인 권장
