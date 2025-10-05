# economy-lab

개인 학습 및 실험 목적의 경제 데이터 분석 레포지토리입니다.  
완성된 제품을 만드는 것이 아니라, 작은 기능 단위로 개발 기획 → 의사코드 → 구현 → 디버깅 과정을 반복하며
경제 데이터 분석 및 퀀트 리서치 역량을 기르는 것을 목표로 합니다.

## 📌 목표
- 경제 및 금융 데이터를 다루는 기본기 습득 (ETL, 전처리, 시각화, 단순 분석)
- 기술적 분석 지표 구현 및 크립토 백테스트 실험
- 거시경제 데이터(금리, 환율, GDP, CPI 등) 기반 시뮬레이션

## 🛠 개발 원칙
1. **작게 시작**: 기능을 최소 단위로 나누어 구현한다.
2. **반복 학습**: 기획 → 의사코드 → 코드 작성 → 디버깅 사이클을 반복한다.
3. **기록 중시**: 각 실험은 `/experiments/날짜_기능명/` 폴더에 결과와 리포트를 남긴다.

## 📂 디렉토리 구조(초안)
```

economy-lab/
data/         # 원천/중간/피처 데이터
src/          # 기능별 모듈
tests/        # 유닛 테스트
experiments/  # 실험 기록
reports/      # 그래프, 리포트 산출물

```

## 🚀 진행 방식
- 기능 아이디어가 나오면 `개발 기획` 템플릿을 작성한다.
- 실제 코드는 직접 작성하고, 디버깅은 AI 리뷰와 함께한다.
- 완성된 기능은 실험 리포트와 함께 기록한다.

## ⚠️ 주의
이 레포지토리는 학습 및 개인 연구 목적이며,
여기서 나온 코드나 결과물은 투자 판단에 직접 사용하지 않습니다.


---

This repository is for **personal learning and experiments in economic data analysis**.  
The goal is not to build a finished product, but to strengthen skills by repeating the cycle of  
**feature planning → pseudocode → implementation → debugging** on small, modular tasks.

## 📌 Objectives
- Build core skills in handling economic and financial data (ETL, preprocessing, visualization, basic analysis)  
- Implement technical indicators and run crypto backtest experiments  
- Explore simulations using macroeconomic data (interest rates, FX, GDP, CPI, etc.)  

## 🛠 Development Principles
1. **Start small**: Break down features into the smallest units possible.  
2. **Iterative learning**: Repeat the cycle of planning → pseudocode → coding → debugging.  
3. **Documentation first**: Every experiment leaves artifacts in `/experiments/<date_feature>/` with results and reports.  

## 📂 Initial Directory Structure
```

economy-lab/
data/         # raw/interim/features datasets
src/          # source code modules
tests/        # unit tests
experiments/  # experiment logs and outputs
reports/      # generated plots and reports

```

## 🚀 Workflow
- Draft a **development plan** whenever a new feature idea comes up.  
- Write pseudocode and implement the actual code.  
- Debug with AI-assisted reviews when errors occur.  
- Archive completed experiments with reports and summaries.  

## ⚠️ Disclaimer
This repository is strictly for **learning and research purposes**.  
The code and results should not be used directly for investment decisions.  