# -*- coding: utf-8 -*-
"""
tests/test_dao.py - DAO 단위 테스트
======================================
인메모리 SQLite(':memory:')를 사용하여 외부 의존성 없이
ProjectDAO와 ExhibitionDAO의 동작을 검증합니다.

실행: python -m pytest tests/test_dao.py -v
"""

import os
import sys
import sqlite3

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.dao import ProjectDAO, ExhibitionDAO, get_connection, init_database


@pytest.fixture
def memory_conn():
    """인메모리 SQLite 연결 픽스처"""
    conn = get_connection(":memory:")
    init_database(conn)
    yield conn
    conn.close()


@pytest.fixture
def project_dao(memory_conn):
    """ProjectDAO 인스턴스 픽스처"""
    return ProjectDAO(conn=memory_conn)


@pytest.fixture
def exhibition_dao(memory_conn):
    """ExhibitionDAO 인스턴스 픽스처"""
    return ExhibitionDAO(conn=memory_conn)


# ═══════════════════════════════════════════
# 스키마 테스트
# ═══════════════════════════════════════════

class TestSchema:
    """데이터베이스 스키마 생성 검증"""

    def test_projects_table_exists(self, memory_conn):
        """projects 테이블이 생성되었는지 확인"""
        cursor = memory_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
        )
        assert cursor.fetchone() is not None

    def test_exhibitions_table_exists(self, memory_conn):
        """exhibitions 테이블이 생성되었는지 확인"""
        cursor = memory_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='exhibitions'"
        )
        assert cursor.fetchone() is not None

    def test_projects_columns(self, memory_conn):
        """projects 테이블의 컬럼 구조 확인"""
        cursor = memory_conn.execute("PRAGMA table_info(projects)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "id", "title", "agency", "source", "url", "files_text",
            "total_budget", "end_date", "suitability_score", "target_entity",
            "consortium_strategy", "ai_summary", "is_manual", "status", "created_at"
        }
        assert expected.issubset(columns)


# ═══════════════════════════════════════════
# ProjectDAO 테스트
# ═══════════════════════════════════════════

