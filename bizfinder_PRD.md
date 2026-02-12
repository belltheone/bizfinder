Project Name: bizfinder (Master PRD v4)

1. 프로젝트 개요 (Project Overview)

1.1. 기획 배경 및 목적

본 프로젝트는 STLABS(소프트웨어/AI)와 Stratio(하드웨어/딥테크) 두 법인의 정부 지원사업 수주 확률을 극대화하기 위한 '의사결정 지원 시스템'입니다. 기존의 단순한 공고 알림 서비스와 달리, 이 시스템은 기업의 재무적 이익(인건비 확보)과 사업 주도권(주관기관 자격)을 기준으로 공고를 정밀 타격합니다.

단순히 공고를 긁어오는 것을 넘어, 첨부파일(HWP, PDF) 내부에 숨겨진 독소 조항을 파싱하고, AI가 심사위원의 관점에서 합격 가능성을 채점합니다. 또한, 사용자가 외부에서 입수한 링크나 파일을 직접 업로드하여 즉시 분석할 수 있는 수동 검증 기능을 포함합니다.

1.2. 핵심 가치 (Core Values)

Profit-Driven Filtering: 총 사업비의 규모보다 중요한 것은 '현금 인건비'의 비중입니다. 회사의 현금 흐름(Cash Flow)에 기여하지 못하는(재료비 위주의) 과제는 과감히 배제합니다.

Dual Persona Routing: 하나의 공고를 STLABS의 관점(단독 수행, SW개발)과 Stratio의 관점(컨소시엄, HW개발)에서 각각 시뮬레이션하여 최적의 수행 주체를 배정합니다.

Deep File Intelligence: 웹 페이지의 요약본은 믿지 않습니다. 반드시 HWP/PDF 원문을 다운로드하고 파싱하여, 본문에 명시되지 않은 '제한 사항'을 찾아냅니다.

On-Demand Analysis: 자동 수집뿐만 아니라, 사용자가 카카오톡/이메일로 받은 공고 링크나 파일을 즉시 시스템에 넣어 적합도를 판단할 수 있는 수동 도구를 제공합니다.

1.3. 운영 환경 (Environment)

Target: Google Antigravity (Cloud IDE & Agent Environment)

Browser Automation: IDE Native Chrome Control (No Selenium/Playwright required)

Infrastructure: 별도의 클라우드 서버 없이 로컬 환경 리소스 활용

2. 시스템 아키텍처 및 기술 스택 (System Architecture)

2.1. 기술 스택 (Tech Stack)

Language: Python 3.10 이상

Backend & Crawler:

requests, urllib: 정적 페이지 및 REST API 데이터 수집 (속도 최적화)

Native Browser Control: Google Antigravity IDE 내장 기능을 활용하여 동적 페이지(IRIS, NTIS) 직접 제어 및 파싱 (Selenium 대체)

schedule: 크롤링 작업 스케줄링 및 자동화 관리

File Parser (Core Engine):

olefile: Legacy HWP(OLE 컨테이너) 구조 분석 및 텍스트 추출

zipfile + xml.etree.ElementTree: HWPX(OOXML 기반) 압축 해제 및 본문 XML 파싱

pdfplumber: PDF 문서의 레이아웃을 보존하며 텍스트 추출

AI Engine:

Model: OpenAI GPT-4o mini (대량의 텍스트 처리에 최적화된 속도와 비용 효율성 보유)

SDK: openai Python Library

Database:

sqlite3: 별도 설치가 필요 없는 파일 기반 RDBMS (백업 및 이동 용이)

Frontend:

streamlit: 데이터 시각화 및 인터랙티브 대시보드 구현

2.2. 데이터 처리 파이프라인 (Data Pipeline)

Input Source:

Auto: 스케줄러에 의한 정기 크롤링 (API, 게시판, 검색)

Manual: 사용자가 UI를 통해 입력한 URL 또는 업로드한 파일

Asset Downloader: 공고 내 첨부파일 링크를 식별하고, temp/ 디렉토리에 고유 해시값으로 파일 저장

Deep Parser: 파일 확장자(.hwp, .hwpx, .pdf)를 판별하여 전용 파서를 통해 순수 텍스트(Plain Text) 추출

