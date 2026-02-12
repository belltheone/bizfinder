# -*- coding: utf-8 -*-
"""
tests/test_ai_analyzer.py - AI 분석 엔진 단위 테스트
======================================================
OpenAI API를 모킹하여 AIAnalyzer의 로직을 검증합니다.

실행: python -m pytest tests/test_ai_analyzer.py -v
"""

import os
import sys
import json
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.ai_analyzer import AIAnalyzer, SYSTEM_PROMPT


# ═══════════════════════════════════════════
# JSON 파싱 로직 테스트
# ═══════════════════════════════════════════

class TestJSONParsing:
    """JSON 응답 파싱 로직 테스트 (API 호출 없이 순수 로직 검증)"""

    def setup_method(self):
        self.analyzer = AIAnalyzer(api_key="test_key")

    def test_parse_valid_json(self):
        """유효한 JSON 직접 파싱 확인"""
        raw = json.dumps({
            "kill_switch": {"triggered": False, "reason": "해당 없음"},
            "suitability_score": 85,
            "target_entity": "STLABS",
        })
        result = self.analyzer._parse_json_response(raw)
        assert result is not None
        assert result["suitability_score"] == 85

    def test_parse_json_in_code_block(self):
        """코드 블록 내부 JSON 추출 확인"""
        raw = '```json\n{"suitability_score": 90, "target_entity": "Stratio"}\n```'
        result = self.analyzer._parse_json_response(raw)
        assert result is not None
        assert result["suitability_score"] == 90

    def test_parse_json_with_surrounding_text(self):
        """주변 텍스트가 있는 JSON 추출 확인"""
        raw = '분석 결과입니다:\n{"suitability_score": 70}\n이상입니다.'
        result = self.analyzer._parse_json_response(raw)
        assert result is not None
        assert result["suitability_score"] == 70

    def test_parse_empty_content(self):
        """빈 내용 처리 확인"""
        assert self.analyzer._parse_json_response("") is None
        assert self.analyzer._parse_json_response(None) is None

    def test_parse_invalid_json(self):
        """유효하지 않은 JSON 처리 확인"""
        assert self.analyzer._parse_json_response("이것은 JSON이 아닙니다") is None

    def test_parse_complex_response(self):
        """전체 구조를 포함하는 복잡한 JSON 파싱 확인"""
        full_response = json.dumps({
            "kill_switch": {"triggered": False, "reason": "해당 없음"},
            "suitability_score": 78,
            "score_breakdown": {
                "domain_fit": 40,
                "role_fit": 22,
                "tech_fit": 16,
            },
            "target_entity": "STLABS",
            "consortium_strategy": {
                "type": "none",
                "description": "단독 수행 권장",
            },
            "ai_summary": "AI 데이터 플랫폼 개발 과제로 STLABS에 적합합니다.",
            "labor_cost_available": True,
            "key_requirements": ["AI 모델 개발", "대시보드 구현"],
        })

        result = self.analyzer._parse_json_response(full_response)
        assert result is not None
        assert result["suitability_score"] == 78
        assert result["target_entity"] == "STLABS"
        assert result["score_breakdown"]["domain_fit"] == 40
        assert result["labor_cost_available"] is True
        assert len(result["key_requirements"]) == 2


# ═══════════════════════════════════════════
# Kill Switch 로직 테스트
# ═══════════════════════════════════════════

