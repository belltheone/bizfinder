# -*- coding: utf-8 -*-
"""
collectors/base_crawler.py - 크롤러 추상 기반 클래스
======================================================
모든 크롤러의 공통 인터페이스와 유틸리티를 정의합니다.
"""

import os
import sys
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urlparse

import requests

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ── 로거 설정 ──
logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """
    크롤러 추상 기반 클래스
    ========================
    모든 크롤러(BizinfoCrawler, BoardCrawler, IrisCrawler)의
    공통 인터페이스와 유틸리티 메서드를 제공합니다.
    """

    def __init__(self, name: str = "BaseCrawler"):
        """
        Args:
            name: 크롤러 이름 (로깅용)
        """
        self.name = name
        self.session = requests.Session()
        self.session.headers.update(config.REQUEST_HEADERS)
        logger.info(f"[{self.name}] 크롤러 초기화 완료")

    @abstractmethod
    def crawl(self) -> list[dict]:
        """
        데이터를 수집하여 공고 목록을 반환합니다.

        Returns:
            list[dict]: 수집된 공고 정보 딕셔너리 목록
                각 딕셔너리는 최소한 'title' 키를 포함해야 합니다.
        """
        pass

    def fetch_html(self, url: str, timeout: int = None) -> Optional[str]:
        """
        URL에서 HTML을 가져옵니다.

        Args:
            url: 대상 URL
            timeout: 요청 타임아웃 (초). None이면 config 기본값 사용.

        Returns:
            str: HTML 문자열. 실패 시 None.
        """
        try:
            response = self.session.get(
                url, timeout=timeout or config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            logger.debug(f"[{self.name}] HTML 가져오기 성공: {url}")
            return response.text
        except requests.RequestException as e:
            logger.error(f"[{self.name}] HTML 가져오기 실패: {url} - {e}")
            return None

    def fetch_json(self, url: str, params: dict = None) -> Optional[dict]:
        """
        URL에서 JSON 데이터를 가져옵니다.

        Args:
            url: API 엔드포인트 URL
            params: 쿼리 파라미터

        Returns:
            dict: JSON 응답. 실패 시 None.
        """
        try:
            response = self.session.get(
                url, params=params, timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            logger.debug(f"[{self.name}] JSON 가져오기 성공: {url}")
            return data
        except (requests.RequestException, ValueError) as e:
            logger.error(f"[{self.name}] JSON 가져오기 실패: {url} - {e}")
            return None

    def download_file(self, url: str, filename: str = None) -> Optional[str]:
        """
        첨부파일을 다운로드하여 temp/ 디렉토리에 저장합니다.
        파일명은 URL의 해시값을 기반으로 고유하게 생성됩니다.

        Args:
            url: 파일 다운로드 URL
            filename: 저장할 파일명. None이면 URL 기반 자동 생성.

        Returns:
            str: 저장된 파일의 절대 경로. 실패 시 None.
        """
        try:
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()

            # 파일명 결정
            if not filename:
                # URL에서 확장자 추출
                parsed = urlparse(url)
                path = parsed.path
                ext = os.path.splitext(path)[1] or ".bin"
                # URL 해시를 파일명으로 사용
                url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                filename = f"{url_hash}{ext}"

            file_path = os.path.join(config.TEMP_DIR, filename)

            with open(file_path, "wb") as f:
                f.write(response.content)

            logger.info(
                f"[{self.name}] 파일 다운로드 완료: {filename} "
                f"({len(response.content):,} bytes)"
            )
            return file_path

        except requests.RequestException as e:
            logger.error(f"[{self.name}] 파일 다운로드 실패: {url} - {e}")
            return None

    @staticmethod
    def filter_noise(title: str) -> bool:
        """
        공고 제목이 노이즈 키워드를 포함하는지 확인합니다.

        Args:
            title: 공고 제목

        Returns:
            bool: 노이즈이면 True (폐기 대상)
        """
        for keyword in config.NOISE_KEYWORDS:
            if keyword in title:
                return True
        return False
