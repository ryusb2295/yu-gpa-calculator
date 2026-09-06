# 영남대학교 전공 평점 자동 계산기 (YU GPA Calculator)

영남대학교 학생종합정보시스템 성적표 형식에 맞춘 전체·전공 평점 분석 웹 애플리케이션입니다. 원본 `mintluv/kau_major_credit`의 화면 구성과 기능을 영남대학교용으로 이식했습니다.

## 주요 기능

1. 영남대학교 성적조회 표 붙여넣기 자동 분석
2. 전공핵심·전공선택·전공필수 집계와 편입인정학점 분리
3. 전체·전공 평점 및 이수연차별 분석
4. 과목 추가·수정, 목표 전공 평점 계산
5. 삼성 지원용 Excel 및 SK하이닉스 지원용 텍스트 내보내기
6. 로컬 FastAPI·Playwright 백엔드 실행 시 포털 자동 수집 시도

GitHub Pages에서는 붙여넣기·직접 입력·계산·내보내기가 브라우저 안에서 작동합니다. 자동 수집은 브라우저 자동화를 실행할 별도 백엔드가 필요합니다.

## GitHub Pages

https://ryusb2295.github.io/yu-gpa-calculator/

## 로컬 백엔드 실행

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다.

## 계산 기준

- A+ 4.5, A/A0 4.0, B+ 3.5, B/B0 3.0, C+ 2.5, C/C0 2.0, D+ 1.5, D/D0 1.0, F 0.0
- P·NP와 편입인정학점은 평점 계산에서 제외
- F는 취득학점에서 제외하고 평점 계산에는 0점으로 반영
- 재수강·소멸 과목은 학교 표시를 확인한 뒤 사용자가 결과를 검토해야 합니다.

비공식 보조 도구이며 학교의 공식 성적표나 졸업사정을 대체하지 않습니다.
