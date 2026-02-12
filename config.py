# -*- coding: utf-8 -*-
"""
config.py - 전역 설정 파일
===========================
프로젝트 전체에서 사용되는 경로, 상수, 키워드 등을 관리합니다.
"""

import os
from dotenv import load_dotenv

# ── 프로젝트 루트 경로 ──
# 이 파일이 위치한 디렉토리를 기준으로 프로젝트 루트를 자동 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── .env 파일 로드 ──
# 프로젝트 루트의 .env 파일에서 API 키 등 환경 변수를 자동으로 로드
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ── 임시 파일 저장 경로 ──
# 다운로드된 HWP/PDF 등의 첨부파일이 저장되는 디렉토리
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# ── 데이터베이스 경로 ──
# SQLite 단일 파일 데이터베이스
DB_PATH = os.path.join(BASE_DIR, "biz_intelligence.db")

# ── 테스트 샘플 경로 ──
# 단위 테스트에 사용되는 샘플 파일 저장 디렉토리
TEST_SAMPLES_DIR = os.path.join(BASE_DIR, "tests", "samples")

# ── OpenAI API 설정 ──
# 환경 변수에서 API 키를 읽어옴 (보안을 위해 코드에 직접 작성하지 않음)
import streamlit as st

# ... (중략) ...

# ── OpenAI API 설정 ──
# 1. 환경 변수 확인 (우선순위 1)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# 2. Streamlit Secrets 확인 (Cloud 배포 환경 대비)
if not OPENAI_API_KEY:
    try:
        # st.secrets는 딕셔너리처럼 동작
        OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        pass  # secrets.toml 없음 등 예외 무시
OPENAI_MODEL = "gpt-4o-mini"  # 대량 텍스트 처리에 최적화된 모델

# ── 기업마당 (Bizinfo) API 설정 ──
# API 키는 환경 변수에서 읽어옴 (https://www.bizinfo.go.kr 에서 발급)
BIZINFO_API_KEY = os.environ.get("BIZINFO_API_KEY", "")
BIZINFO_API_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"

# ── 노이즈 필터링 키워드 ──
# 수집 단계에서 이 키워드가 제목에 포함되면 즉시 폐기(Drop)
NOISE_KEYWORDS = [
    "행사", "교육", "세미나", "설명회", "멘토링",
    "입주기업", "전시회 참가", "렌탈", "구매",
    "공사", "시공", "인테리어", "청소", "경비",
]

# ── 도메인 적합도 키워드 (AI Scoring용) ──
# STLABS/Stratio의 핵심 사업 영역과 관련된 키워드
DOMAIN_KEYWORDS = [
    "기후테크", "폐플라스틱", "폐의류", "탄소중립", "리사이클링",
    "마약 탐지", "드론 탐지", "적외선 센서", "SoC",
    "스마트 가전", "섬유 구분", "스마트팜",
]

# ── 기술 스택 키워드 (AI Scoring용) ──
TECH_KEYWORDS = [
    "Web Platform", "Dashboard", "AI Model",
    "Image Processing", "IoT Sensor Data",
]

# ── 지원 파일 확장자 ──
# FileParser가 처리할 수 있는 파일 형식
SUPPORTED_EXTENSIONS = [".hwp", ".hwpx", ".pdf"]

# ── 크롤링 대상 게시판 설정 ──
# Group B/C 게시판 사이트 정보 (BoardCrawler에서 사용)
CRAWL_TARGETS = {
    "DIP": {
        "name": "대구디지털혁신진흥원",
        "group": "C",
        "base_url": "https://www.dip.or.kr",
        "board_url": "https://www.dip.or.kr/bbs/board.php?bo_table=notice",
        "description": "대구 지역 SW 과제의 90% 발생 핵심 채널",
    },
    "NIPA": {
        "name": "정보통신산업진흥원",
        "group": "B",
        "base_url": "https://www.nipa.kr",
        "board_url": "https://www.nipa.kr/main/selectBbsNttList.do?bbsNo=113",
        "description": "SW 및 데이터 관련 고단가 과제",
    },
    "NIA": {
        "name": "한국지능정보사회진흥원",
        "group": "B",
        "base_url": "https://www.nia.or.kr",
        "board_url": "https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=82618",
        "description": "데이터 관련 고단가 과제",
    },
    "IITP": {
        "name": "정보통신기획평가원",
        "group": "B",
        "base_url": "https://www.iitp.kr",
        "board_url": "https://www.iitp.kr/kr/1/business/businessNotice/list.it",
        "description": "R&D 과제",
    },
    "DAEGU_TP": {
        "name": "대구테크노파크",
        "group": "C",
        "base_url": "https://www.ttp.org",
        "board_url": "https://www.ttp.org/cms/board/notice/list.do",
        "description": "대구 지역 특화 공고",
    },
    "GBTP": {
        "name": "경북테크노파크",
        "group": "C",
        "base_url": "https://www.gbtp.or.kr",
        "board_url": "https://www.gbtp.or.kr/board/notice",
        "description": "경북 지역 특화 공고",
    },
}

# ── IRIS/NTIS 검색 키워드 ──
# Group A 동적 페이지 검색 시 사용하는 키워드
SEARCH_KEYWORDS = ["AI", "데이터", "센서", "탄소", "기후", "탐지"]

# ── HTTP 요청 기본 설정 ──
REQUEST_TIMEOUT = 30  # 초
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}

# ── 디렉토리 자동 생성 ──
# 필요한 디렉토리가 없으면 자동으로 생성
for _dir in [TEMP_DIR, TEST_SAMPLES_DIR]:
    os.makedirs(_dir, exist_ok=True)
