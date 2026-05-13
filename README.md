# DGU Portfolio Dashboard

동국대 동기들이 다니는 회사 기준으로 만든 DGU 포트폴리오 정적 웹 대시보드입니다.

## 구성

- `index.html`: 모바일 우선 차트/표 UI, 일/주/월/년 단위 보기
- `scripts/update_data.py`: Yahoo Finance 데이터를 yfinance로 내려받아 `data/portfolio.json` 생성
- `.github/workflows/update-dgu-portfolio.yml`: 매일 한국시간 00:10 자동 갱신
- `data/portfolio.json`: 자동 생성되는 실제 차트 데이터
- `data/price-table.csv`: 자동 생성되는 표 데이터 백업

## 포트폴리오 산식

- 시작 기준: 2020-01-01 이후 첫 거래일 종가
- DGU 포트폴리오: 아래 국내 종목을 각각 1주씩 매수했다고 가정
- 차트: 모든 종목과 지수를 시작점 100으로 정규화
- 수익률: 가격 수익률 기준. 배당, 세금, 거래비용 미반영

## 종목

| 이름 | Yahoo Finance 티커 |
|---|---|
| 삼성전자 | 005930.KS |
| SK하이닉스 | 000660.KS |
| 기아 | 000270.KS |
| 신한지주 | 055550.KS |
| 아모레퍼시픽 | 090430.KS |
| 스카이라이프 | 053210.KS |
| CJ ENM | 035760.KQ |
| 신원 | 009270.KS |
| 동양고속 | 084670.KS |
| 유니드 | 014830.KS |
| 한샘 | 009240.KS |
| 서연이화 | 200880.KS |
| 삼양식품 | 003230.KS |
| 코스피 | ^KS11 |
| S&P 500 | ^GSPC |
| 나스닥 | ^IXIC |

## 배포 방법: GitHub Pages

1. 새 GitHub repository 생성
2. 이 폴더의 파일을 그대로 업로드
3. repository `Settings` → `Pages` → `Build and deployment`에서 `Deploy from a branch` 선택
4. Branch는 `main`, folder는 `/root`로 설정
5. `Actions` 탭 → `Update DGU Portfolio Data` → `Run workflow` 1회 수동 실행
6. 이후 매일 한국시간 00:10에 자동으로 `data/portfolio.json`이 갱신됩니다.

## 로컬 테스트

```bash
pip install -r requirements.txt
python scripts/update_data.py
python -m http.server 8000
```

브라우저에서 `http://localhost:8000` 접속.

## 참고

GitHub Actions의 cron은 UTC 기준입니다. 이 프로젝트는 `cron: '10 15 * * *'`로 설정되어 있으며, 이는 한국시간 00:10입니다.
