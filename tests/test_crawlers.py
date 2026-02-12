# -*- coding: utf-8 -*-
"""
tests/test_crawlers.py - 크롤러 단위 테스트
==============================================
unittest.mock으로 HTTP 응답을 모킹하여
BizinfoCrawler와 BoardCrawler의 파싱 로직을 검증합니다.

실행: python -m pytest tests/test_crawlers.py -v
"""

import os
import sys
import json
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.bizinfo_crawler import BizinfoCrawler
from collectors.board_crawler import BoardCrawler
from collectors.iris_crawler import IrisCrawler


# ═══════════════════════════════════════════
# BizinfoCrawler 테스트
# ═══════════════════════════════════════════

class TestBizinfoCrawler:
    """기업마당 API 크롤러 테스트"""

    def test_init_with_api_key(self):
        """API 키가 정상적으로 설정되는지 확인"""
        crawler = BizinfoCrawler(api_key="test_key_123")
        assert crawler.api_key == "test_key_123"

    def test_init_without_api_key(self):
        """API 키 없이 초기화 시 경고 로그만 표시되는지 확인"""
        crawler = BizinfoCrawler(api_key="")
        assert crawler.api_key == ""

    def test_crawl_without_api_key_returns_empty(self):
        """API 키 없이 크롤링 시 빈 리스트 반환 확인"""
        crawler = BizinfoCrawler(api_key="")
        result = crawler.crawl()
        assert result == []

    def test_parse_response_valid_json(self):
        """API JSON 응답 파싱 성공 확인"""
        crawler = BizinfoCrawler(api_key="test_key")

        mock_response = {
            "jsonArray": [
                {
                    "pblancNm": "2026년 AI 데이터 플랫폼 개발 지원사업",
                    "jrsdInsttNm": "정보통신산업진흥원",
                    "reqstBeginEndDe": "2026-01-15 ~ 2026-03-31",
                    "pblancUrl": "https://www.bizinfo.go.kr/detail/1234",
                    "totBudget": "10억원",
                },
                {
                    "pblancNm": "2026년 스마트팩토리 센서 개발 과제",
                    "jrsdInsttNm": "IITP",
                    "reqstBeginEndDe": "2026-02-01 ~ 2026-04-15",
                    "pblancUrl": "https://www.bizinfo.go.kr/detail/5678",
                    "totBudget": "3억원",
                },
            ]
        }

        result = crawler._parse_response(mock_response)

        assert len(result) == 2
        assert result[0]["title"] == "2026년 AI 데이터 플랫폼 개발 지원사업"
        assert result[0]["agency"] == "정보통신산업진흥원"
        assert result[0]["end_date"] == "2026-03-31"
        assert result[0]["source"] == "Group A - Bizinfo"
        assert result[1]["end_date"] == "2026-04-15"

    def test_parse_response_empty_array(self):
        """빈 JSON 배열에 대한 처리 확인"""
        crawler = BizinfoCrawler(api_key="test_key")
        result = crawler._parse_response({"jsonArray": []})
        assert result == []

    def test_parse_response_missing_key(self):
        """jsonArray 키가 없는 응답 처리 확인"""
        crawler = BizinfoCrawler(api_key="test_key")
        result = crawler._parse_response({"unexpected": "data"})
        assert result == []

    def test_noise_filtered_in_crawl(self):
        """크롤링 결과에서 노이즈가 필터링되는지 확인"""
        crawler = BizinfoCrawler(api_key="test_key")

        mock_response = {
            "jsonArray": [
                {
                    "pblancNm": "2026년 AI 교육 세미나 개최",  # 노이즈: 교육, 세미나
                    "jrsdInsttNm": "NIA",
                    "reqstBeginEndDe": "",
                    "pblancUrl": "",
                },
                {
                    "pblancNm": "2026년 기후테크 R&D 과제",  # 정상 공고
                    "jrsdInsttNm": "NIPA",
                    "reqstBeginEndDe": "2026-03-01 ~ 2026-05-31",
                    "pblancUrl": "https://example.com",
                },
            ]
        }

        with patch.object(crawler, '_fetch_page',
                          return_value=crawler._parse_response(mock_response)):
            result = crawler.crawl(page_count=1)

        # "교육 세미나"가 포함된 공고는 필터링됨
        assert len(result) == 1
        assert result[0]["title"] == "2026년 기후테크 R&D 과제"

    def test_extract_end_date_dash_format(self):
        """날짜 추출: YYYY-MM-DD 형식 확인"""
        assert BizinfoCrawler._extract_end_date("2026-01-15 ~ 2026-03-31") == "2026-03-31"

    def test_extract_end_date_dot_format(self):
        """날짜 추출: YYYY.MM.DD 형식 확인"""
        assert BizinfoCrawler._extract_end_date("2026.01.15 ~ 2026.03.31") == "2026-03-31"

    def test_extract_end_date_no_separator(self):
        """날짜 추출: 구분자 없는 형식 확인"""
        assert BizinfoCrawler._extract_end_date("20260115 ~ 20260331") == "2026-03-31"

    def test_extract_end_date_empty(self):
        """날짜 추출: 빈 문자열 처리 확인"""
        assert BizinfoCrawler._extract_end_date("") == ""
        assert BizinfoCrawler._extract_end_date("미정") == ""


# ═══════════════════════════════════════════
# BoardCrawler 테스트
# ═══════════════════════════════════════════

