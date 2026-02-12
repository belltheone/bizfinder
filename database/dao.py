# -*- coding: utf-8 -*-
"""
database/dao.py - 데이터 접근 객체 (Data Access Object)
=========================================================
SQLite 데이터베이스의 스키마 관리 및 CRUD 작업을 담당합니다.
해시 기반 중복 방지와 노이즈 필터링 로직을 포함합니다.

사용 예시:
    >>> from database.dao import ProjectDAO
    >>> dao = ProjectDAO()
    >>> dao.insert_project({
    ...     "title": "AI 플랫폼 개발",
    ...     "agency": "NIPA",
    ...     "source": "Group B",
    ...     "url": "https://example.com/1234",
    ... })
"""

import os
import sys
import hashlib
import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ── 로거 설정 ──
logger = logging.getLogger(__name__)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    SQLite 데이터베이스 연결을 생성합니다.

    Args:
        db_path: DB 파일 경로. None이면 config.DB_PATH 사용.
                 ':memory:' 전달 시 인메모리 DB 생성 (테스트용).

    Returns:
        sqlite3.Connection: DB 연결 객체
    """
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    # 딕셔너리처럼 접근할 수 있도록 Row 팩토리 설정
    conn.row_factory = sqlite3.Row
    # 외래 키 제약 활성화
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database(conn: sqlite3.Connection):
    """
    데이터베이스 스키마를 초기화합니다.
    테이블이 이미 존재하면 무시합니다.

    PRD 4절의 스키마 명세를 그대로 반영합니다.

    Args:
        conn: SQLite 연결 객체
    """
    cursor = conn.cursor()

    # ── projects 테이블 ──
    # 정부 지원사업 공고 정보를 저장하는 핵심 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            agency          TEXT DEFAULT '',
            source          TEXT DEFAULT '',
            url             TEXT DEFAULT '',
            files_text      TEXT DEFAULT '',
            total_budget    TEXT DEFAULT '',
            end_date        DATE,
            suitability_score INTEGER DEFAULT -1,
            target_entity   TEXT DEFAULT '',
            consortium_strategy TEXT DEFAULT '{}',
            ai_summary      TEXT DEFAULT '',
            is_manual       BOOLEAN DEFAULT 0,
            status          TEXT DEFAULT 'NEW',
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── exhibitions 테이블 ──
    # 전시회 일정 정보 (Market Intel 기능에서 사용)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exhibitions (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            location    TEXT DEFAULT '',
            start_date  DATE,
            category    TEXT DEFAULT '',
            url         TEXT DEFAULT ''
        )
    """)

    # ── 인덱스 생성 ──
    # 자주 조회되는 컬럼에 인덱스를 생성하여 검색 속도 향상
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_score ON projects(suitability_score DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_entity ON projects(target_entity)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_end_date ON projects(end_date)"
    )

    conn.commit()
    logger.info("데이터베이스 스키마가 초기화되었습니다.")


