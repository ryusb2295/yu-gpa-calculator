import asyncio
import json
import re
import uuid
from typing import List, Optional

from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Yeungnam University GPA Calculator API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")


class Course(BaseModel):
    id: str
    name: str
    credits: float
    grade: str
    is_major: bool = True
    classification: str = "미분류"
    year_semester: Optional[str] = ""
    code: Optional[str] = ""
    retake: Optional[str] = "본수강"


class CrawlRequest(BaseModel):
    portal_url: str = "https://std.yu.ac.kr/"
    user_id: str
    password: str
    headless: bool = False
    id_selector: Optional[str] = "input[name='userId'], input[name='id'], #userId, #id, input[type='text']"
    pw_selector: Optional[str] = "input[name='password'], input[name='pw'], #password, #pw, input[type='password']"
    login_btn_selector: Optional[str] = "button[type='submit'], input[type='submit'], #loginBtn, .login_btn, button:has-text('로그인')"
    grade_url: Optional[str] = None
    auto_navigate_grade: bool = True


class ParseTextRequest(BaseModel):
    text: str


class GoalSimulationRequest(BaseModel):
    current_major_gpa: float
    current_major_credits: float
    target_major_gpa: float
    remaining_major_credits: float
    scale: float = 4.5


GRADES = {"A+", "A0", "A", "B+", "B0", "B", "C+", "C0", "C", "D+", "D0", "D", "F", "P", "NP"}
MAJOR_WORDS = ("전공핵심", "전공선택", "전공필수", "전필", "전선")
CLASS_MAP = {"전필": "전공필수", "전선": "전공선택", "교필": "교양필수", "교선": "교양선택", "일선": "일반선택"}


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/style.css")
async def css():
    return FileResponse("static/style.css", media_type="text/css")


@app.get("/app.js")
async def javascript():
    return FileResponse("static/app.js", media_type="application/javascript")


@app.get("/health")
async def health():
    return {"ok": True, "school": "영남대학교"}


def semester_label(value: str) -> str:
    value = str(value or "").strip()
    if value in {"1", "1학기"}:
        return "1학기"
    if value in {"2", "2학기"}:
        return "2학기"
    if "여름" in value or "하계" in value:
        return "여름학기"
    if "겨울" in value or "동계" in value:
        return "겨울학기"
    return value or "학기미상"


def make_course(year: str, semester: str, classification: str, code: str, name: str, credit: str, grade: str, tail: str = "") -> Optional[Course]:
    grade = grade.strip().upper()
    try:
        credits = float(credit)
    except (TypeError, ValueError):
        return None
    if not name.strip() or credits <= 0 or grade not in GRADES:
        return None
    classification = CLASS_MAP.get(classification.strip(), classification.strip())
    if not classification:
        classification = "편입인정학점" if "편입인정" in name or "편입" in semester else "미분류"
    is_major = any(word in classification for word in MAJOR_WORDS)
    return Course(
        id=str(uuid.uuid4())[:8], name=name.strip(), credits=credits, grade=grade,
        is_major=is_major, classification=classification,
        year_semester=f"{year}년 {semester_label(semester)}", code=code.strip(),
        retake="재수강" if "재수강" in tail else "본수강"
    )


def parse_yu_text(raw: str) -> List[Course]:
    courses: List[Course] = []
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or re.search(r"교과목명.*학점.*등급", line) or re.match(r"^(년도|연도)\s", line):
            continue
        cols = [x.strip() for x in (line.split("\t") if "\t" in line else re.split(r"\s{2,}", line))]
        course = None
        if len(cols) >= 7 and re.fullmatch(r"20\d{2}", cols[0]):
            course = make_course(cols[0], cols[1], cols[2], cols[3], cols[4], cols[5], cols[6], " ".join(cols[7:]))
        else:
            match = re.match(
                r"^(20\d{2})\s+(\S+)\s+(?:(전공핵심|전공선택|전공필수|전공기초|교양필수|교양선택|일반선택|전필|전선|교필|교선|일선)\s+)?"
                r"([A-Za-z0-9_-]+)\s+(.+?)\s+(\d+(?:\.\d+)?)\s+(A\+|A0?|B\+|B0?|C\+|C0?|D\+|D0?|F|NP|P)(?:\s+\d+(?:\.\d+)?)?(?:\s+(.*))?$",
                line, re.IGNORECASE
            )
            if match:
                course = make_course(*match.groups(default=""))
        if course:
            courses.append(course)
    return courses


def extract_yu_courses(html: str) -> List[Course]:
    soup = BeautifulSoup(html, "html.parser")
    courses: List[Course] = []
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select(":scope > th, :scope > td")]
        if len(cells) < 7 or not re.fullmatch(r"20\d{2}", cells[0]):
            continue
        course = make_course(cells[0], cells[1], cells[2], cells[3], cells[4], cells[5], cells[6], " ".join(cells[7:]))
        if course:
            courses.append(course)
    return courses