AI Analyzer: 추출된 텍스트와 메타데이터를 프롬프트 템플릿에 주입하여 GPT-4o mini에 전송 -> JSON 응답 수신

Data Persistence: 분석 결과(적합도 점수, 전략, 요약)를 SQLite DB에 저장 (URL 기준 중복 방지)

Visual Presenter: Streamlit UI를 통해 사용자에게 카드/리스트 형태로 정보 제공

3. 상세 기능 명세 (Functional Specifications)

3.1. [Module] 데이터 수집기 (The Collector)

수집 대상 사이트의 특성에 따라 3가지 수집 전략을 병행합니다.

Group A: 통합 포털 (API & Native Browser)

기업마당 (Bizinfo): Open API를 활용하여 일일 단위 신규 공고 리스트(XML) 수취. 가장 기본이 되는 데이터 소스.

K-Startup (창업넷): 창업 7년 미만 대상 공고 수집.

IRIS / NTIS: Google Antigravity IDE의 내장 브라우저 제어 기능을 활용. 검색창에 키워드(AI, 데이터, 센서, 탄소, 기후, 탐지)를 입력하고 결과 페이지를 렌더링 후 파싱.

Group B: 전문 기관 게시판 (List Parsing)

정보통신산업진흥원 (NIPA) / 한국지능정보사회진흥원 (NIA): SW 및 데이터 관련 고단가 과제 집중 수집.

정보통신기획평가원 (IITP) / 한국탄소산업진흥원: R&D 및 소재/부품 과제 수집.

Method: requests로 HTML을 받아오고 BeautifulSoup으로 <table> 태그 내의 공고 목록을 순회하며 파싱.

Group C: 지역 거점 (Local Board)

대구디지털혁신진흥원 (DIP): 대구 지역 SW 과제의 90%가 발생하는 핵심 채널. 필수 수집.

대구TP / 경북TP / 성남산업진흥원: 지역 한정 특화 공고 수집.

노이즈 필터링 (Pre-processing)

수집 단계에서 제목에 다음 키워드가 포함되면 DB 저장 없이 즉시 폐기(Drop)합니다.

행사, 교육, 세미나, 설명회, 멘토링, 입주기업, 전시회 참가, 렌탈, 구매, 공사, 시공, 인테리어, 청소, 경비

3.2. [Module] 첨부파일 심층 파석 (Deep File Parser)

본 시스템의 기술적 차별점입니다. 웹상의 텍스트는 요약본일 뿐이므로, 반드시 원본 파일을 분석합니다.

HWP (Legacy) 처리: olefile 라이브러리를 사용하여 HWP 파일 내부의 BodyText 섹션 스트림을 찾고, 압축된 바이너리를 해제(Decompress)하여 유니코드 텍스트로 변환합니다. 표(Table) 내부의 텍스트가 누락되지 않도록 순차적으로 추출합니다.

HWPX (XML) 처리: 파일 확장자를 .zip으로 변경하여 압축을 해제합니다. Contents/section0.xml 파일을 찾아 XML 파서로 텍스트 태그(<hp:t>) 안의 내용을 모두 추출합니다.

PDF 처리: pdfplumber를 사용하여 페이지 단위로 텍스트를 추출합니다. 만약 텍스트 추출 결과가 비어있다면(이미지 스캔본), 이는 기술적 한계로 간주하고 "수동 확인 필요" 태그를 부착합니다.

3.3. [Feature] 수동 검증기 (Manual Validator) - NEW

사용자가 외부에서 입수한 정보를 즉석에서 검증하는 기능입니다. 크롤러 로직과 독립적으로 작동합니다.

Input Method 1 (URL 검증):

사용자가 공고 상세 페이지 URL을 입력창에 붙여넣습니다.

시스템은 해당 URL의 HTML을 긁어오고 (필요시 내장 브라우저 활용), 첨부파일이 있다면 다운로드하여 파싱 프로세스를 가동합니다.

Input Method 2 (파일 업로드):

사용자가 카카오톡/메일로 받은 HWP/PDF 파일을 직접 업로드합니다.

