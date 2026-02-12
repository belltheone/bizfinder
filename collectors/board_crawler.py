# -*- coding: utf-8 -*-
"""
collectors/board_crawler.py - 범용 게시판 크롤러
===================================================
Group B(전문 기관 게시판) 및 Group C(지역 거점) 사이트에서
BeautifulSoup을 사용하여 공고 목록을 파싱합니다.

사이트별 파싱 규칙은 config.CRAWL_TARGETS에 정의되며,
각 사이트의 HTML 구조에 맞는 파서를 내부적으로 선택합니다.

사용 예시:
    >>> from collectors.board_crawler import BoardCrawler
    >>> crawler = BoardCrawler(target_key="DIP")
    >>> results = crawler.crawl()
"""

import os
import re
import sys
import logging
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from collectors.base_crawler import BaseCrawler

# ── 로거 설정 ──
logger = logging.getLogger(__name__)


class BoardCrawler(BaseCrawler):
    """
    범용 게시판 크롤러
    ====================
    HTML 게시판에서 공고 목록을 파싱합니다.
    <table> 태그 기반 및 <div> 기반 게시판을 모두 지원합니다.
    """

    def __init__(self, target_key: str = None, custom_url: str = None,
                 custom_name: str = "CustomBoard"):
        """
        Args:
            target_key: config.CRAWL_TARGETS의 키 (예: "DIP", "NIPA")
            custom_url: 직접 URL을 지정할 경우 (target_key 대신)
            custom_name: custom_url 사용 시 크롤러 이름
        """
        # 설정에서 대상 사이트 정보 로드
        if target_key and target_key in config.CRAWL_TARGETS:
            target = config.CRAWL_TARGETS[target_key]
            self.target_name = target["name"]
            self.board_url = target["board_url"]
            self.base_url = target["base_url"]
            self.group = target["group"]
        elif custom_url:
            self.target_name = custom_name
            self.board_url = custom_url
            self.base_url = custom_url
            self.group = "Custom"
        else:
            raise ValueError(
                f"유효한 target_key 또는 custom_url이 필요합니다. "
                f"사용 가능한 target_key: {list(config.CRAWL_TARGETS.keys())}"
            )

        super().__init__(name=f"BoardCrawler-{self.target_name}")

    def crawl(self, pages: int = 1) -> list[dict]:
        """
        게시판에서 공고 목록을 수집합니다.

        Args:
            pages: 수집할 페이지 수

        Returns:
            list[dict]: 수집된 공고 정보 목록
        """
        all_items = []

        for page in range(1, pages + 1):
            # 페이지 URL 구성 (게시판마다 페이징 파라미터가 다를 수 있음)
            page_url = self._build_page_url(page)
            html = self.fetch_html(page_url)
            if not html:
                logger.warning(f"[{self.name}] 페이지 {page} 로드 실패")
                continue

            items = self._parse_board_html(html)
            if not items:
                break
            all_items.extend(items)
            logger.info(
                f"[{self.name}] 페이지 {page} 수집: {len(items)}건"
            )

        # 노이즈 필터링
        filtered = [
            item for item in all_items
            if not self.filter_noise(item.get("title", ""))
        ]
        logger.info(
            f"[{self.name}] 최종 수집: {len(filtered)}건 "
            f"(필터링 전: {len(all_items)}건)"
        )
        return filtered

    def _build_page_url(self, page: int) -> str:
        """
        페이지 번호에 따른 URL을 구성합니다.
        게시판마다 페이징 파라미터가 다르므로 유연하게 처리합니다.

        Args:
            page: 페이지 번호

        Returns:
            str: 페이지 URL
        """
        url = self.board_url
        # URL에 이미 파라미터가 있는 경우
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}page={page}"

    def _parse_board_html(self, html: str) -> list[dict]:
        """
        게시판 HTML에서 공고 목록을 추출합니다.

        두 가지 전략을 순차적으로 시도합니다:
        1. <table> 기반 게시판 파싱
        2. <div> 리스트 기반 게시판 파싱

        Args:
            html: 게시판 페이지 HTML

        Returns:
            list[dict]: 파싱된 공고 목록
        """
        soup = BeautifulSoup(html, "lxml")
        items = []

        # 전략 1: <table> 기반 게시판 파싱
        items = self._parse_table_board(soup)

        # 전략 2: 결과가 없으면 <div> 리스트 기반 파싱
        if not items:
            items = self._parse_div_board(soup)

        return items

    def _parse_table_board(self, soup: BeautifulSoup) -> list[dict]:
        """
        <table> 태그 기반 게시판을 파싱합니다.

        일반적인 게시판 테이블 구조:
        <table>
          <thead>...</thead>
          <tbody>
            <tr>
              <td>번호</td>
              <td><a href="...">제목</a></td>
              <td>작성자/기관</td>
              <td>날짜</td>
              ...
            </tr>
          </tbody>
        </table>

        Args:
            soup: BeautifulSoup 객체

        Returns:
            list[dict]: 파싱된 공고 목록
        """
        items = []

        # 게시판 테이블 찾기 (board, list, notice 등의 클래스명을 가진 테이블 우선)
        tables = soup.find_all("table", class_=re.compile(
            r"(board|list|notice|bbs|tbl|table)", re.IGNORECASE
        ))
        if not tables:
            # class 없는 일반 테이블도 시도
            tables = soup.find_all("table")

        for table in tables:
            tbody = table.find("tbody") or table
            rows = tbody.find_all("tr")

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                # 제목이 포함된 셀 찾기 (보통 <a> 태그가 있는 셀)
                title_cell = None
                link_href = ""
                for cell in cells:
                    link = cell.find("a")
                    if link and link.get_text(strip=True):
                        title_cell = cell
                        link_href = link.get("href", "")
                        break

                if not title_cell:
                    continue

                title = title_cell.get_text(strip=True)
                if not title:
                    continue

                # 절대 URL로 변환
                if link_href:
                    link_href = urljoin(self.base_url, link_href)

                # 날짜 추출 (숫자와 - 또는 . 으로 구성된 셀)
                end_date = ""
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    date_match = re.search(
                        r'(\d{4}[-./]\d{2}[-./]\d{2})', cell_text
                    )
                    if date_match:
                        end_date = date_match.group(1).replace(".", "-").replace("/", "-")
                        break

                items.append({
                    "title": title,
                    "agency": self.target_name,
                    "source": f"Group {self.group} - {self.target_name}",
                    "url": link_href,
                    "end_date": end_date,
                    "status": "NEW",
                })

            # 첫 번째 유효한 테이블에서 결과를 찾으면 중지
            if items:
                break

        return items

    def _parse_div_board(self, soup: BeautifulSoup) -> list[dict]:
        """
        <div> 리스트 기반 게시판을 파싱합니다.

        최근 게시판들은 <table> 대신 <div>, <ul>, <li> 구조를 사용합니다.

        Args:
            soup: BeautifulSoup 객체

        Returns:
            list[dict]: 파싱된 공고 목록
        """
        items = []

        # 게시판 리스트 컨테이너 찾기
        list_containers = soup.find_all(
            ["div", "ul", "ol"],
            class_=re.compile(
                r"(board|list|notice|bbs|post)", re.IGNORECASE
            ),
        )

        for container in list_containers:
            # 리스트 아이템 찾기
            list_items = container.find_all(
                ["li", "div", "article"],
                class_=re.compile(r"(item|row|post|entry)", re.IGNORECASE),
            )
            if not list_items:
                list_items = container.find_all("li")

            for li in list_items:
                link = li.find("a")
                if not link:
                    continue

                title = link.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                href = urljoin(self.base_url, link.get("href", ""))

                # 날짜 추출
                end_date = ""
                date_elem = li.find(
                    ["span", "em", "time"],
                    class_=re.compile(r"(date|time|day)", re.IGNORECASE),
                )
                if date_elem:
                    date_match = re.search(
                        r'(\d{4}[-./]\d{2}[-./]\d{2})',
                        date_elem.get_text(),
                    )
                    if date_match:
                        end_date = date_match.group(1).replace(".", "-").replace("/", "-")

                items.append({
                    "title": title,
                    "agency": self.target_name,
                    "source": f"Group {self.group} - {self.target_name}",
                    "url": href,
                    "end_date": end_date,
                    "status": "NEW",
                })

        return items

    def find_attachment_links(self, detail_url: str) -> list[str]:
        """
        공고 상세 페이지에서 첨부파일 다운로드 링크를 찾습니다.
        지원하는 확장자(.hwp, .hwpx, .pdf)만 필터링합니다.

        Args:
            detail_url: 공고 상세 페이지 URL

        Returns:
            list[str]: 첨부파일 다운로드 링크 목록
        """
        html = self.fetch_html(detail_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        attachment_links = []

        # 모든 <a> 태그에서 파일 링크 찾기
        for link in soup.find_all("a", href=True):
            href = link["href"].lower()
            # 지원하는 확장자의 파일 링크인지 확인
            for ext in config.SUPPORTED_EXTENSIONS:
                if href.endswith(ext) or ext in href:
                    full_url = urljoin(detail_url, link["href"])
                    attachment_links.append(full_url)
                    break

        logger.info(
            f"[{self.name}] 첨부파일 {len(attachment_links)}개 발견: {detail_url}"
        )
        return attachment_links


class MultiSiteCrawler:
    """
    다중 사이트 일괄 크롤러
    ========================
    config.CRAWL_TARGETS에 등록된 모든 사이트를 순차적으로 크롤링합니다.
    """

    def crawl_all(self, pages_per_site: int = 1) -> list[dict]:
        """
        등록된 모든 게시판 사이트에서 공고를 수집합니다.

        Args:
            pages_per_site: 사이트당 수집할 페이지 수

        Returns:
            list[dict]: 전체 수집 결과
        """
        all_items = []

        for key in config.CRAWL_TARGETS:
            try:
                crawler = BoardCrawler(target_key=key)
                items = crawler.crawl(pages=pages_per_site)
                all_items.extend(items)
                logger.info(f"[MultiSiteCrawler] {key}: {len(items)}건 수집")
            except Exception as e:
                logger.error(f"[MultiSiteCrawler] {key} 크롤링 실패: {e}")
                continue

        logger.info(
            f"[MultiSiteCrawler] 전체 수집 완료: {len(all_items)}건"
        )
        return all_items