class TestBoardCrawler:
    """게시판 크롤러 테스트"""

    def test_init_with_valid_target(self):
        """유효한 target_key로 초기화 확인"""
        crawler = BoardCrawler(target_key="DIP")
        assert "대구디지털혁신진흥원" in crawler.target_name

    def test_init_with_custom_url(self):
        """custom_url로 초기화 확인"""
        crawler = BoardCrawler(
            custom_url="https://example.com/board",
            custom_name="테스트 보드"
        )
        assert crawler.target_name == "테스트 보드"
        assert crawler.board_url == "https://example.com/board"

    def test_init_invalid_target_raises_error(self):
        """유효하지 않은 target_key에 대해 ValueError 발생 확인"""
        with pytest.raises(ValueError, match="유효한 target_key"):
            BoardCrawler(target_key="INVALID_KEY")

    def test_parse_table_board(self):
        """<table> 기반 게시판 HTML 파싱 확인"""
        crawler = BoardCrawler(target_key="DIP")

        # 테스트용 HTML (일반적인 게시판 테이블 구조)
        test_html = """
        <html><body>
        <table class="board-list">
          <thead><tr><th>No</th><th>제목</th><th>등록일</th></tr></thead>
          <tbody>
            <tr>
              <td>1</td>
              <td><a href="/notice/view?id=100">2026년 AI 플랫폼 개발 지원사업 공고</a></td>
              <td>2026-02-10</td>
            </tr>
            <tr>
              <td>2</td>
              <td><a href="/notice/view?id=101">2026년 스마트팩토리 구축 사업 안내</a></td>
              <td>2026-02-08</td>
            </tr>
          </tbody>
        </table>
        </body></html>
        """

        result = crawler._parse_board_html(test_html)

        assert len(result) == 2
        assert result[0]["title"] == "2026년 AI 플랫폼 개발 지원사업 공고"
        assert "2026-02-10" in result[0]["end_date"]
        assert result[0]["agency"] == "대구디지털혁신진흥원"
        assert "https://www.dip.or.kr/notice/view?id=100" in result[0]["url"]

    def test_parse_div_board(self):
        """<div> 리스트 기반 게시판 파싱 확인"""
        crawler = BoardCrawler(target_key="NIPA")

        test_html = """
        <html><body>
        <div class="board-list">
          <div class="item">
            <a href="/bbs/detail/456">데이터 기반 서비스 개발 지원</a>
            <span class="date">2026.02.15</span>
          </div>
          <div class="item">
            <a href="/bbs/detail/457">클라우드 전환 사업 공고</a>
            <span class="date">2026.02.12</span>
          </div>
        </div>
        </body></html>
        """

        result = crawler._parse_board_html(test_html)

        assert len(result) == 2
        assert result[0]["title"] == "데이터 기반 서비스 개발 지원"
        assert result[0]["end_date"] == "2026-02-15"

    def test_noise_filtering_in_crawl(self):
        """크롤링 시 노이즈 공고가 필터링되는지 확인"""
        crawler = BoardCrawler(target_key="DIP")

        test_html = """
        <html><body>
        <table class="notice-board">
          <tbody>
            <tr>
              <td>1</td>
              <td><a href="/1">AI 스타트업 교육 프로그램</a></td>
              <td>2026-02-20</td>
            </tr>
            <tr>
              <td>2</td>
              <td><a href="/2">2026년 데이터 바우처 지원사업</a></td>
              <td>2026-03-15</td>
            </tr>
          </tbody>
        </table>
        </body></html>
        """

        with patch.object(crawler, 'fetch_html', return_value=test_html):
            result = crawler.crawl(pages=1)

        # "교육"이 포함된 공고는 필터링됨
        assert len(result) == 1
        assert result[0]["title"] == "2026년 데이터 바우처 지원사업"

    def test_empty_html_returns_empty(self):
        """빈 HTML에 대한 처리 확인"""
        crawler = BoardCrawler(target_key="DIP")
        result = crawler._parse_board_html("<html><body></body></html>")
        assert result == []


# ═══════════════════════════════════════════
# IrisCrawler 스켈레톤 테스트
# ═══════════════════════════════════════════

class TestIrisCrawler:
    """IRIS 크롤러 스켈레톤 테스트"""

    def test_init(self):
        """IrisCrawler 초기화 확인"""
        crawler = IrisCrawler()
        assert crawler.name == "IrisCrawler"

    def test_crawl_returns_empty(self):
        """Phase 2에서는 빈 리스트 반환 확인"""
        crawler = IrisCrawler()
        result = crawler.crawl()
        assert result == []

    def test_search_iris_returns_empty(self):
        """IRIS 검색 미구현 확인"""
        crawler = IrisCrawler()
        result = crawler.search_iris("AI")
        assert result == []


# ═══════════════════════════════════════════
# BaseCrawler 유틸리티 테스트
# ═══════════════════════════════════════════

class TestBaseCrawlerUtils:
    """BaseCrawler 정적 유틸리티 메서드 테스트"""

    def test_filter_noise_true(self):
        """노이즈 키워드 매칭 확인"""
        from collectors.base_crawler import BaseCrawler
        assert BaseCrawler.filter_noise("2026 AI 교육 세미나") is True
        assert BaseCrawler.filter_noise("사무실 인테리어 공사") is True

    def test_filter_noise_false(self):
        """정상 공고 제목은 통과 확인"""
        from collectors.base_crawler import BaseCrawler
        assert BaseCrawler.filter_noise("기후테크 R&D 지원사업") is False
        assert BaseCrawler.filter_noise("AI 데이터 플랫폼 개발") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
