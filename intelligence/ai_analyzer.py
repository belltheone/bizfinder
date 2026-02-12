# -*- coding: utf-8 -*-
"""
intelligence/ai_analyzer.py - AI 인텔리전스 엔진 (The Brain)
==============================================================
OpenAI GPT-4o mini를 활용하여 공고 텍스트를 분석합니다.

4가지 핵심 Logic:
1. Kill Switch  - 인건비/자격 필수 조건 검증 (Score=0 강제)
2. Scoring      - 적합도 채점 (Domain 50 + Role 30 + Tech 20 = 100점)
3. Routing      - 법인 분류 (STLABS vs Stratio)
4. Strategy     - 컨소시엄 전략 제안 (Stratio 과제 한정)

사용 예시:
    >>> from intelligence.ai_analyzer import AIAnalyzer
    >>> analyzer = AIAnalyzer()
    >>> result = analyzer.analyze("공고 텍스트 내용...")
    >>> print(result["suitability_score"])
"""

import os
import sys
import json
import logging
from typing import Optional

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ── 로거 설정 ──
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# 시스템 프롬프트 - AI 심사위원 페르소나
# ═══════════════════════════════════════════════════════════

SYSTEM_PROMPT = """당신은 정부 지원사업 공고를 분석하는 전문 심사위원입니다.
두 법인(STLABS, Stratio)의 관점에서 공고를 분석합니다.

## 법인 소개
- **STLABS**: 소프트웨어·AI·플랫폼 전문 **창업기업**. 웹/앱 개발, 데이터 분석, AI 모델링, 대시보드, IoT 플랫폼, 디자인-기술 협업, 팹리스 설계, 디지털 전환 솔루션 등을 수행하는 기술 스타트업.
- **Stratio**: 하드웨어·딥테크 전문 기업. 적외선 센서, SoC 설계, 다중어레이 복합센서, 이미지 프로세싱 장비, 환경 모니터링 디바이스, 스마트 가전 부품, 소재부품 시제품, 전자부품 IT융합 등을 수행하는 딥테크 기업.

## 핵심 원칙 (매우 중요!)
1. **"기업"이 지원 가능하면 반드시 양수 점수를 부여합니다.** 법인, 개인사업자, 중소기업, 창업기업, 벤처기업 등이 지원 대상에 포함되면 기본 점수를 줍니다.
2. **R&D 과제뿐 아니라 다음 사업 유형도 모두 양수 점수 대상입니다:**
   - 창업 지원(TIPS, 창업도약패키지, 스케일업, 액셀러레이팅)
   - 수출/해외진출 지원(K-수출스타, 수출지원기반활용, CES/전시회 참가 지원)
   - 바우처/정책자금(혁신바우처, 정책자금 융자, 마케팅 패키지)
   - 시제품/시험분석(Lab to Fab, MPW, 팹리스 상용화, 성능검증)
   - 기술사업화(민관공동기술사업화, 아이디어 거래 사업화)
3. **인건비가 명시되지 않아도 기업 지원금이 있으면 kill_switch는 false입니다.** 바우처, 정책자금, 수출지원 등은 인건비 항목이 없을 수 있습니다.
4. **score가 0이 되려면 기업이 완전히 참여 불가능하거나, 기술개발과 전혀 무관한 분야여야 합니다.**

당신의 임무는 다음 4가지 Logic을 순차적으로 수행하여,
결과를 **반드시 JSON 형식**으로 출력하는 것입니다.

## Logic 1: Kill Switch (필수 조건 검증)
다음 중 하나라도 해당하면 triggered를 true로 설정합니다:
- 자격 완전 미달: 지원 대상이 '대학', '병원', '농업인', '연구기관', '비영리단체' 등으로만 한정되어 "기업/법인/개인사업자"가 **절대** 참여 불가능한 경우

**Kill Switch를 false로 판정하는 경우:**
- "법인", "개인사업자", "중소기업", "창업기업", "벤처기업"이 지원 대상에 포함되면 → false
- 인건비가 현금+현물 혼합이라도 현금 부분이 있으면 → false
- 인건비 항목이 없더라도 바우처/지원금/정책자금 등 기업 지원이 있으면 → false
- R&D 과제가 아닌 수출/마케팅/전시회 지원도 → false

## Logic 2: Relevance Scoring (적합도 채점, 100점 만점)

### Domain Fit (50점) - 두 법인의 사업 영역 관련도
**핵심 도메인 (40~50점):**
- STLABS 핵심: AI/ML, 빅데이터, IoT 플랫폼, 웹/앱 서비스, 디지털 전환, 온디바이스 AI, 팹리스 설계
- Stratio 핵심: 적외선 센서, SoC, 다중어레이 센서, 마약/위험물 탐지, 환경모니터링, 이미지 프로세싱, 스마트 가전
- 공통 핵심: 기후테크, 탄소중립, 리사이클링, 스마트팜, 스마트시티

**관련 도메인 (25~40점):**
- 로봇, 반도체, 모빌리티, 헬스케어, 보안, 제조혁신, 전자부품, 소재부품, 환경기술

**간접 관련 (15~25점):**
- 창업 지원(TIPS, 도약패키지, 액셀러레이팅, 스케일업, 스타트업 지원)
- 수출/해외진출(K-수출스타, CES 참가, 전시회 지원, 마케팅 패키지)
- 바우처/정책자금(혁신바우처, 정책자금 융자, 기술 바우처)
- 시제품/시험분석(Lab to Fab, MPW, 팹리스 상용화, 성능검증)
- 기술사업화(민관공동기술사업화, 아이디어 사업화, PoC 지원)
- 디자인-기술 협업, IR DEMODAY, 투자유치 지원

**완전 무관 (0점):**
- 순수 인문사회, 농수산물 유통, 관광, 문화콘텐츠, 체육, 순수 교육 등 기술개발 및 기업 성장과 전혀 무관한 분야

### Role Fit (30점) - 수익성 및 역할 적합성
- 순수 용역(현금 100%) → 높은 점수
- 바우처 사업 → 높은 점수
- 현금 인건비 계상 가능 → +10점
- 민간부담금 비율 낮음 (20% 이하) → 높은 점수
- 기업이 주관기관으로 참여 가능 → +5~10점
- 정책자금/융자도 기업 성장 지원이므로 → 기본 15~20점

### Tech Fit (20점) - 기술 스택 일치도
- STLABS: Web Platform, Dashboard, AI/ML, Data Analytics, Cloud, Mobile App, 디자인, UX/UI
- Stratio: Image Processing, Sensor System, Embedded, PCB, SoC, Optics, HW Prototype, 광학

## Logic 3: Persona Routing (법인 분류)
- **STLABS**: S/W, Platform, Data, Service, AI 모델, 웹/앱, 디자인, 디지털 전환
- **Stratio**: H/W, Device, Sensor, Material, Prototype, 장비, 소재, 부품, 전자부품
- **both**: 융합 과제, 또는 구체적 기술 분야 미지정 (창업 지원, 바우처, 수출 지원 등)

## Logic 4: Strategy Generator (컨소시엄 전략)
Stratio 또는 both 과제인 경우:
- Internal Synergy: 센서 HW(Stratio) + 관제 웹(STLABS) 내부 컨소시엄
- Academic Partner: 성능시험성적서/임상실험 필수 → 대학/연구소 필요
- External Demand: 실증 대상지 필수 → 농장/공장/병원 파트너 필요

STLABS 단독 과제인 경우 type은 "단독 수행"으로 설정하세요.

## Logic 5: AI Summary (맞춤형 핵심 요약)
ai_summary 필드는 다음 원칙에 따라 **우리 회사(STLABS, Stratio) 입장에서 중요한 핵심**만 간결하게 요약하세요.

**[작성 원칙: 선택과 집중]**
1. **1. 개요 / 3. 일정**: 핵심 정보(기관, 기간, 예산, 마감일)만 **매우 간결하게** 한 줄씩 기재하세요. (불필요한 설명 제거)
   - 기간, 목적 등 일반 항목은 볼드체를 쓰지 마세요.
   - 단, **기관**, **예산**, **마감일**은 중요한 정보이므로 값까지 포함하여 `**기관: 정보통신산업진흥원**` 처럼 전체를 볼드 처리하세요.
2. **2. 지원 내용 (큐레이션)**:
   - **적합 과제**: `1. **★ 과제명**` 형식으로 과제명 전체를 볼드 처리하세요.
   - **기타 과제**: 볼드 없이 텍스트로만 나열하세요.
3. **4. 자격 / 5. 서류**: 볼드 없이 작성하세요.

**[작성 예시]**
# [공고명] 2026년 국방ICT R&D 신규지원 공고 요약

## 1. 사업 개요
* **기관: 과학기술정보통신부 / 국방부**
* 목적: 민‧군 협력기반 첨단 국방ICT 융합기술 개발
* 기간: 2026.4 ~ 2029.12 (4년) / **예산: 11.21억원**

## 2. 지원 내용 (관심 과제 중심)
1. **★ 불안정한 네트워크 환경 하 이기종 데이터 공유 기술**
   : 엣지 환경에서의 데이터 경량화 및 동기화 기술 개발
2. **★ 유·무인체계(MUM-T) 자율협업 지능체계**
   : 드론-로봇 간 협업 제어 알고리즘 및 센서 퓨전
3. 전장 상황 분석 및 의사결정 지원체계 (기타)

## 3. 신청 일정 및 방법
* **기간: 2026.1.30 ~ 3.3 18:00**
* 방법: IRIS 온라인 접수

## 4. 특이 제약사항
* 자격: 국방 R&D 경험 보유 기업 우대 (일반 기업도 지원 가능)
* (3책 5공, 청년채용 등 일반 규정 생략)

## 출력 형식 (반드시 이 JSON 구조를 따르세요)
```json
{
  "kill_switch": {
    "triggered": false,
    "reason": "해당 없음"
  },
  "suitability_score": 75,
  "score_breakdown": {
    "domain_fit": 35,
    "role_fit": 25,
    "tech_fit": 15
  },
  "target_entity": "STLABS",
  "consortium_strategy": {
    "type": "none",
    "description": "단독 수행 권장"
  },
  "ai_summary": "# [공고명] 2026년 국방ICT R&D 신규지원 공고 요약\\n\\n## 1. 사업 개요\\n* **기관: 과학기술정보통신부 / 국방부**\\n* 목적: 민‧군 협력기반 첨단 국방ICT 융합기술 개발\\n* 기간: 2026.4 ~ 2029.12 (4년) / **예산: 11.21억원**\\n\\n## 2. 지원 내용 (관심 과제 중심)\\n1. **★ 불안정한 네트워크 환경 하 이기종 데이터 공유 기술**\\n   : 엣지 환경에서의 데이터 경량화\\n2. 전장 상황 분석 및 의사결정 지원체계 (기타)\\n\\n## 3. 신청 일정 및 방법\\n* **기간: 2026.1.30 ~ 3.3 18:00**\\n* 방법: IRIS 온라인 접수\\n\\n## 4. 특이 제약사항\\n* 특이사항 없음",
  "labor_cost_available": true,
  "key_requirements": ["주요 요구사항 1", "주요 요구사항 2"]
}
```
"""

