# -*- coding: utf-8 -*-
"""
app.py - STLABS & Stratio Biz-Intelligence System
=====================================================
Streamlit 기반 4-Tab 레이아웃 메인 애플리케이션

실행: streamlit run app.py
"""

import os
import sys
import json
import logging
import re
from datetime import datetime, date
from dotenv import load_dotenv

import streamlit as st

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from database.dao import ProjectDAO, ExhibitionDAO, get_connection, init_database
from core.file_parser import FileParser
from intelligence.ai_analyzer import AIAnalyzer

# ── 환경 변수 로드 ──
load_dotenv()

# ── 유틸리티 함수 ──
def _convert_to_google_chat_format(text: str) -> str:
    """
    표준 마크다운을 Google Chat 호환 텍스트로 변환합니다.
    """
    if not text:
        return ""
        
    lines = text.split('\n')
    converted_lines = []
    
    for line in lines:
        # 1. 헤더 변환
        # H1 (#) -> *제목* (볼드)
        h1_match = re.match(r'^#\s+(.+)', line)
        if h1_match:
            content = h1_match.group(1)
            line = f"*{content}*"
        else:
            # H2~H6 (##...) -> 제목 (볼드 제거)
            header_match = re.match(r'^#+\s+(.+)', line)
            if header_match:
                line = header_match.group(1)
        
        # 2. 볼드체 변환 (**text** -> *text*)
        line = re.sub(r'\*\*(.+?)\*\*', r'*\1*', line)
        
        # 3. 불릿 포인트 변환 (- 항목 -> • 항목)
        line = re.sub(r'^[\-\*]\s+', '• ', line)
        
        converted_lines.append(line)
        
    return '\n'.join(converted_lines)

# ── 로깅 설정 ──
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# 페이지 설정
# ═══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Biz-Intelligence System",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ═══════════════════════════════════════════════════════════
# 커스텀 CSS (프리미엄 다크 테마)
# ═══════════════════════════════════════════════════════════