class TestKillSwitch:
    """Kill Switch 로직 검증 - 가장 중요한 비즈니스 규칙"""

    def test_kill_switch_triggered_forces_zero_score(self):
        """Kill Switch 발동 시 Score=0 강제 확인 (PRD 절대 원칙)"""
        result = {
            "kill_switch": {
                "triggered": True,
                "reason": "인건비 현금 계상 불가 (현물만 가능)",
            },
            "suitability_score": 85,  # 원래 높은 점수
            "target_entity": "STLABS",
        }

        processed = AIAnalyzer._apply_kill_switch(result)
        assert processed["suitability_score"] == 0  # 강제로 0

    def test_kill_switch_not_triggered_preserves_score(self):
        """Kill Switch 미발동 시 원래 점수 유지 확인"""
        result = {
            "kill_switch": {
                "triggered": False,
                "reason": "해당 없음",
            },
            "suitability_score": 85,
        }

        processed = AIAnalyzer._apply_kill_switch(result)
        assert processed["suitability_score"] == 85

    def test_kill_switch_missing_key(self):
        """kill_switch 키가 없는 경우 정상 처리 확인"""
        result = {"suitability_score": 60}
        processed = AIAnalyzer._apply_kill_switch(result)
        assert processed["suitability_score"] == 60

    def test_kill_switch_university_only(self):
        """대학 한정 과제에 대한 Kill Switch 시뮬레이션"""
        result = {
            "kill_switch": {
                "triggered": True,
                "reason": "주관기관 자격이 '4년제 대학'으로 한정됨",
            },
            "suitability_score": 92,
        }

        processed = AIAnalyzer._apply_kill_switch(result)
        assert processed["suitability_score"] == 0


# ═══════════════════════════════════════════
# 기본 결과 생성 테스트
# ═══════════════════════════════════════════

class TestDefaultResult:
    """기본 결과 생성 검증"""

    def test_default_result_structure(self):
        """기본 결과에 필수 키가 모두 포함되어 있는지 확인"""
        result = AIAnalyzer._default_result("테스트 사유")

        assert "kill_switch" in result
        assert "suitability_score" in result
        assert "score_breakdown" in result
        assert "target_entity" in result
        assert "consortium_strategy" in result
        assert "ai_summary" in result
        assert "labor_cost_available" in result
        assert "key_requirements" in result

    def test_default_result_score_is_minus_one(self):
        """기본 결과의 점수가 -1 (미분석)인지 확인"""
        result = AIAnalyzer._default_result()
        assert result["suitability_score"] == -1

    def test_default_result_reason(self):
        """기본 결과에 사유가 포함되는지 확인"""
        result = AIAnalyzer._default_result("API 키 없음")
        assert "API 키 없음" in result["ai_summary"]


# ═══════════════════════════════════════════
# API 호출 통합 테스트 (모킹)
# ═══════════════════════════════════════════

class TestAPIIntegration:
    """API 호출 모킹 테스트"""

    def test_analyze_without_api_key(self):
        """API 키 없이 분석 시 기본 결과 반환 확인"""
        analyzer = AIAnalyzer(api_key="INVALID_KEY_FOR_TEST")
        # api_key가 빈 문자열이 아닌 유효하지 않은 키로 설정
        # 빈 문자열은 dotenv가 실제 키를 로드할 수 있으므로 명시적 무효 키 사용
        analyzer.api_key = ""  # 강제로 빈 키 설정
        result = analyzer.analyze("테스트 텍스트입니다. 충분히 긴 텍스트.")
        assert result["suitability_score"] <= 0

    def test_analyze_short_text(self):
        """텍스트가 너무 짧은 경우 기본 결과 반환 확인"""
        analyzer = AIAnalyzer(api_key="test_key")
        result = analyzer.analyze("짧은 텍스트")
        assert result["suitability_score"] == -1

    def test_analyze_with_mocked_api(self):
        """모킹된 API 응답으로 전체 분석 플로우 검증"""
        analyzer = AIAnalyzer(api_key="test_key")

        # 모킹할 API 응답 생성
        mock_api_response = json.dumps({
            "kill_switch": {"triggered": False, "reason": "해당 없음"},
            "suitability_score": 82,
            "score_breakdown": {
                "domain_fit": 45,
                "role_fit": 22,
                "tech_fit": 15,
            },
            "target_entity": "STLABS",
            "consortium_strategy": {
                "type": "none",
                "description": "SW 개발 단독 수행 권장",
            },
            "ai_summary": "기후테크 관련 AI 플랫폼 개발 과제로 STLABS에 적합합니다.",
            "labor_cost_available": True,
            "key_requirements": ["AI 모델 개발", "웹 대시보드 구현"],
        })

        # OpenAI 클라이언트 모킹
        mock_message = MagicMock()
        mock_message.content = mock_api_response

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        # _client를 직접 주입
        analyzer._client = mock_client

        result = analyzer.analyze(
            text="본 사업은 기후테크 분야의 AI 기반 데이터 플랫폼을 개발하는 프로젝트입니다. "
                 "인건비 현금 계상이 가능하며, 총 사업비 5억원 중 인건비 3억원을 지원합니다. "
                 "주관기관은 중소기업 또는 스타트업이어야 합니다.",
            title="2026년 기후테크 AI 플랫폼 개발 지원사업",
            agency="NIPA",
            budget="5억원",
            end_date="2026-03-31",
        )

        assert result["suitability_score"] == 82
        assert result["target_entity"] == "STLABS"
        assert result["labor_cost_available"] is True
        assert "기후테크" in result["ai_summary"]

    def test_analyze_kill_switch_flow(self):
        """Kill Switch 발동 시 전체 플로우 검증"""
        analyzer = AIAnalyzer(api_key="test_key")

        # Kill Switch가 발동된 응답
        mock_api_response = json.dumps({
            "kill_switch": {
                "triggered": True,
                "reason": "인건비 현금 계상 불가 - 재료비 위주 과제",
            },
            "suitability_score": 75,
            "score_breakdown": {"domain_fit": 40, "role_fit": 20, "tech_fit": 15},
            "target_entity": "Stratio",
            "consortium_strategy": {
                "type": "Academic Partner",
                "description": "대학 연구소 필요",
            },
            "ai_summary": "재료비 위주 과제로 인건비 확보 불가",
            "labor_cost_available": False,
            "key_requirements": ["센서 프로토타입 개발"],
        })

        mock_message = MagicMock()
        mock_message.content = mock_api_response
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        analyzer._client = mock_client

        result = analyzer.analyze(
            text="본 과제는 적외선 센서 모듈 시제품 제작을 목표로 합니다. "
                 "총 사업비 3억원 중 재료비 2.5억원, 인건비는 현물로만 인정됩니다.",
            title="적외선 센서 시제품 개발",
        )

        # Kill Switch로 인해 score=0
        assert result["suitability_score"] == 0
        assert result["labor_cost_available"] is False