시스템은 즉시 해당 파일의 내용을 파싱하여 AI 분석 엔진으로 보냅니다.

Output:

전체 공고 리스트에 저장하지 않고, 화면에 일회성 리포트(Report Card)를 출력합니다.

리포트 내용: 적합도 점수, 추천 수행 주체(STLABS/Stratio), 인건비 지원 여부, 3줄 요약.

3.4. [Module] AI 인텔리전스 엔진 (The Brain)

수집된 텍스트 데이터를 GPT-4o mini에 전송하여 JSON 형식의 분석 결과를 받습니다.

Logic 1: Kill Switch (필수 조건 검증)

분석 결과 다음 조건 중 하나라도 해당하면 Score = 0 처리하고 "부적합" 판정을 내립니다.

인건비 불가: 예산 비목에 '인건비'가 없거나 '현물만 가능'한 경우.

자격 미달: 주관기관 자격이 '대학', '병원', '농업인' 등으로 한정되어 기업이 주관할 수 없는 경우.

Logic 2: Relevance Scoring (적합도 채점 알고리즘)

100점 만점 기준으로 다음 항목을 평가합니다.

Domain Fit (50점): 회사의 특화 레퍼런스 키워드와 일치하는가?

Keywords: 기후테크, 폐플라스틱, 폐의류, 탄소중립, 리사이클링, 마약 탐지, 드론 탐지, 적외선 센서, SoC, 스마트 가전, 섬유 구분, 스마트팜

Role Fit (30점): 수익성 및 역할 적합성

순수 용역(현금 100%)이거나 바우처 사업인가?

민간부담금 비율이 낮은가?

Tech Fit (20점): 기술 스택 일치도

Web Platform, Dashboard, AI Model, Image Processing, IoT Sensor Data.

Logic 3: Persona Routing (법인 분류)

STLABS (Blue Team): 과업의 결과물이 S/W, Platform, Data, Service인 경우.

Stratio (Red Team): 과업의 결과물이 H/W, Device, Sensor, Material, Prototype인 경우.

Logic 4: Strategy Generator (컨소시엄 전략)

Stratio 과제로 분류된 경우, AI는 다음 시나리오 중 하나를 제안합니다.

Internal Synergy: "센서 하드웨어(Stratio)와 이를 모니터링할 관제 웹(STLABS)이 모두 필요한 과제임."

Academic Partner: "성능시험성적서 또는 임상실험 결과가 필수 산출물임 -> 대학/연구소 컨소시엄 필요."

External Demand: "실증(Testbed) 대상지가 필수임 -> 농장/공장/병원 파트너 필요."

4. 데이터베이스 설계 (Database Schema)

sqlite3를 사용하여 단일 파일(biz_intelligence.db)로 관리합니다.

Table: projects

Column Name

Type

Description

id

TEXT (PK)

공고 고유 ID (Hash: Title + Agency + Date)

title

TEXT

공고명

agency

TEXT

발주 기관명

source

TEXT

수집 출처 (Group A/B/C)

url

TEXT

공고 상세 페이지 URL

files_text

TEXT

첨부파일에서 추출한 요약 텍스트 (검색용)

total_budget

TEXT

총 사업비 (문자열)

end_date

DATE

마감일 (YYYY-MM-DD)

suitability_score

INTEGER

AI 적합도 점수 (0~100)

target_entity

TEXT

'STLABS' 또는 'Stratio'

consortium_strategy

JSON

전략 내용 (유형, 파트너 추천 등)

ai_summary

TEXT

AI가 요약한 3줄 핵심 내용

is_manual

BOOLEAN

수동 검증으로 등록된 데이터 여부

status

TEXT

'NEW', 'READ', 'HIDDEN', 'TRASH'

created_at

DATETIME

수집 일시

Table: exhibitions (전시회)

Column Name

Type

Description

id

TEXT (PK)

전시회 고유 ID

name

TEXT

전시회명

location

TEXT

EXCO, COEX, KINTEX 등

start_date

DATE

시작일

category

TEXT

관련 분야 (스마트팜, 보안, 기계 등)

url

TEXT

홈페이지 URL

5. UI/UX 상세 명세 (Frontend Specifications)