class TestProjectDAO:
    """ProjectDAO CRUD 및 비즈니스 로직 테스트"""

    def test_generate_id_deterministic(self):
        """동일한 입력에 대해 동일한 ID가 생성되는지 확인"""
        id1 = ProjectDAO.generate_id("테스트 공고", "NIPA", "2026-03-31")
        id2 = ProjectDAO.generate_id("테스트 공고", "NIPA", "2026-03-31")
        assert id1 == id2

    def test_generate_id_different_inputs(self):
        """다른 입력에 대해 다른 ID가 생성되는지 확인"""
        id1 = ProjectDAO.generate_id("공고 A", "NIPA", "2026-03-31")
        id2 = ProjectDAO.generate_id("공고 B", "NIPA", "2026-03-31")
        assert id1 != id2

    def test_insert_and_retrieve(self, project_dao):
        """공고 삽입 및 조회 확인"""
        pid = project_dao.insert_project({
            "title": "AI 기반 기후테크 플랫폼 개발",
            "agency": "NIPA",
            "source": "Group B",
            "url": "https://example.com/1234",
            "total_budget": "5억원",
            "end_date": "2026-03-31",
        })

        assert pid is not None

        project = project_dao.get_project(pid)
        assert project is not None
        assert project["title"] == "AI 기반 기후테크 플랫폼 개발"
        assert project["agency"] == "NIPA"
        assert project["total_budget"] == "5억원"
        assert project["status"] == "NEW"

    def test_duplicate_prevention(self, project_dao):
        """해시 기반 중복 삽입 방지 확인"""
        data = {
            "title": "동일한 공고",
            "agency": "IITP",
            "end_date": "2026-06-30",
        }

        pid1 = project_dao.insert_project(data)
        pid2 = project_dao.insert_project(data)

        assert pid1 is not None
        assert pid2 is None  # 중복이므로 None 반환
        assert project_dao.count_projects() == 1

    def test_noise_filtering_education(self, project_dao):
        """노이즈 필터링: '교육' 키워드 포함 공고 폐기 확인"""
        pid = project_dao.insert_project({
            "title": "2026년 스타트업 교육 프로그램 참가자 모집",
            "agency": "K-Startup",
        })
        assert pid is None  # 노이즈로 폐기
        assert project_dao.count_projects() == 0

    def test_noise_filtering_seminar(self, project_dao):
        """노이즈 필터링: '세미나' 키워드 포함 공고 폐기 확인"""
        pid = project_dao.insert_project({
            "title": "AI 기술 세미나 안내",
            "agency": "NIA",
        })
        assert pid is None

    def test_noise_filtering_construction(self, project_dao):
        """노이즈 필터링: '공사' 키워드 포함 공고 폐기 확인"""
        pid = project_dao.insert_project({
            "title": "사무실 인테리어 공사 업체 모집",
            "agency": "DIP",
        })
        assert pid is None

    def test_valid_title_passes_noise_filter(self, project_dao):
        """정상 공고 제목은 노이즈 필터를 통과하는지 확인"""
        pid = project_dao.insert_project({
            "title": "2026년 AI·데이터 기반 서비스 개발 지원사업 공고",
            "agency": "NIPA",
        })
        assert pid is not None

    def test_empty_title_rejected(self, project_dao):
        """빈 제목은 저장 거부 확인"""
        pid = project_dao.insert_project({"title": ""})
        assert pid is None

    def test_update_project(self, project_dao):
        """프로젝트 업데이트 확인"""
        pid = project_dao.insert_project({
            "title": "업데이트 테스트 공고",
            "agency": "DIP",
        })

        success = project_dao.update_project(pid, {
            "suitability_score": 85,
            "target_entity": "STLABS",
            "status": "READ",
        })
        assert success is True

        project = project_dao.get_project(pid)
        assert project["suitability_score"] == 85
        assert project["target_entity"] == "STLABS"
        assert project["status"] == "READ"

    def test_get_all_projects_filter_entity(self, project_dao):
        """법인별 필터링 조회 확인"""
        project_dao.insert_project({
            "title": "SW 플랫폼 개발 A",
            "agency": "NIPA",
        })
        project_dao.update_project(
            project_dao.generate_id("SW 플랫폼 개발 A", "NIPA", ""),
            {"target_entity": "STLABS"}
        )

        project_dao.insert_project({
            "title": "센서 장치 개발 B",
            "agency": "IITP",
        })
        project_dao.update_project(
            project_dao.generate_id("센서 장치 개발 B", "IITP", ""),
            {"target_entity": "Stratio"}
        )

        stlabs_list = project_dao.get_all_projects(entity="STLABS")
        stratio_list = project_dao.get_all_projects(entity="Stratio")

        assert len(stlabs_list) == 1
        assert len(stratio_list) == 1
        assert stlabs_list[0]["title"] == "SW 플랫폼 개발 A"

    def test_count_projects(self, project_dao):
        """프로젝트 수 카운트 확인"""
        assert project_dao.count_projects() == 0

        project_dao.insert_project({"title": "프로젝트 1", "agency": "A"})
        project_dao.insert_project({"title": "프로젝트 2", "agency": "B"})

        assert project_dao.count_projects() == 2

    def test_is_noise_static_method(self):
        """is_noise 정적 메서드 직접 테스트"""
        assert ProjectDAO.is_noise("AI 교육 참가 안내") is True
        assert ProjectDAO.is_noise("입주기업 모집 공고") is True
        assert ProjectDAO.is_noise("AI 데이터 플랫폼 개발") is False
        assert ProjectDAO.is_noise("기후테크 R&D 지원사업") is False


# ═══════════════════════════════════════════
# ExhibitionDAO 테스트
# ═══════════════════════════════════════════

class TestExhibitionDAO:
    """전시회 DAO 테스트"""

    def test_insert_and_retrieve(self, exhibition_dao):
        """전시회 삽입 및 조회 확인"""
        eid = exhibition_dao.insert_exhibition({
            "name": "2026 스마트팩토리 엑스포",
            "location": "COEX",
            "start_date": "2026-06-15",
            "category": "스마트팩토리, 자동화",
            "url": "https://example.com/expo",
        })
        assert eid is not None

        exhibitions = exhibition_dao.get_all_exhibitions()
        assert len(exhibitions) == 1
        assert exhibitions[0]["name"] == "2026 스마트팩토리 엑스포"
        assert exhibitions[0]["location"] == "COEX"

    def test_duplicate_exhibition(self, exhibition_dao):
        """전시회 중복 방지 확인"""
        data = {
            "name": "중복 전시회",
            "start_date": "2026-09-01",
        }
        eid1 = exhibition_dao.insert_exhibition(data)
        eid2 = exhibition_dao.insert_exhibition(data)

        assert eid1 is not None
        assert eid2 is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