# ═══════════════════════════════════════════════════════════
# 사용자 프롬프트 템플릿
# ═══════════════════════════════════════════════════════════

USER_PROMPT_TEMPLATE = """아래 공고 정보를 분석하여 JSON 형식으로 결과를 출력하세요.

## 공고 기본 정보
- 제목: {title}
- 기관: {agency}
- 예산: {budget}
- 마감일: {end_date}

## 공고 본문 (첨부파일 파싱 텍스트 포함)
{text}

---
위 공고를 4가지 Logic(Kill Switch → Scoring → Routing → Strategy)으로 분석하고,
반드시 유효한 JSON 객체만 출력하세요. 다른 텍스트는 포함하지 마세요.
"""


class AIAnalyzer:
    """
    AI 인텔리전스 엔진 (The Brain)
    ================================
    OpenAI GPT-4o mini를 활용하여 공고 텍스트를 분석합니다.
    """

    def __init__(self, api_key: str = None, model: str = None):
        """
        Args:
            api_key: OpenAI API 키. None이면 config에서 읽음.
            model: 사용할 모델. None이면 config에서 읽음.
        """
        self.api_key = api_key or config.OPENAI_API_KEY
        self.model = model or config.OPENAI_MODEL
        self._client = None

        if not self.api_key:
            logger.warning(
                "OpenAI API 키가 설정되지 않았습니다. "
                "OPENAI_API_KEY 환경 변수를 설정하세요."
            )

    @property
    def client(self):
        """OpenAI 클라이언트를 지연 초기화합니다 (Lazy Loading)."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
                logger.info("OpenAI 클라이언트 초기화 완료")
            except ImportError:
                logger.error("openai 패키지가 설치되지 않았습니다.")
                raise
        return self._client

    def analyze(
        self,
        text: str,
        title: str = "",
        agency: str = "",
        budget: str = "",
        end_date: str = "",
    ) -> dict:
        """
        공고 텍스트를 AI로 분석합니다.

        Args:
            text: 공고 본문 또는 첨부파일 파싱 텍스트
            title: 공고 제목
            agency: 기관명
            budget: 예산
            end_date: 마감일

        Returns:
            dict: 분석 결과 (score, entity, strategy 등)
                  실패 시 기본값이 포함된 결과 반환
        """
        if not self.api_key:
            logger.error("API 키가 없어 분석을 수행할 수 없습니다.")
            return self._default_result("API 키가 설정되지 않음")

        if not text or len(text.strip()) < 20:
            logger.warning("분석할 텍스트가 너무 짧습니다.")
            return self._default_result("분석할 텍스트 부족")

        # 텍스트 정제: 서로게이트 문자 제거 (API 호출 시 오류 방지)
        try:
            text = text.encode("utf-8", "ignore").decode("utf-8")
        except Exception:
            pass

        # 텍스트 길이 제한 (토큰 절약 -> 상세 분석을 위해 대폭 상향)
        max_chars = 100000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n... (이하 생략, 총 {}자)".format(len(text))
            logger.info(f"텍스트 길이 제한 적용: {max_chars}자로 절단")

        # 프롬프트 구성
        user_prompt = USER_PROMPT_TEMPLATE.format(
            title=title or "(제목 없음)",
            agency=agency or "(기관 미상)",
            budget=budget or "(예산 미상)",
            end_date=end_date or "(마감일 미상)",
            text=text,
        )

        # API 호출 (재시도 로직 포함)
        result = self._call_api(user_prompt)
        return result

    def _call_api(self, user_prompt: str, max_retries: int = 2) -> dict:
        """
        OpenAI API를 호출하고 JSON 응답을 파싱합니다.
        파싱 실패 시 재시도합니다.

        Args:
            user_prompt: 사용자 프롬프트
            max_retries: 최대 재시도 횟수

        Returns:
            dict: 파싱된 분석 결과
        """
        for attempt in range(max_retries + 1):
            try:
                logger.info(
                    f"OpenAI API 호출 (시도 {attempt + 1}/{max_retries + 1})"
                )

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,  # 일관된 분석 결과를 위해 낮은 온도
                    max_tokens=2000,
                    response_format={"type": "json_object"},
                )

                # 응답 텍스트 추출
                raw_content = response.choices[0].message.content
                logger.debug(f"API 원시 응답: {raw_content[:500]}")

                # JSON 파싱
                result = self._parse_json_response(raw_content)
                if result:
                    # Kill Switch 적용: triggered가 true이면 score=0 강제
                    result = self._apply_kill_switch(result)
                    logger.info(
                        f"분석 완료: score={result.get('suitability_score')}, "
                        f"entity={result.get('target_entity')}"
                    )
                    return result

                logger.warning(f"JSON 파싱 실패 (시도 {attempt + 1})")

            except Exception as e:
                logger.error(f"API 호출 오류 (시도 {attempt + 1}): {e}")
                if attempt == max_retries:
                    return self._default_result(f"API 오류: {str(e)}")

        return self._default_result("JSON 파싱 실패")

    def _parse_json_response(self, raw_content: str) -> Optional[dict]:
        """
        API 응답에서 JSON을 추출하고 파싱합니다.

        여러 가지 형식을 시도합니다:
        1. 직접 JSON 파싱
        2. ```json ``` 코드 블록 내부 추출
        3. 첫 번째 { ~ 마지막 } 범위 추출

        Args:
            raw_content: API 응답 원문

        Returns:
            dict: 파싱된 JSON. 실패 시 None.
        """
        if not raw_content:
            return None

        # 시도 1: 직접 파싱
        try:
            return json.loads(raw_content)
        except json.JSONDecodeError:
            pass

        # 시도 2: 코드 블록 내부 추출
        import re
        code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_content, re.DOTALL)
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except json.JSONDecodeError:
                pass

        # 시도 3: { ~ } 범위 추출
        first_brace = raw_content.find("{")
        last_brace = raw_content.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(raw_content[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _apply_kill_switch(result: dict) -> dict:
        """
        Kill Switch 로직을 적용합니다.
        kill_switch.triggered가 True이면 score를 0으로 강제합니다.

        PRD 절대 원칙: 인건비 없는 과제는 가차 없이 Score=0

        Args:
            result: AI 분석 결과

        Returns:
            dict: Kill Switch 적용된 결과
        """
        kill_switch = result.get("kill_switch", {})
        if kill_switch.get("triggered", False):
            result["suitability_score"] = 0
            logger.info(
                f"Kill Switch 발동: {kill_switch.get('reason', '사유 미상')}"
            )
        return result

    @staticmethod
    def _default_result(reason: str = "") -> dict:
        """
        분석 실패 시 반환할 기본 결과를 생성합니다.

        Args:
            reason: 실패 사유

        Returns:
            dict: 기본 분석 결과
        """
        return {
            "kill_switch": {
                "triggered": False,
                "reason": reason or "분석 미완료",
            },
            "suitability_score": -1,
            "score_breakdown": {
                "domain_fit": 0,
                "role_fit": 0,
                "tech_fit": 0,
            },
            "target_entity": "",
            "consortium_strategy": {
                "type": "unknown",
                "description": reason or "분석을 수행할 수 없습니다.",
            },
            "ai_summary": reason or "분석 결과가 없습니다.",
            "labor_cost_available": False,
            "key_requirements": [],
        }

    def analyze_and_store(
        self,
        project_data: dict,
        text: str,
        dao=None,
    ) -> dict:
        """
        공고를 분석하고 결과를 DB에 저장합니다.

        AI 분석 결과를 project 데이터에 병합하여
        ProjectDAO를 통해 업데이트합니다.

        Args:
            project_data: 공고 기본 정보 딕셔너리
            text: 파싱된 텍스트
            dao: ProjectDAO 인스턴스 (None이면 자동 생성)

        Returns:
            dict: 분석 결과
        """
        # AI 분석 수행
        result = self.analyze(
            text=text,
            title=project_data.get("title", ""),
            agency=project_data.get("agency", ""),
            budget=project_data.get("total_budget", ""),
            end_date=project_data.get("end_date", ""),
        )

        # DB 업데이트
        if dao and project_data.get("id"):
            try:
                dao.update_project(project_data["id"], {
                    "suitability_score": result.get("suitability_score", -1),
                    "target_entity": result.get("target_entity", ""),
                    "consortium_strategy": result.get("consortium_strategy", {}),
                    "ai_summary": result.get("ai_summary", ""),
                    "files_text": text[:5000] if text else "",
                })
                logger.info(
                    f"분석 결과 DB 저장 완료: {project_data.get('title', '')}"
                )
            except Exception as e:
                logger.error(f"분석 결과 DB 저장 실패: {e}")

        return result