Streamlit을 활용하여 직관적인 4-Tab 레이아웃을 구성합니다.

5.1. Sidebar (Control Panel)

Status Dashboard: 마지막 크롤링 시간, 수집된 총 공고 수, 금일 신규 공고 수 표시.

Action Button: [🔄 데이터 최신화] 버튼 (크롤러 수동 트리거).

Keyword Manager: 사용자가 직접 제외 단어(행사, 교육 등)를 추가/삭제할 수 있는 태그 입력창.

5.2. Tab 1: 🧪 실험실 (Manual Validator) - NEW

Layout: 화면 상단에 2개의 입력 옵션 제공 (Tab 또는 Radio Button).

Option A: 🌐 URL 입력 (공고 링크 붙여넣기)

Option B: 📂 파일 업로드 (HWP/PDF 드래그 앤 드롭)

Process: [분석 시작] 버튼 클릭 시 로딩 스피너 표시 -> 파싱 및 AI 분석 수행.

Result View: 분석이 완료되면 하단에 '분석 결과 리포트' 카드 생성.

적합도 점수(0~100) 게이지 표시.

STLABS / Stratio 중 추천 수행 주체 표시.

"이 공고는 인건비 현금 계상이 가능합니다" 등의 핵심 코멘트 표시.

5.3. Tab 2: STLABS (SW/Platform Focus)

Filter: 점수순 / 마감임박순 / 예산순 정렬 드롭다운.

List Item:

Title: 클릭 시 아코디언 형태로 상세 내용(요약, 전략) 전개.

Meta: 기관명 | D-Day | 예산 (파란색 굵은 글씨)

Badge: 🔥 90점, 단독주관, SI, 바우처

External Link: 우측 끝 [공고문 원문 보기 🔗] 버튼.

5.4. Tab 3: Stratio (DeepTech/Consortium Focus)

Card Item: 전략 정보를 강조한 카드 형태 디자인.

Strategy Box:

내부 시너지형(Type A)일 경우: "Stratio + STLABS 내부 컨소시엄 추천" (초록색 배경)

외부 협력형(Type B/C)일 경우: "대학/병원 파트너 필요" (노란색 배경)

Action: [RFP 상세 확인 🔗] 버튼.

5.5. Tab 4: Market Intel & Exhibition

Split View:

Left: Tab 3에서 '외부 파트너 필요'로 분석된 공고 리스트.

Right: 해당 공고의 파트너(섬유, 의료, 기계 등)를 만날 수 있는 최신 전시회 일정 매칭.

6. 개발 로드맵 (Development Roadmap)

Phase 1: Core Parsing Engine (핵심 기술 확보)

Python 환경 설정 및 필수 라이브러리 설치.

FileParser 클래스 구현: olefile과 xml 파싱을 통해 HWP, HWPX 파일에서 텍스트가 깨지지 않고 추출되는지 단위 테스트(Unit Test) 완료. (가장 난이도가 높음)

Phase 2: Crawler & Collector (데이터 수집)

BizinfoCrawler, LocalBoardCrawler 구현.

Native Browser Control Implementation: IrisCrawler 구현 시 Selenium 대신 IDE 내장 브라우저 제어 기능 활용.

수집된 데이터를 sqlite에 저장하는 DAO(Data Access Object) 구현.

Phase 3: AI Integration (지능화)

OpenAI API 연동.

Prompt Engineering: 페르소나, 킬 스위치(인건비/자격), 채점 기준 등을 명시한 시스템 프롬프트 최적화.

JSON Output 파싱 및 에러 핸들링 로직 구현.

Phase 4: UI Implementation (시각화)

Streamlit을 활용한 레이아웃(Tab, Sidebar) 구성.

Manual Validator 기능 구현 (URL/File 처리 로직 연결).

데이터 바인딩 및 시각화 요소(Badge, Progress Bar) 적용.

Phase 5: Deployment & Automation (운영)

schedule 라이브러리로 백그라운드 자동 수집 스크립트 작성.

Windows 시작 프로그램 등록을 통한 자동 실행.

최종 사용자 테스트(UAT) 및 키워드 튜닝.