def inject_custom_css():
    """프리미엄 UI 스타일 주입"""
    st.markdown("""
    <style>
    /* ── 전역 폰트 및 배경 ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* ── 메트릭 카드 스타일 ── */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
    }
    
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #60a5fa;
    }
    
    /* ── 배지 스타일 ── */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 4px;
    }
    .badge-fire { background: #ef4444; color: white; }
    .badge-blue { background: #3b82f6; color: white; }
    .badge-green { background: #10b981; color: white; }
    .badge-yellow { background: #f59e0b; color: #1e293b; }
    .badge-purple { background: #8b5cf6; color: white; }
    .badge-gray { background: #475569; color: #e2e8f0; }
    
    /* ── 점수 게이지 ── */
    .score-gauge {
        background: linear-gradient(90deg, #ef4444, #f59e0b, #10b981);
        height: 8px;
        border-radius: 4px;
        margin: 8px 0;
        position: relative;
    }
    .score-marker {
        position: absolute;
        top: -6px;
        width: 20px;
        height: 20px;
        background: white;
        border-radius: 50%;
        border: 3px solid #3b82f6;
        transform: translateX(-50%);
    }
    
    /* ── 전략 박스 ── */
    .strategy-box {
        padding: 16px 20px;
        border-radius: 12px;
        margin: 12px 0;
        font-size: 0.9rem;
        border-left: 4px solid;
    }
    .strategy-internal {
        background: rgba(16, 185, 129, 0.1);
        border-color: #10b981;
        color: #a7f3d0;
    }
    .strategy-academic {
        background: rgba(245, 158, 11, 0.1);
        border-color: #f59e0b;
        color: #fde68a;
    }
    .strategy-external {
        background: rgba(59, 130, 246, 0.1);
        border-color: #3b82f6;
        color: #bfdbfe;
    }
    
    /* ── stExpander  ── */
    .streamlit-expanderHeader {
        font-weight: 600;
        font-size: 1rem;
    }
    
    /* ── 카드 ── */
    .project-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .project-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.4);
    }
    
    /* ── 사이드바 스타일 ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    
    /* ── 프로그레스 바 ── */
    .stProgress > div > div {
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        border-radius: 4px;
    }
    
    /* ── 탭 스타일 ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════════════════

def get_db():
    """데이터베이스 연결을 세션 상태에서 관리합니다."""
    if "db_conn" not in st.session_state:
        conn = get_connection(config.DB_PATH)
        init_database(conn)
        st.session_state.db_conn = conn
    return st.session_state.db_conn


def get_project_dao():
    """ProjectDAO 인스턴스를 반환합니다."""
    return ProjectDAO(conn=get_db())


def get_exhibition_dao():
    """ExhibitionDAO 인스턴스를 반환합니다."""
    return ExhibitionDAO(conn=get_db())


def calc_dday(end_date_str: str) -> str:
    """마감일까지 남은 일수를 D-Day 형식으로 반환합니다."""
    if not end_date_str:
        return ""
    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        diff = (end_date - date.today()).days
        if diff < 0:
            return "마감"
        elif diff == 0:
            return "D-Day"
        else:
            return f"D-{diff}"
    except ValueError:
        return ""


def score_color(score: int) -> str:
    """점수에 따른 색상 클래스를 반환합니다."""
    if score >= 80:
        return "badge-fire"
    elif score >= 60:
        return "badge-blue"
    elif score >= 40:
        return "badge-yellow"
    else:
        return "badge-gray"


def render_badges(project: dict):
    """프로젝트에 대한 배지를 HTML로 생성합니다."""
    badges = []
    score = project.get("suitability_score", 0)
    if score and score > 0:
        cls = score_color(score)
        badges.append(f'<span class="badge {cls}">🔥 {score}점</span>')

    entity = project.get("target_entity", "")
    if entity == "STLABS":
        badges.append('<span class="badge badge-blue">💻 STLABS</span>')
    elif entity == "Stratio":
        badges.append('<span class="badge badge-purple">🔬 Stratio</span>')

    dday = calc_dday(project.get("end_date", ""))
    if dday and dday != "마감":
        badges.append(f'<span class="badge badge-green">{dday}</span>')
    elif dday == "마감":
        badges.append('<span class="badge badge-gray">마감</span>')

    return " ".join(badges)


def render_strategy_box(strategy: dict):
    """컨소시엄 전략을 스타일 박스로 렌더링합니다."""
    if not strategy or not isinstance(strategy, dict):
        return

    strategy_type = strategy.get("type", "").lower()
    description = strategy.get("description", "")

    if "internal" in strategy_type or "synergy" in strategy_type:
        css_class = "strategy-internal"
        icon = "🤝"
    elif "academic" in strategy_type:
        css_class = "strategy-academic"
        icon = "🎓"
    elif "external" in strategy_type:
        css_class = "strategy-external"
        icon = "🌐"
    else:
        css_class = "strategy-external"
        icon = "📋"

    st.markdown(
        f'<div class="strategy-box {css_class}">'
        f'{icon} <strong>{strategy.get("type", "전략")}</strong><br>{description}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════
# Sidebar (Control Panel)
# ═══════════════════════════════════════════════════════════

def render_sidebar():
    """PRD 5.1: Sidebar (Control Panel)"""
    with st.sidebar:
        st.markdown("## 🧠 Biz-Intelligence")
        st.markdown("**STLABS & Stratio**")
        st.divider()

        # ── Status Dashboard ──
        dao = get_project_dao()
        total_count = dao.count_projects()
        today_str = date.today().strftime("%Y-%m-%d")

        # 금일 신규 공고 수
        all_projects = dao.get_all_projects()
        today_count = sum(
            1 for p in all_projects
            if p.get("created_at", "").startswith(today_str)
        )

        col1, col2 = st.columns(2)
        with col1:
            st.metric("📊 전체 공고", f"{total_count}건")
        with col2:
            st.metric("🆕 금일 신규", f"{today_count}건")

        st.caption(f"🕐 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        st.divider()

        # ── Action Button: 데이터 최신화 ──
        if st.button("🔄 데이터 최신화", use_container_width=True, type="primary"):
            with st.spinner("크롤러 실행 중..."):
                try:
                    from collectors.bizinfo_crawler import BizinfoCrawler
                    from collectors.board_crawler import MultiSiteCrawler

                    results = []

                    # 기업마당 API 크롤링
                    if config.BIZINFO_API_KEY:
                        biz_crawler = BizinfoCrawler()
                        results.extend(biz_crawler.crawl(page_count=3))

                    # 게시판 크롤링
                    multi = MultiSiteCrawler()
                    results.extend(multi.crawl_all(pages_per_site=1))

                    # DB 저장
                    saved = 0
                    for item in results:
                        pid = dao.insert_project(item)
                        if pid:
                            saved += 1

                    st.success(f"✅ 수집 완료: {len(results)}건 중 {saved}건 신규 저장")
                except Exception as e:
                    st.error(f"❌ 크롤링 오류: {e}")

        st.divider()

        # ── Keyword Manager: 제외 키워드 관리 ──
        st.markdown("### 🏷️ 제외 키워드")
        st.caption("노이즈로 분류할 키워드를 관리합니다.")

        # 현재 키워드 표시
        keywords_str = ", ".join(config.NOISE_KEYWORDS)
        st.markdown(f"현재: `{keywords_str}`")

        new_keyword = st.text_input(
            "키워드 추가",
            placeholder="예: 행사, 교육",
            label_visibility="collapsed",
        )
        if new_keyword and st.button("➕ 추가"):
            if new_keyword not in config.NOISE_KEYWORDS:
                config.NOISE_KEYWORDS.append(new_keyword)
                st.success(f"'{new_keyword}' 추가됨")
                st.rerun()


# ═══════════════════════════════════════════════════════════
# Tab 1: 실험실 (Manual Validator)
# ═══════════════════════════════════════════════════════════

def render_tab_lab():
    """PRD 5.2: Tab 1 - 🧪 실험실 (Manual Validator)"""
    st.markdown("## 🧪 실험실 (Manual Validator)")
    

    st.markdown("공고 URL 또는 파일을 업로드하여 AI 분석을 수행합니다. (동시 입력 가능)")

    # ── session_state 초기화 ──
    if "lab_parsed_text" not in st.session_state:
        st.session_state.lab_parsed_text = ""
    if "lab_analysis_result" not in st.session_state:
        st.session_state.lab_analysis_result = None
    if "lab_input_hash" not in st.session_state:
        st.session_state.lab_input_hash = ""

    # ── 통합 입력 폼 ──
    col_input1, col_input2 = st.columns([1, 1])
    
    with col_input1:
        st.markdown("### 🌐 URL 입력")
        url_input = st.text_input(
            "공고 URL",
            placeholder="https://www.example.com/notice/1234",
            label_visibility="collapsed",
        )
    
    with col_input2:
        st.markdown("### 📂 파일 업로드 (다중 선택 가능)")
        uploaded_files = st.file_uploader(
            "첨부파일",
            type=["hwp", "hwpx", "pdf"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            help="여러 파일을 한 번에 업로드할 수 있습니다.",
        )

    # 메타 정보 입력
    st.caption("공고 기본 정보 (선택사항)")
    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        title_input = st.text_input("공고 제목", placeholder="AI 플랫폼 개발 지원사업", key="lab_title")
    with col_meta2:
        agency_input = st.text_input("기관명", placeholder="NIPA", key="lab_agency")

    # ── 텍스트 추출 및 결합 로직 ──
    # 입력 변경 감지 (URL + 파일명/크기 조합)
    current_input_hash = f"{url_input}_" + "_".join([f"{f.name}_{f.size}" for f in uploaded_files])
    
    if st.session_state.lab_input_hash != current_input_hash:
        # 입력이 변경되었으므로 다시 파싱
        combined_text = []
        
        # 1. URL 텍스트
        if url_input:
            combined_text.append(f"=== [URL 공고] {url_input} ===\n")
        
        # 2. 파일 텍스트
        if uploaded_files:
            import hashlib
            os.makedirs(config.TEMP_DIR, exist_ok=True)
            parser = FileParser()
            
            for uploaded_file in uploaded_files:
                try:
                    # 안전한 임시 파일 저장
                    safe_name = hashlib.md5(uploaded_file.name.encode()).hexdigest()
                    ext = os.path.splitext(uploaded_file.name)[1]
                    temp_path = os.path.join(config.TEMP_DIR, f"{safe_name}{ext}")
                    
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # 파싱
                    parsed = parser.parse(temp_path)
                    combined_text.append(f"\n=== [첨부파일: {uploaded_file.name}] ===\n{parsed}")
                except Exception as e:
                    st.error(f"❌ '{uploaded_file.name}' 파싱 오류: {e}")

        # 결과 저장
        st.session_state.lab_parsed_text = "\n".join(combined_text)
        st.session_state.lab_input_hash = current_input_hash
        
        # 입력이 바뀌면 이전 분석 결과는 초기화 (사용자 혼동 방지)
        # 단, 파싱만 하고 분석은 안 한 상태일 수 있으므로 명시적 초기화
        st.session_state.lab_analysis_result = None

        if st.session_state.lab_parsed_text:
            st.success(f"✅ 텍스트 추출 완료 ({len(st.session_state.lab_parsed_text):,}자)")

    st.divider()

    # ── 분석 시작 버튼 ──
    text_to_analyze = st.session_state.lab_parsed_text
    
    # 미리보기 (접기)
    if text_to_analyze:
        with st.expander("📄 추출된 텍스트 미리보기", expanded=False):
            st.text(text_to_analyze[:3000] + ("..." if len(text_to_analyze) > 3000 else ""))

    if st.button("🚀 AI 분석 시작", type="primary", use_container_width=True):
        if not text_to_analyze or len(text_to_analyze.strip()) < 10:
            st.warning("⚠️ 분석할 내용이 없습니다. URL을 입력하거나 파일을 업로드하세요.")
            return

        with st.spinner("🤖 AI가 공고를 분석 중입니다... (10~20초 소요)"):
            try:
                analyzer = AIAnalyzer()
                # 제목/기관명이 비어있으면 파일명/URL 등에서 유추할 수도 있지만, 일단 입력값 사용
                result = analyzer.analyze(
                    text=text_to_analyze,
                    title=title_input,
                    agency=agency_input,
                )
                st.session_state.lab_analysis_result = result
            except Exception as e:
                st.error(f"❌ 분석 오류: {e}")
                return

    # ── 분석 결과 리포트 ──
    result = st.session_state.lab_analysis_result
    if result:
        st.markdown("---")
        
        # 1.        # AI 요약
        summary = result.get("ai_summary", "")
        if summary:
            st.markdown("#### 📝 공고문 요약")
            with st.container(border=True):
                st.markdown(summary)
            
            # 구글 챗용 텍스트 변환
            google_chat_text = _convert_to_google_chat_format(summary)
            
            col1, col2 = st.columns(2)
            with col1:
                with st.expander("📋 마크다운 원문 (티스토리/Github용)"):
                    st.code(summary, language="markdown")
            with col2:
                with st.expander("💬 구글 챗 포맷 (복사 후 붙여넣기)"):
                    st.code(google_chat_text, language="text")

        st.markdown("### 📊 분석 상세")
        
        score = result.get("suitability_score", -1)
        kill_switch = result.get("kill_switch", {})
        entity = result.get("target_entity", "미분류")
        breakdown = result.get("score_breakdown", {})

        # Kill Switch 경고
        if kill_switch.get("triggered"):
            st.error(f"🚫 **Kill Switch 발동**: {kill_switch.get('reason', '')}")

        # 점수 표시
        col1, col2, col3 = st.columns(3)
        with col1:
            if score >= 0:
                st.metric("적합도 점수", f"{score}/100")
                st.progress(min(score / 100, 1.0))
            else:
                st.metric("적합도 점수", "미분석")
        with col2:
            entity_icon = "💻" if entity == "STLABS" else "🔬" if entity == "Stratio" else "🤝" if entity == "both" else "❓"
            st.metric("추천 법인", f"{entity_icon} {entity}")
        with col3:
            labor = result.get("labor_cost_available", False)
            labor_text = "✅ 가능" if labor else "❌ 불가/미확인"
            st.metric("인건비 현금 계상", labor_text)

        # 세부 점수
        if breakdown:
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                d = breakdown.get("domain_fit", 0)
                st.metric("Domain Fit", f"{d}/50")
            with col_b2:
                r = breakdown.get("role_fit", 0)
                st.metric("Role Fit", f"{r}/30")
            with col_b3:
                t = breakdown.get("tech_fit", 0)
                st.metric("Tech Fit", f"{t}/20")

        # 컨소시엄 전략
        strategy = result.get("consortium_strategy", {})
        if strategy and strategy.get("type", "none") != "none":
            st.markdown("#### 🤝 컨소시엄 전략")
            render_strategy_box(strategy)

        # 주요 요구사항
        reqs = result.get("key_requirements", [])
        if reqs:
            st.markdown("#### 📌 주요 요구사항")
            for req in reqs:
                st.markdown(f"- {req}")

        # DB 저장 옵션
        if score >= 0:
            if st.button("💾 DB에 저장", key="save_manual_v2"):
                dao = get_project_dao()
                # 제목이 없으면 자동 생성
                final_title = title_input or (f"수동 분석: {url_input}" if url_input else "파일 업로드 분석")
                
                pid = dao.insert_project({
                    "title": final_title,
                    "agency": agency_input or "",
                    "source": "Manual",
                    "suitability_score": score,
                    "target_entity": entity,
                    "consortium_strategy": strategy,
                    "ai_summary": summary,
                    "files_text": text_to_analyze[:5000],
                    "is_manual": True,
                })
                if pid:
                    st.success("✅ DB에 저장되었습니다!")
                else:
                    st.warning("⚠️ 이미 DB에 존재하는 공고이거나 저장에 실패했습니다.")

    # ── [NEW] 분석 알고리즘 안내 (하단 배치, 항상 표시) ──
    st.markdown("---")
    with st.expander("ℹ️ AI 분석 알고리즘 상세 보기 (필수 확인)", expanded=True):
        st.markdown("""
        ### ✅ 분석 프로세스 체크리스트
        STLABS & Stratio 맞춤형 AI 엔진은 다음 5단계로 공고를 정밀 분석합니다.

        - [ ] **1. 자격 검증 (Kill Switch)**
            - 신청 자격, 필수 요건을 1차로 스크리닝하여 지원 불가능한 공고인지 확인합니다.
        - [ ] **2. 적합성 평가 (Scoring)**
            - **Domain Fit (50점)**: AI/SW(STLABS) 또는 센서/HW(Stratio) 사업 영역과의 연관성
            - **Role Fit (30점)**: 수익성, 주관기관 가능 여부, 인건비 지원 등 사업 매력도
            - **Tech Fit (20점)**: 보유 기술 스택(Python, Embedded, Image Processing 등) 일치도
        - [ ] **3. 전략 수립 (Strategy)**
            - 단독 수행 가능 여부 및 컨소시엄(대학/연구소/수요처) 필요성 판단
        - [ ] **4. 큐레이션 요약 (Summary)**
            - 수많은 과제 중 **우리 회사와 연관된 과제**만 선별하여 `★` 표시 및 상세 요약
        - [ ] **5. 최종 리포트 생성**
            - 임원 보고용 마크다운 리포트 및 구글 챗 요약본 자동 생성
        """)


# ═══════════════════════════════════════════════════════════
# Tab 2: STLABS (SW/Platform Focus)
# ═══════════════════════════════════════════════════════════

def render_tab_stlabs():
    """PRD 5.3: Tab 2 - STLABS (SW/Platform 과제 목록)"""
    st.markdown("## 💻 STLABS (SW / Platform)")
    st.caption("AI가 분류한 소프트웨어·플랫폼 관련 과제 목록")

    dao = get_project_dao()
    projects = dao.get_all_projects(entity="STLABS")

    if not projects:
        st.info("📭 아직 STLABS 과제가 없습니다. '데이터 최신화' 또는 '실험실'에서 공고를 분석해보세요.")
        return

    # ── 필터/정렬 ──
    sort_col1, sort_col2 = st.columns([2, 1])
    with sort_col1:
        sort_option = st.selectbox(
            "정렬",
            ["점수순 (높은순)", "마감임박순", "최신등록순"],
            label_visibility="collapsed",
        )
    with sort_col2:
        min_score = st.number_input("최소 점수", 0, 100, 0, step=10)

    # 필터링
    filtered = [p for p in projects if (p.get("suitability_score") or 0) >= min_score]

    # 정렬
    if "점수순" in sort_option:
        filtered.sort(key=lambda x: x.get("suitability_score", 0) or 0, reverse=True)
    elif "마감임박" in sort_option:
        filtered.sort(key=lambda x: x.get("end_date", "9999-12-31") or "9999-12-31")
    else:
        filtered.sort(key=lambda x: x.get("created_at", "") or "", reverse=True)

    st.caption(f"총 {len(filtered)}건")

    # ── 공고 목록 ──
    for project in filtered:
        score = project.get("suitability_score", 0) or 0
        title = project.get("title", "제목 없음")
        agency = project.get("agency", "")
        budget = project.get("total_budget", "")
        dday = calc_dday(project.get("end_date", ""))
        url = project.get("url", "")

        # 메타 정보
        meta_parts = [f"**{agency}**" if agency else None]
        if dday:
            meta_parts.append(f"📅 {dday}")
        if budget:
            meta_parts.append(f"💰 {budget}")
        meta = " | ".join(filter(None, meta_parts))

        with st.expander(f"🔥 {score}점 — {title}", expanded=False):
            st.markdown(render_badges(project), unsafe_allow_html=True)
            st.markdown(meta)

            summary = project.get("ai_summary", "")
            if summary:
                st.markdown(f"**AI 요약:** {summary}")

            strategy = project.get("consortium_strategy")
            if isinstance(strategy, str):
                try:
                    strategy = json.loads(strategy)
                except (json.JSONDecodeError, TypeError):
                    strategy = None
            if strategy and isinstance(strategy, dict):
                render_strategy_box(strategy)

            if url:
                st.link_button("📄 공고문 원문 보기 🔗", url)


# ═══════════════════════════════════════════════════════════
# Tab 3: Stratio (DeepTech/Consortium Focus)
# ═══════════════════════════════════════════════════════════

def render_tab_stratio():
    """PRD 5.4: Tab 3 - Stratio (DeepTech/Consortium 과제 카드)"""
    st.markdown("## 🔬 Stratio (DeepTech / Consortium)")
    st.caption("AI가 분류한 하드웨어·딥테크 관련 과제 — 전략 정보 강조")

    dao = get_project_dao()
    projects = dao.get_all_projects(entity="Stratio")

    if not projects:
        st.info("📭 아직 Stratio 과제가 없습니다. '데이터 최신화' 또는 '실험실'에서 공고를 분석해보세요.")
        return

    # 점수순 정렬
    projects.sort(key=lambda x: x.get("suitability_score", 0) or 0, reverse=True)
    st.caption(f"총 {len(projects)}건")

    # ── 카드 형태 ──
    for i in range(0, len(projects), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(projects):
                break
            project = projects[idx]

            with col:
                score = project.get("suitability_score", 0) or 0
                title = project.get("title", "제목 없음")
                agency = project.get("agency", "")
                dday = calc_dday(project.get("end_date", ""))
                url = project.get("url", "")

                # 카드 헤더
                st.markdown(
                    f'<div class="project-card">'
                    f'<h4>{title}</h4>'
                    f'{render_badges(project)}'
                    f'<p style="color:#94a3b8; margin-top:8px;">{agency} {f"| 📅 {dday}" if dday else ""}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # 전략 박스
                strategy = project.get("consortium_strategy")
                if isinstance(strategy, str):
                    try:
                        strategy = json.loads(strategy)
                    except (json.JSONDecodeError, TypeError):
                        strategy = None
                if strategy and isinstance(strategy, dict):
                    render_strategy_box(strategy)

                # AI 요약
                summary = project.get("ai_summary", "")
                if summary:
                    st.caption(f"💡 {summary}")

                if url:
                    st.link_button("📄 RFP 상세 확인 🔗", url, key=f"stratio_link_{idx}")


# ═══════════════════════════════════════════════════════════
# Tab 4: Market Intel & Exhibition
# ═══════════════════════════════════════════════════════════

def render_tab_market():
    """PRD 5.5: Tab 4 - Market Intel & Exhibition"""
    st.markdown("## 🌐 Market Intel & Exhibition")
    st.caption("외부 파트너 필요 과제 + 관련 전시회 일정 매칭")

    col_left, col_right = st.columns([1, 1])

    # ── Left: 외부 파트너 필요 과제 ──
    with col_left:
        st.markdown("### 🤝 외부 파트너 필요 과제")

        dao = get_project_dao()
        all_stratio = dao.get_all_projects(entity="Stratio")

        # 외부 협력형 필터링 (Academic Partner 또는 External Demand)
        partner_needed = []
        for p in all_stratio:
            strategy = p.get("consortium_strategy")
            if isinstance(strategy, str):
                try:
                    strategy = json.loads(strategy)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(strategy, dict):
                stype = strategy.get("type", "").lower()
                if "academic" in stype or "external" in stype:
                    p["_strategy"] = strategy
                    partner_needed.append(p)

        if not partner_needed:
            st.info("외부 파트너가 필요한 과제가 아직 없습니다.")
        else:
            for p in partner_needed:
                with st.expander(f"📋 {p.get('title', '')}"):
                    st.markdown(render_badges(p), unsafe_allow_html=True)
                    render_strategy_box(p.get("_strategy", {}))
                    summary = p.get("ai_summary", "")
                    if summary:
                        st.caption(summary)

    # ── Right: 전시회 일정 ──
    with col_right:
        st.markdown("### 📅 관련 전시회 일정")

        exhibition_dao = get_exhibition_dao()
        exhibitions = exhibition_dao.get_all_exhibitions()

        if not exhibitions:
            st.info("등록된 전시회가 없습니다.")

            # 전시회 추가 폼
            with st.expander("➕ 전시회 수동 등록"):
                with st.form("add_exhibition"):
                    ex_name = st.text_input("전시회명")
                    ex_loc = st.text_input("장소", placeholder="EXCO, COEX, KINTEX 등")
                    ex_date = st.date_input("시작일")
                    ex_cat = st.text_input("관련 분야", placeholder="스마트팜, 보안, 기계 등")
                    ex_url = st.text_input("홈페이지 URL")

                    if st.form_submit_button("등록"):
                        eid = exhibition_dao.insert_exhibition({
                            "name": ex_name,
                            "location": ex_loc,
                            "start_date": ex_date.strftime("%Y-%m-%d"),
                            "category": ex_cat,
                            "url": ex_url,
                        })
                        if eid:
                            st.success(f"✅ '{ex_name}' 등록 완료!")
                            st.rerun()
        else:
            for ex in exhibitions:
                st.markdown(
                    f"**{ex.get('name', '')}**\n\n"
                    f"📍 {ex.get('location', '')} | "
                    f"📅 {ex.get('start_date', '')} | "
                    f"🏷️ {ex.get('category', '')}"
                )
                url = ex.get("url", "")
                if url:
                    st.link_button("🔗 홈페이지", url, key=f"ex_{ex.get('id', '')}")
                st.divider()


# ═══════════════════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════════════════

def main():
    """애플리케이션 메인 함수"""
    inject_custom_css()
    render_sidebar()

    # ── 4-Tab 레이아웃 ──
    tab1, tab2, tab3, tab4 = st.tabs([
        "🧪 실험실",
        "💻 STLABS",
        "🔬 Stratio",
        "🌐 Market Intel",
    ])

    with tab1:
        render_tab_lab()

    with tab2:
        render_tab_stlabs()

    with tab3:
        render_tab_stratio()

    with tab4:
        render_tab_market()


if __name__ == "__main__":
    main()
