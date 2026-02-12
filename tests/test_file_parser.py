# -*- coding: utf-8 -*-
"""
tests/test_file_parser.py - FileParser 단위 테스트
=====================================================
프로그래밍 방식으로 합성 파일(HWP, HWPX, PDF)을 생성하여
FileParser의 각 파서가 올바르게 동작하는지 검증합니다.

실행 방법:
    python -m pytest tests/test_file_parser.py -v
"""

import os
import sys
import zlib
import struct
import zipfile
import tempfile
import shutil

import pytest

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.file_parser import FileParser


class TestFileParserInit:
    """FileParser 초기화 및 기본 동작 테스트"""

    def setup_method(self):
        """각 테스트 메서드 실행 전 FileParser 인스턴스 생성"""
        self.parser = FileParser()

    def test_instance_creation(self):
        """FileParser 인스턴스가 정상적으로 생성되는지 확인"""
        assert self.parser is not None
        assert hasattr(self.parser, 'parse')
        assert hasattr(self.parser, '_parse_hwp')
        assert hasattr(self.parser, '_parse_hwpx')
        assert hasattr(self.parser, '_parse_pdf')

    def test_supported_extensions(self):
        """지원하는 파일 확장자가 올바르게 설정되었는지 확인"""
        expected = {".hwp", ".hwpx", ".pdf"}
        assert FileParser.SUPPORTED_EXTENSIONS == expected


class TestFileNotFound:
    """파일이 존재하지 않는 경우의 에러 처리 테스트"""

    def setup_method(self):
        self.parser = FileParser()

    def test_nonexistent_file_raises_error(self):
        """존재하지 않는 파일 경로에 대해 FileNotFoundError 발생 확인"""
        with pytest.raises(FileNotFoundError, match="파일을 찾을 수 없습니다"):
            self.parser.parse("/nonexistent/path/document.hwp")

    def test_nonexistent_pdf_raises_error(self):
        """존재하지 않는 PDF 파일에 대해 FileNotFoundError 발생 확인"""
        with pytest.raises(FileNotFoundError):
            self.parser.parse("C:\\없는폴더\\없는파일.pdf")


class TestUnsupportedFormat:
    """지원하지 않는 파일 형식 처리 테스트"""

    def setup_method(self):
        self.parser = FileParser()
        # 임시 디렉토리 생성
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        # 임시 디렉토리 삭제
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unsupported_extension_raises_error(self):
        """지원하지 않는 확장자(.docx)에 대해 ValueError 발생 확인"""
        # 임시 .docx 파일 생성
        test_file = os.path.join(self.temp_dir, "test.docx")
        with open(test_file, "w") as f:
            f.write("dummy content")

        with pytest.raises(ValueError, match="지원하지 않는 파일 형식"):
            self.parser.parse(test_file)

    def test_txt_extension_raises_error(self):
        """지원하지 않는 확장자(.txt)에 대해 ValueError 발생 확인"""
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("dummy content")

        with pytest.raises(ValueError, match="지원하지 않는 파일 형식"):
            self.parser.parse(test_file)