async def click_grade_menu(page, log):
    keywords = ["성적관리", "성적조회", "전체성적조회", "누적성적조회", "학기별성적조회"]
    for _ in range(2):
        clicked = False
        for frame in [page] + page.frames:
            for keyword in keywords:
                try:
                    item = frame.get_by_text(keyword, exact=True).first
                    if await item.count():
                        await item.click(timeout=2000)
                        await log(f"      - '{keyword}' 메뉴 선택")
                        await asyncio.sleep(2)
                        clicked = True
                        break
                except Exception:
                    continue
            if clicked:
                break


async def run_crawler_core(req: CrawlRequest, emit_log=None):
    logs, courses = [], []

    async def log(message: str):
        logs.append(message)
        if emit_log:
            await emit_log(message)

    await log("🚀 [1/4] 브라우저를 시작합니다.")
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        message = "Playwright가 없습니다. pip install -r requirements.txt 후 python -m playwright install chromium을 실행하세요."
        await log(f"❌ {message}")
        return {"success": False, "logs": logs, "courses": [], "error": message}

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=req.headless, args=["--start-maximized"] if not req.headless else [])
            context = await browser.new_context(no_viewport=True) if not req.headless else await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await context.new_page()
            await log("🌐 [2/4] 영남대학교 학생종합정보시스템에 접속합니다.")
            await page.goto(req.portal_url or "https://std.yu.ac.kr/", wait_until="domcontentloaded", timeout=45000)
            id_input = page.locator(req.id_selector or "input[type='text']").first
            pw_input = page.locator(req.pw_selector or "input[type='password']").first
            await id_input.wait_for(state="visible", timeout=15000)
            await id_input.fill(req.user_id)
            await pw_input.fill(req.password)
            try:
                await page.locator(req.login_btn_selector or "button[type='submit']").first.click(timeout=3000)
            except Exception:
                await pw_input.press("Enter")
            await log("🔑 [3/4] 로그인을 요청했습니다. 추가 인증이 보이면 열린 브라우저에서 완료하세요.")
            await asyncio.sleep(6)
            if req.grade_url:
                await page.goto(req.grade_url, wait_until="domcontentloaded", timeout=30000)
            elif req.auto_navigate_grade:
                await click_grade_menu(page, log)
            await asyncio.sleep(5)
            await log("📚 [4/4] 성적조회 표를 읽습니다.")
            for frame in [page] + page.frames:
                try:
                    courses.extend(extract_yu_courses(await frame.content()))
                except Exception:
                    continue
            unique = {}
            for course in courses:
                unique[(course.year_semester, course.code, course.name)] = course
            courses = list(unique.values())
            await browser.close()
            if not courses:
                message = "성적 행을 찾지 못했습니다. 붙여넣기 기능을 사용하거나 고급 설정에 성적 조회 URL을 입력해 주세요."
                await log(f"⚠️ {message}")
                return {"success": False, "logs": logs, "courses": [], "error": message}
            await log(f"✅ {len(courses)}개 과목을 수집했습니다.")
            return {"success": True, "logs": logs, "courses": [c.model_dump() for c in courses], "message": f"{len(courses)}개 과목 수집 완료"}
    except Exception as exc:
        await log(f"❌ 자동 수집 오류: {exc}")
        return {"success": False, "logs": logs, "courses": [], "error": str(exc)}


@app.post("/api/crawl")
async def crawl(req: CrawlRequest):
    return await run_crawler_core(req)


@app.post("/api/crawl-stream")
async def crawl_stream(req: CrawlRequest):
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(message: str):
        await queue.put({"type": "log", "message": message})

    async def task():
        result = await run_crawler_core(req, emit)
        await queue.put({"type": "done", "result": result})

    async def events():
        runner = asyncio.create_task(task())
        while True:
            item = await queue.get()
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            if item["type"] == "done":
                break
        await runner

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/parse-text")
async def parse_text(req: ParseTextRequest):
    courses = parse_yu_text(req.text)
    return {"success": bool(courses), "courses": [c.model_dump() for c in courses]}


@app.post("/api/simulate-goal")
async def simulate_goal(req: GoalSimulationRequest):
    if req.remaining_major_credits <= 0:
        return {"possible": False, "message": "남은 전공 이수 학점은 1 이상이어야 합니다."}
    required = (req.target_major_gpa * (req.current_major_credits + req.remaining_major_credits) - req.current_major_gpa * req.current_major_credits) / req.remaining_major_credits
    possible = required <= req.scale
    if possible:
        message = f"남은 {req.remaining_major_credits:g}학점에서 평균 {max(0, required):.2f} / {req.scale:.2f}가 필요합니다."
    else:
        message = f"필요 평균이 {required:.2f}로 {req.scale:.2f} 만점을 초과하여 현재 조건으로는 달성할 수 없습니다."
    return {"possible": possible, "required_average": round(required, 4), "message": message}
