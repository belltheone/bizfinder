# -*- coding: utf-8 -*-
"""
collectors/iris_crawler.py - IRIS/NTIS 동적 페이지 크롤러 (스켈레톤)
======================================================================
IRIS 및 NTIS는 JavaScript로 렌더링되는 동적 페이지이므로,
IDE 내장 브라우저 제어 기능을 활용하여 데이터를 수집합니다.

현재 Phase 2에서는 인터페이스(스켈레톤)만 정의하며,
Phase 4 (UI 구현) 단계에서 실제 브라우저 연동을 구현합니다.

사용 예시 (Phase 4 완성 후):
    >>> from collectors.iris_crawler import IrisCrawler
    >>> crawler = IrisCrawler()
    >>> results = crawler.crawl()
"""

import os
import sys
import logging

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from collectors.base_crawler import BaseCrawler

# ── 로거 설정 ──
logger = logging.getLogger(__name__)


class IrisCrawler(BaseCrawler):
    """
    IRIS/NTIS 동적 페이지 크롤러 (스켈레톤)
    ==========================================
    IDE 내장 브라우저를 활용한 동적 렌더링 기반 크롤러입니다.

    구현 예정 기능:
    - IRIS 검색 페이지에 키워드 입력 후 결과 파싱
    - NTIS 과제 검색 결과 수집
    - 검색 키워드: config.SEARCH_KEYWORDS 활용

    Note:
        Phase 4에서 Streamlit UI와 통합 시 구현됩니다.
        Selenium/Playwright 대신 IDE 내장 브라우저 기능을 사용합니다.
    """

    # IRIS/NTIS URL 상수
    IRIS_URL = "https://www.iris.go.kr/contents/retrieveBsnsAnnoDetailView.do"
    NTIS_URL = "https://www.ntis.go.kr/ThSearchTotalList.do"

    def __init__(self):
        super().__init__(name="IrisCrawler")
        self.search_keywords = config.SEARCH_KEYWORDS
        logger.info(
            f"[IrisCrawler] 스켈레톤 초기화 (검색 키워드: {self.search_keywords})"
        )

    def crawl(self) -> list[dict]:
        """
        IRIS/NTIS에서 공고를 수집합니다.

        현재 Phase 2에서는 빈 리스트를 반환합니다.
        Phase 4에서 IDE 내장 브라우저 연동 시 실제 구현됩니다.

        Returns:
            list[dict]: 수집된 공고 목록 (현재 빈 리스트)
        """
        logger.warning(
            "[IrisCrawler] 아직 구현되지 않았습니다. "
            "Phase 4에서 IDE 브라우저 연동 후 활성화됩니다."
        )
        # TODO: Phase 4에서 구현
        # 1. IDE 내장 브라우저로 IRIS 페이지 열기
        # 2. 검색창에 키워드 입력 (config.SEARCH_KEYWORDS 순회)
        # 3. 결과 렌더링 대기
        # 4. HTML 파싱하여 공고 목록 추출
        return []

    def search_iris(self, keyword: str) -> list[dict]:
        """
        IRIS에서 특정 키워드로 검색합니다. (Phase 4에서 구현 예정)

        Args:
            keyword: 검색 키워드

        Returns:
            list[dict]: 검색 결과
        """
        logger.warning(f"[IrisCrawler] IRIS 검색 미구현: {keyword}")
        return []

    def search_ntis(self, keyword: str) -> list[dict]:
        """
        NTIS에서 특정 키워드로 검색합니다. (Phase 4에서 구현 예정)

        Args:
            keyword: 검색 키워드

        Returns:
            list[dict]: 검색 결과
        """
        logger.warning(f"[IrisCrawler] NTIS 검색 미구현: {keyword}")
        return []