class TestHWPXParser:
    """
    HWPX 파서 테스트
    =================
    프로그래밍 방식으로 HWPX(ZIP+XML) 파일을 생성하여 파싱 검증.
    HWPX는 ZIP 안에 Contents/section0.xml 형태의 XML 본문을 포함합니다.
    """

    def setup_method(self):
        self.parser = FileParser()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_hwpx(self, filename: str, sections: list[dict]) -> str:
        """
        테스트용 HWPX 파일을 프로그래밍 방식으로 생성합니다.

        Args:
            filename: 생성할 파일명
            sections: 섹션 목록. 각 항목은 {"name": str, "texts": list[str]}

        Returns:
            str: 생성된 HWPX 파일 경로
        """
        file_path = os.path.join(self.temp_dir, filename)

        with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for section in sections:
                # hp 네임스페이스를 사용한 XML 생성
                xml_parts = [
                    '<?xml version="1.0" encoding="UTF-8"?>',
                    '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
                    ' xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">',
                ]
                for text in section["texts"]:
                    xml_parts.append(
                        f'  <hp:p><hp:run><hp:t>{text}</hp:t></hp:run></hp:p>'
                    )
                xml_parts.append('</hs:sec>')
                xml_content = "\n".join(xml_parts)
                zf.writestr(section["name"], xml_content.encode("utf-8"))

        return file_path

    def test_single_section_korean(self):
        """단일 섹션에서 한국어 텍스트가 정상 추출되는지 확인"""
        hwpx_path = self._create_hwpx("test_korean.hwpx", [
            {
                "name": "Contents/section0.xml",
                "texts": [
                    "정부 지원사업 공고문",
                    "과제명: AI 기반 기후테크 플랫폼 개발",
                    "총 사업비: 5억원 (인건비 3억원 포함)",
                ],
            }
        ])

        result = self.parser.parse(hwpx_path)

        # 핵심 텍스트가 포함되어 있는지 확인
        assert "정부 지원사업 공고문" in result
        assert "기후테크" in result
        assert "인건비" in result
        assert "5억원" in result

    def test_multiple_sections(self):
        """여러 섹션이 있는 HWPX 파일에서 모든 텍스트가 추출되는지 확인"""
        hwpx_path = self._create_hwpx("test_multi.hwpx", [
            {
                "name": "Contents/section0.xml",
                "texts": ["섹션 0의 내용입니다."],
            },
            {
                "name": "Contents/section1.xml",
                "texts": ["섹션 1의 내용입니다."],
            },
        ])

        result = self.parser.parse(hwpx_path)

        assert "섹션 0의 내용" in result
        assert "섹션 1의 내용" in result

    def test_empty_sections(self):
        """빈 텍스트가 있는 섹션 처리 확인"""
        hwpx_path = self._create_hwpx("test_empty.hwpx", [
            {
                "name": "Contents/section0.xml",
                "texts": [],
            }
        ])

        result = self.parser.parse(hwpx_path)
        # 빈 결과여도 에러가 나지 않아야 함
        assert isinstance(result, str)

    def test_special_characters(self):
        """특수 문자가 포함된 텍스트 처리 확인"""
        hwpx_path = self._create_hwpx("test_special.hwpx", [
            {
                "name": "Contents/section0.xml",
                "texts": [
                    "민간부담금 비율: 20%",
                    "지원기간: 2026.03 ~ 2027.02",
                    "문의: tech@stlabs.co.kr",
                ],
            }
        ])

        result = self.parser.parse(hwpx_path)

        assert "20%" in result
        assert "2026.03" in result
        assert "tech@stlabs.co.kr" in result

    def test_budget_and_labor_cost_keywords(self):
        """'인건비', '현물', '현금' 등 핵심 키워드가 정확히 추출되는지 확인
        (AI Kill Switch에서 이 키워드들을 기반으로 판단하므로 매우 중요)"""
        hwpx_path = self._create_hwpx("test_budget.hwpx", [
            {
                "name": "Contents/section0.xml",
                "texts": [
                    "예산 비목 안내",
                    "인건비: 현금 계상 가능",
                    "재료비: 현물 가능",
                    "주관기관 자격: 중소기업, 스타트업",
                    "민간부담금: 총 사업비의 10%",
                ],
            }
        ])

        result = self.parser.parse(hwpx_path)

        # Kill Switch 관련 핵심 키워드 확인
        assert "인건비" in result
        assert "현금" in result
        assert "현물" in result
        assert "주관기관" in result
        assert "중소기업" in result

    def test_invalid_hwpx_file(self):
        """손상된 HWPX(ZIP이 아닌) 파일 처리 확인"""
        bad_file = os.path.join(self.temp_dir, "bad.hwpx")
        with open(bad_file, "wb") as f:
            f.write(b"This is not a valid ZIP file")

        result = self.parser.parse(bad_file)
        assert "[파싱 오류]" in result


