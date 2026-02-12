# -*- coding: utf-8 -*-
"""
collectors/bizinfo_crawler.py - 기업마당 API 크롤러
=====================================================
기업마당(Bizinfo) Open API를 활용하여 정부 지원사업 공고를 수집합니다.
Group A의 가장 기본적인 데이터 소스입니다.

API 엔드포인트: https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do
인증: crtfcKey (기업마당 사이트에서 이메일로 발급)
호출방식: GET
응답 형식: JSON (dataType=json) 또는 XML/RSS (dataType=rss)

요청 파라미터:
  - crtfcKey (필수): 서비스 인증키
  - dataType (선택): json | rss (기본: rss)

응답 주요 필드 (jsonArray 또는 item 배열):
  - pblancNm     : 공고명
  - jrsdInsttNm  : 소관기관명
  - excInsttNm   : 수행기관명
  - reqstBeginEndDe : 접수기간
  - pblancUrl / link : 공고 상세 URL
  - bsnsSumryCn  : 사업 요약 내용
  - totBudget    : 총 예산 (있는 경우)

API 키 발급:
  https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi
  하단의 'API 사용 신청' 폼에서 정보 입력 후 이메일로 인증키 수신

사용 예시:
    >>> from collectors.bizinfo_crawler import BizinfoCrawler
    >>> crawler = BizinfoCrawler(api_key="YOUR_KEY")
    >>> results = crawler.crawl()
    >>> print(f"수집된 공고: {len(results)}건")
"""

import os
import sys
import logging
from typing import Optional

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from collectors.base_crawler import BaseCrawler

# ── 로거 설정 ──
logger = logging.getLogger(__name__)


class BizinfoCrawler(BaseCrawler):
    """
    기업마당 Open API 크롤러
    =========================
    REST API를 통해 정부 지원사업 공고를 JSON 형태로 수집합니다.
    """

    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: 기업마당 API 인증 키. None이면 config/.env에서 읽음.
        """
        super().__init__(name="BizinfoCrawler")
        self.api_key = api_key or config.BIZINFO_API_KEY
        self.api_url = config.BIZINFO_API_URL

        if not self.api_key:
            logger.warning(
                "기업마당 API 키가 설정되지 않았습니다. "
                ".env 파일에 BIZINFO_API_KEY를 설정하세요. "
                "발급: https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi"
            )

    def crawl(self, page_count: int = 3) -> list[dict]:
        """
        기업마당 API에서 공고 목록을 수집합니다.

        Args:
            page_count: 수집할 페이지 수 (각 페이지 기본 20건)

        Returns:
            list[dict]: 수집된 공고 정보 목록
        """
        if not self.api_key:
            logger.error("API 키가 없어 수집을 중단합니다.")
            return []

        all_items = []

        for page_no in range(1, page_count + 1):
            items = self._fetch_page(page_no)
            if not items:
                break
            all_items.extend(items)
            logger.info(
                f"[BizinfoCrawler] 페이지 {page_no} 수집 완료: {len(items)}건"
            )

        # 노이즈 필터링 적용
        filtered = [
            item for item in all_items
            if not self.filter_noise(item.get("title", ""))
        ]
        logger.info(
            f"[BizinfoCrawler] 최종 수집: {len(filtered)}건 "
            f"(필터링 전: {len(all_items)}건)"
        )
        return filtered

    def _fetch_page(self, page_no: int = 1) -> list[dict]:
        """
        단일 페이지의 공고 목록을 가져옵니다.

        API 파라미터:
        - crtfcKey (필수): 인증 키
        - dataType (선택): json

        Args:
            page_no: 페이지 번호

        Returns:
            list[dict]: 파싱된 공고 목록
        """
        params = {
            "crtfcKey": self.api_key,
            "dataType": "json",
        }

        data = self.fetch_json(self.api_url, params=params)
        if not data:
            return []

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> list[dict]:
        """
        API JSON 응답에서 공고 정보를 추출합니다.

        기업마당 API 응답 구조 (두 가지 형태 대응):
        형태 1: { "jsonArray": [ {...}, ... ] }
        형태 2: { "item": [ {...}, ... ] }

        각 항목 주요 필드:
        - pblancNm      : 공고명
        - jrsdInsttNm   : 소관기관명
        - excInsttNm    : 수행기관명
        - reqstBeginEndDe : 접수기간 (예: "2026-01-15 ~ 2026-03-31")
        - pblancUrl     : 공고 URL (1차)
        - link          : 공고 URL (2차, RSS 형식)
        - bsnsSumryCn   : 사업 요약 내용
        - totBudget     : 총 예산

        Args:
            data: API JSON 응답

        Returns:
            list[dict]: 정규화된 공고 정보 목록
        """
        items = []

        # 응답 구조 탐색 - 실제 API는 jsonArray 또는 item 키를 사용
        json_array = data.get("jsonArray", [])
        if not json_array:
            json_array = data.get("item", data.get("items", data.get("data", [])))
        # 단일 객체가 반환되는 경우 리스트로 감싸기
        if isinstance(json_array, dict):
            json_array = [json_array]

        for raw in json_array:
            try:
                # 날짜 추출 (접수기간에서 마감일 파싱)
                end_date = self._extract_end_date(
                    raw.get("reqstBeginEndDe", "")
                )

                # URL: pblancUrl 우선, 없으면 link 사용
                url = (raw.get("pblancUrl", "") or raw.get("link", "")).strip()

                # 기관명: 소관기관 우선, 없으면 수행기관
                agency = (raw.get("jrsdInsttNm", "") or raw.get("excInsttNm", "")).strip()

                item = {
                    "title": raw.get("pblancNm", "").strip(),
                    "agency": agency,
                    "source": "Group A - Bizinfo",
                    "url": url,
                    "total_budget": raw.get("totBudget", ""),
                    "end_date": end_date,
                    "summary": raw.get("bsnsSumryCn", "").strip(),
                    "status": "NEW",
                }

                # 제목이 있는 항목만 추가
                if item["title"]:
                    items.append(item)

            except Exception as e:
                logger.warning(f"공고 파싱 오류: {e}")
                continue

        return items

    @staticmethod
    def _extract_end_date(date_range: str) -> str:
        """
        접수기간 문자열에서 마감일을 추출합니다.

        입력 형식 예시:
        - "2026-01-15 ~ 2026-03-31"
        - "2026.01.15 ~ 2026.03.31"
        - "20260115 ~ 20260331"

        Args:
            date_range: 접수기간 문자열

        Returns:
            str: YYYY-MM-DD 형식의 마감일. 파싱 실패 시 빈 문자열.
        """
        if not date_range or "~" not in date_range:
            return ""

        try:
            end_part = date_range.split("~")[-1].strip()
            # 구분자(-, .) 제거 후 8자리 숫자 확인
            clean = end_part.replace("-", "").replace(".", "").replace(" ", "")
            if len(clean) >= 8 and clean[:8].isdigit():
                return f"{clean[:4]}-{clean[4:6]}-{clean[6:8]}"
        except (IndexError, ValueError):
            pass

        return ""