class ProjectDAO:
    """
    프로젝트(공고) 데이터 접근 객체
    =================================
    projects 테이블에 대한 CRUD 작업 및 비즈니스 로직을 제공합니다.
    해시 기반 중복 방지와 노이즈 필터링을 포함합니다.
    """

    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        """
        Args:
            conn: SQLite 연결 객체. None이면 config.DB_PATH로 새 연결 생성.
        """
        self.conn = conn or get_connection()
        init_database(self.conn)

    @staticmethod
    def generate_id(title: str, agency: str, date_str: str = "") -> str:
        """
        공고의 고유 ID를 생성합니다.
        제목 + 기관명 + 날짜를 조합하여 SHA256 해시를 생성합니다.

        Args:
            title: 공고 제목
            agency: 발주 기관명
            date_str: 날짜 문자열 (없으면 빈 문자열)

        Returns:
            str: SHA256 해시 문자열 (16자리로 절단하여 가독성 확보)
        """
        raw = f"{title.strip()}|{agency.strip()}|{date_str.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def is_noise(title: str) -> bool:
        """
        제목이 노이즈 키워드를 포함하는지 확인합니다.
        노이즈에 해당하면 DB에 저장하지 않고 즉시 폐기합니다.

        Args:
            title: 공고 제목

        Returns:
            bool: 노이즈이면 True
        """
        for keyword in config.NOISE_KEYWORDS:
            if keyword in title:
                logger.debug(f"노이즈 필터링: '{title}' (매칭: '{keyword}')")
                return True
        return False

    def exists(self, project_id: str) -> bool:
        """
        해당 ID의 프로젝트가 이미 존재하는지 확인합니다.
        중복 삽입을 방지하기 위한 해시 체크 메서드입니다.

        Args:
            project_id: 공고 고유 ID

        Returns:
            bool: 존재하면 True
        """
        cursor = self.conn.execute(
            "SELECT 1 FROM projects WHERE id = ?", (project_id,)
        )
        return cursor.fetchone() is not None

    def insert_project(self, data: dict) -> Optional[str]:
        """
        새 프로젝트(공고)를 저장합니다.

        자동으로 수행하는 전처리:
        1. 노이즈 필터링 (제목에 필터 키워드 포함 시 저장 거부)
        2. 해시 기반 중복 체크 (이미 존재하면 저장 거부)
        3. ID 자동 생성 (title + agency + end_date 해시)

        Args:
            data: 공고 정보 딕셔너리. 최소 'title' 필드 필수.
                  선택: agency, source, url, files_text, total_budget,
                        end_date, suitability_score, target_entity,
                        consortium_strategy, ai_summary, is_manual, status

        Returns:
            str: 저장된 프로젝트 ID. 저장 거부 시 None.
        """
        title = data.get("title", "").strip()
        if not title:
            logger.warning("제목이 비어있어 저장할 수 없습니다.")
            return None

        # 1. 노이즈 필터링
        if self.is_noise(title):
            logger.info(f"노이즈로 폐기됨: {title}")
            return None

        # 2. ID 생성 및 중복 체크
        agency = data.get("agency", "")
        end_date = data.get("end_date", "")
        project_id = data.get("id") or self.generate_id(title, agency, end_date)

        if self.exists(project_id):
            logger.info(f"중복 공고 무시: {title} (ID: {project_id})")
            return None

        # 3. 데이터 삽입
        # consortium_strategy는 JSON 직렬화
        consortium = data.get("consortium_strategy", {})
        if isinstance(consortium, dict):
            consortium = json.dumps(consortium, ensure_ascii=False)

        try:
            self.conn.execute(
                """
                INSERT INTO projects
                    (id, title, agency, source, url, files_text,
                     total_budget, end_date, suitability_score,
                     target_entity, consortium_strategy, ai_summary,
                     is_manual, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    title,
                    agency,
                    data.get("source", ""),
                    data.get("url", ""),
                    data.get("files_text", ""),
                    data.get("total_budget", ""),
                    end_date or None,
                    data.get("suitability_score", -1),
                    data.get("target_entity", ""),
                    consortium,
                    data.get("ai_summary", ""),
                    1 if data.get("is_manual", False) else 0,
                    data.get("status", "NEW"),
                    datetime.now().isoformat(),
                ),
            )
            self.conn.commit()
            logger.info(f"공고 저장 완료: {title} (ID: {project_id})")
            return project_id

        except sqlite3.Error as e:
            logger.error(f"DB 저장 오류: {e}")
            self.conn.rollback()
            return None

    def get_project(self, project_id: str) -> Optional[dict]:
        """
        ID로 프로젝트를 조회합니다.

        Args:
            project_id: 공고 고유 ID

        Returns:
            dict: 프로젝트 정보. 없으면 None.
        """
        cursor = self.conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_projects(
        self,
        entity: Optional[str] = None,
        status: Optional[str] = None,
        order_by: str = "suitability_score DESC",
    ) -> list[dict]:
        """
        프로젝트 목록을 조회합니다.

        Args:
            entity: 필터 - 'STLABS' 또는 'Stratio'. None이면 전체 조회.
            status: 필터 - 'NEW', 'READ', 'HIDDEN', 'TRASH'. None이면 전체.
            order_by: 정렬 기준. 기본은 점수 내림차순.

        Returns:
            list[dict]: 프로젝트 목록
        """
        query = "SELECT * FROM projects WHERE 1=1"
        params = []

        if entity:
            query += " AND target_entity = ?"
            params.append(entity)

        if status:
            query += " AND status = ?"
            params.append(status)

        # order_by는 사전 정의된 값만 허용 (SQL Injection 방지)
        allowed_orders = {
            "suitability_score DESC": "suitability_score DESC",
            "end_date ASC": "end_date ASC",
            "total_budget DESC": "total_budget DESC",
            "created_at DESC": "created_at DESC",
        }
        safe_order = allowed_orders.get(order_by, "suitability_score DESC")
        query += f" ORDER BY {safe_order}"

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def update_project(self, project_id: str, updates: dict) -> bool:
        """
        프로젝트 정보를 업데이트합니다.

        Args:
            project_id: 대상 공고 ID
            updates: 업데이트할 필드와 값의 딕셔너리

        Returns:
            bool: 성공 여부
        """
        if not updates:
            return False

        # consortium_strategy가 dict이면 JSON 변환
        if "consortium_strategy" in updates and isinstance(
            updates["consortium_strategy"], dict
        ):
            updates["consortium_strategy"] = json.dumps(
                updates["consortium_strategy"], ensure_ascii=False
            )

        # 허용된 컬럼명만 사용 (SQL Injection 방지)
        allowed_columns = {
            "title", "agency", "source", "url", "files_text",
            "total_budget", "end_date", "suitability_score",
            "target_entity", "consortium_strategy", "ai_summary",
            "is_manual", "status",
        }
        safe_updates = {k: v for k, v in updates.items() if k in allowed_columns}

        if not safe_updates:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in safe_updates)
        values = list(safe_updates.values()) + [project_id]

        try:
            self.conn.execute(
                f"UPDATE projects SET {set_clause} WHERE id = ?", values
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"DB 업데이트 오류: {e}")
            self.conn.rollback()
            return False

    def count_projects(self, status: Optional[str] = None) -> int:
        """
        프로젝트 수를 반환합니다.

        Args:
            status: 상태 필터. None이면 전체.

        Returns:
            int: 프로젝트 수
        """
        if status:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM projects WHERE status = ?", (status,)
            )
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM projects")
        return cursor.fetchone()[0]

    def count_today_new(self) -> int:
        """
        금일 신규 공고 수를 반환합니다.

        Returns:
            int: 금일 신규 공고 수
        """
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM projects WHERE created_at LIKE ?",
            (f"{today}%",),
        )
        return cursor.fetchone()[0]


class ExhibitionDAO:
    """
    전시회 데이터 접근 객체
    ========================
    exhibitions 테이블에 대한 CRUD 작업을 제공합니다.
    """

    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        self.conn = conn or get_connection()
        init_database(self.conn)

    @staticmethod
    def generate_id(name: str, start_date: str) -> str:
        """전시회 고유 ID 생성 (이름 + 시작일 해시)"""
        raw = f"{name.strip()}|{start_date.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def insert_exhibition(self, data: dict) -> Optional[str]:
        """
        전시회 정보를 저장합니다.

        Args:
            data: 전시회 정보 (name, location, start_date, category, url)

        Returns:
            str: 저장된 전시회 ID. 중복 시 None.
        """
        name = data.get("name", "").strip()
        start_date = data.get("start_date", "")
        if not name:
            return None

        exh_id = data.get("id") or self.generate_id(name, start_date)

        # 중복 체크
        cursor = self.conn.execute(
            "SELECT 1 FROM exhibitions WHERE id = ?", (exh_id,)
        )
        if cursor.fetchone():
            return None

        try:
            self.conn.execute(
                """
                INSERT INTO exhibitions (id, name, location, start_date, category, url)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    exh_id,
                    name,
                    data.get("location", ""),
                    start_date or None,
                    data.get("category", ""),
                    data.get("url", ""),
                ),
            )
            self.conn.commit()
            return exh_id
        except sqlite3.Error as e:
            logger.error(f"전시회 DB 저장 오류: {e}")
            self.conn.rollback()
            return None

    def get_all_exhibitions(self) -> list[dict]:
        """전체 전시회 목록 조회"""
        cursor = self.conn.execute(
            "SELECT * FROM exhibitions ORDER BY start_date ASC"
        )
        return [dict(row) for row in cursor.fetchall()]