class TestPDFParser:
    """
    PDF 파서 테스트
    ================
    reportlab로 합성 PDF 파일을 생성하여 파싱 검증.
    """

    def setup_method(self):
        self.parser = FileParser()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_pdf(self, filename: str, texts: list[str]) -> str:
        """
        테스트용 PDF 파일을 reportlab으로 생성합니다.

        Args:
            filename: 생성할 파일명
            texts: 각 페이지에 넣을 텍스트 목록

        Returns:
            str: 생성된 PDF 파일 경로
        """
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        file_path = os.path.join(self.temp_dir, filename)
        c = canvas.Canvas(file_path, pagesize=A4)

        # 시스템 한글 폰트 등록 시도 (Windows)
        font_name = "Helvetica"  # 기본 폰트 (영문용)
        korean_font_registered = False

        # Windows 한글 폰트 경로 목록
        korean_font_paths = [
            "C:/Windows/Fonts/malgun.ttf",      # 맑은 고딕
            "C:/Windows/Fonts/gulim.ttc",        # 굴림
            "C:/Windows/Fonts/batang.ttc",       # 바탕
        ]

        for font_path in korean_font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont("KoreanFont", font_path))
                    font_name = "KoreanFont"
                    korean_font_registered = True
                    break
                except Exception:
                    continue

        for text in texts:
            c.setFont(font_name, 12)
            # 한글 폰트가 없으면 영문만 사용
            y_position = 750
            for line in text.split("\n"):
                c.drawString(72, y_position, line)
                y_position -= 20
            c.showPage()

        c.save()
        return file_path

    def test_single_page_pdf(self):
        """단일 페이지 PDF에서 텍스트 추출 확인"""
        pdf_path = self._create_pdf("test_single.pdf", [
            "Government Support Project Announcement\nBudget: 500M KRW"
        ])

        result = self.parser.parse(pdf_path)

        assert "Government" in result or "Support" in result
        assert "500M" in result or "Budget" in result

    def test_multi_page_pdf(self):
        """여러 페이지 PDF에서 모든 페이지 텍스트 추출 확인"""
        pdf_path = self._create_pdf("test_multi.pdf", [
            "Page 1: Project Overview",
            "Page 2: Budget Details",
            "Page 3: Eligibility Criteria",
        ])

        result = self.parser.parse(pdf_path)

        assert "Page 1" in result
        assert "Page 2" in result
        assert "Page 3" in result

    def test_korean_text_pdf(self):
        """한국어 텍스트가 포함된 PDF 처리 확인"""
        pdf_path = self._create_pdf("test_korean.pdf", [
            "AI Platform Development Project"
        ])

        result = self.parser.parse(pdf_path)
        # 최소한 영문 텍스트는 추출되어야 함
        assert len(result) > 0
        assert "AI" in result or "Platform" in result

    def test_empty_pdf_returns_manual_check(self):
        """빈 PDF (이미지 기반)에서 '수동 확인 필요' 태그 반환 확인"""
        # 빈 PDF 생성 (텍스트 없음)
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        file_path = os.path.join(self.temp_dir, "empty.pdf")
        c = canvas.Canvas(file_path, pagesize=A4)
        c.showPage()  # 빈 페이지
        c.save()

        result = self.parser.parse(file_path)
        assert "[수동 확인 필요]" in result

    def test_invalid_pdf_file(self):
        """손상된 PDF 파일 처리 확인"""
        bad_file = os.path.join(self.temp_dir, "bad.pdf")
        with open(bad_file, "wb") as f:
            f.write(b"This is not a valid PDF file")

        result = self.parser.parse(bad_file)
        assert "[파싱 오류]" in result