# ═══════════════════════════════════════════
# 프롬프트 품질 테스트
# ═══════════════════════════════════════════

class TestPromptQuality:
    """시스템 프롬프트의 품질 및 완전성 검증"""

    def test_system_prompt_contains_kill_switch(self):
        """시스템 프롬프트에 Kill Switch 규칙이 포함되어 있는지 확인"""
        assert "Kill Switch" in SYSTEM_PROMPT
        assert "인건비" in SYSTEM_PROMPT
        assert "triggered" in SYSTEM_PROMPT

    def test_system_prompt_contains_scoring_criteria(self):
        """시스템 프롬프트에 채점 기준이 포함되어 있는지 확인"""
        assert "Domain Fit" in SYSTEM_PROMPT
        assert "Role Fit" in SYSTEM_PROMPT
        assert "Tech Fit" in SYSTEM_PROMPT
        assert "50점" in SYSTEM_PROMPT
        assert "30점" in SYSTEM_PROMPT
        assert "20점" in SYSTEM_PROMPT

    def test_system_prompt_contains_domain_keywords(self):
        """시스템 프롬프트에 도메인 키워드가 포함되어 있는지 확인"""
        for keyword in ["기후테크", "탄소중립", "스마트팜", "로봇", "반도체"]:
            assert keyword in SYSTEM_PROMPT

    def test_system_prompt_contains_routing_rules(self):
        """시스템 프롬프트에 Routing 규칙이 포함되어 있는지 확인"""
        assert "STLABS" in SYSTEM_PROMPT
        assert "Stratio" in SYSTEM_PROMPT
        assert "S/W" in SYSTEM_PROMPT
        assert "H/W" in SYSTEM_PROMPT

    def test_system_prompt_contains_strategy_types(self):
        """시스템 프롬프트에 전략 유형이 포함되어 있는지 확인"""
        assert "Internal Synergy" in SYSTEM_PROMPT
        assert "Academic Partner" in SYSTEM_PROMPT
        assert "External Demand" in SYSTEM_PROMPT

    def test_system_prompt_requires_json_output(self):
        """시스템 프롬프트에 JSON 출력 요구가 명시되어 있는지 확인"""
        assert "JSON" in SYSTEM_PROMPT
        assert "json" in SYSTEM_PROMPT.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