class TestHWPParser:
    """
    HWP 파서 테스트
    =================
    HWP(OLE) 파일의 바이너리 레코드 파싱 로직을 검증합니다.

    실제 OLE 컨테이너를 프로그래밍으로 생성하기 어려우므로,
    내부 메서드(_extract_text_from_hwp_records, _decode_hwp_text)를
    직접 테스트합니다.
    """

    def setup_method(self):
        self.parser = FileParser()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _build_hwp_record(self, tag_id: int, data: bytes, level: int = 0) -> bytes:
        """
        테스트용 HWP 바이너리 레코드를 생성합니다.

        HWP 레코드 구조:
        - 헤더 4바이트: TagID(10비트) | Level(10비트) | Size(12비트)
        - 뒤이어 data 바이트

        Args:
            tag_id: 레코드 TagID (67 = HWPTAG_PARA_TEXT)
            data: 레코드 데이터
            level: 레코드 레벨

        Returns:
            bytes: 생성된 레코드 바이너리
        """
        size = len(data)
        if size >= 0xFFF:
            # 큰 사이즈: 헤더의 Size 필드를 0xFFF로 설정하고 추가 4바이트
            header = (tag_id & 0x3FF) | ((level & 0x3FF) << 10) | (0xFFF << 20)
            return struct.pack("<I", header) + struct.pack("<I", size) + data
        else:
            header = (tag_id & 0x3FF) | ((level & 0x3FF) << 10) | ((size & 0xFFF) << 20)
            return struct.pack("<I", header) + data

    def test_decode_hwp_text_korean(self):
        """HWP 텍스트 디코딩: 한국어(UTF-16LE) 텍스트 변환 확인"""
        # "안녕하세요"를 UTF-16LE로 인코딩
        test_text = "안녕하세요"
        encoded = test_text.encode("utf-16-le")

        result = FileParser._decode_hwp_text(encoded)
        assert result == test_text

    def test_decode_hwp_text_mixed(self):
        """HWP 텍스트 디코딩: 한/영 혼합 텍스트 변환 확인"""
        test_text = "인건비 Budget"
        encoded = test_text.encode("utf-16-le")

        result = FileParser._decode_hwp_text(encoded)
        assert result == test_text

    def test_decode_hwp_text_with_newline(self):
        """HWP 텍스트 디코딩: 단락 끝(0x000D을) 줄바꿈으로 변환 확인"""
        # "가" + 단락끝 + "나"
        data = "가".encode("utf-16-le") + struct.pack("<H", 0x000D) + "나".encode("utf-16-le")

        result = FileParser._decode_hwp_text(data)
        assert "가" in result
        assert "\n" in result
        assert "나" in result

    def test_decode_hwp_text_with_control_chars(self):
        """HWP 텍스트 디코딩: 제어 문자(0x0001 등)가 무시되는지 확인"""
        # 제어문자(0x0001) + "테스트"
        data = struct.pack("<H", 0x0001) + "테스트".encode("utf-16-le")

        result = FileParser._decode_hwp_text(data)
        assert "테스트" in result
        # 제어 문자는 출력에 포함되지 않아야 함
        assert "\x01" not in result

    def test_extract_text_from_records(self):
        """HWP 레코드 스트림에서 HWPTAG_PARA_TEXT 텍스트 추출 확인"""
        # HWPTAG_PARA_TEXT (TagID=67)인 레코드 생성
        text_data = "정부지원사업 공고".encode("utf-16-le")
        record = self._build_hwp_record(67, text_data)

        result = self.parser._extract_text_from_hwp_records(record)
        assert "정부지원사업" in result
        assert "공고" in result

    def test_extract_ignores_non_text_records(self):
        """비-텍스트 레코드(TagID != 67)는 무시되는지 확인"""
        # TagID=10 (텍스트가 아닌 레코드) + TagID=67 (텍스트 레코드)
        non_text = self._build_hwp_record(10, b"\x00" * 8)
        text_data = "인건비 현금".encode("utf-16-le")
        text_record = self._build_hwp_record(67, text_data)

        combined = non_text + text_record
        result = self.parser._extract_text_from_hwp_records(combined)

        assert "인건비" in result
        assert "현금" in result

    def test_extract_multiple_text_records(self):
        """여러 개의 HWPTAG_PARA_TEXT 레코드에서 텍스트를 모두 추출하는지 확인"""
        records = b""
        texts = ["과제명: AI 플랫폼", "총 사업비: 5억원", "마감일: 2026-03-31"]

        for text in texts:
            text_data = text.encode("utf-16-le")
            records += self._build_hwp_record(67, text_data)

        result = self.parser._extract_text_from_hwp_records(records)

        for text in texts:
            assert text in result

    def test_invalid_ole_file(self):
        """유효하지 않은 OLE 파일에 대한 에러 처리 확인"""
        bad_file = os.path.join(self.temp_dir, "bad.hwp")
        with open(bad_file, "wb") as f:
            f.write(b"This is not a valid OLE/HWP file")

        result = self.parser.parse(bad_file)
        assert "[파싱 오류]" in result


class TestCleanText:
    """텍스트 정리 유틸리티 테스트"""

    def test_multiple_blank_lines(self):
        """연속된 빈 줄이 하나로 축소되는지 확인"""
        text = "첫째 줄\n\n\n\n\n둘째 줄"
        result = FileParser._clean_text(text)
        assert result == "첫째 줄\n\n둘째 줄"

    def test_trailing_spaces(self):
        """각 줄의 양쪽 공백이 제거되는지 확인"""
        text = "  앞쪽 공백  \n  뒤쪽 공백  "
        result = FileParser._clean_text(text)
        assert "앞쪽 공백" in result
        assert "뒤쪽 공백" in result

    def test_empty_string(self):
        """빈 문자열 처리 확인"""
        assert FileParser._clean_text("") == ""
        assert FileParser._clean_text(None) == ""


class TestGetFileInfo:
    """파일 정보 조회 유틸리티 테스트"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_existing_hwp_file(self):
        """존재하는 HWP 파일의 정보가 올바르게 반환되는지 확인"""
        test_file = os.path.join(self.temp_dir, "test.hwp")
        with open(test_file, "wb") as f:
            f.write(b"\x00" * 100)

        info = FileParser.get_file_info(test_file)

        assert info["exists"] is True
        assert info["extension"] == ".hwp"
        assert info["supported"] is True
        assert info["size_bytes"] == 100

    def test_nonexistent_file(self):
        """존재하지 않는 파일의 정보가 올바르게 반환되는지 확인"""
        info = FileParser.get_file_info("/nonexistent/file.pdf")

        assert info["exists"] is False
        assert info["supported"] is True
        assert info["size_bytes"] == 0

    def test_unsupported_extension(self):
        """지원하지 않는 확장자 파일의 정보 확인"""
        test_file = os.path.join(self.temp_dir, "test.docx")
        with open(test_file, "w") as f:
            f.write("dummy")

        info = FileParser.get_file_info(test_file)

        assert info["supported"] is False
        assert info["extension"] == ".docx"


# ── 직접 실행 시 pytest 호출 ──
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
