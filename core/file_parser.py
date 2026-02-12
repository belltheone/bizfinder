# -*- coding: utf-8 -*-
"""
core/file_parser.py - 첨부파일 심층 파서 (Deep File Parser)
=============================================================
본 시스템의 기술적 핵심 모듈입니다.
HWP(OLE), HWPX(XML), PDF 파일에서 텍스트를 추출합니다.

웹상의 텍스트는 요약본일 뿐이므로, 반드시 원본 파일을 분석하여
'숨겨진 제한사항'을 찾아내는 것이 이 모듈의 존재 이유입니다.

지원 포맷:
    - HWP  : Legacy 한글 문서 (OLE 컨테이너 구조)
    - HWPX : 신규 한글 문서 (OOXML 기반, ZIP 압축)
    - PDF  : 범용 문서 포맷 (pdfplumber 사용)

사용 예시:
    >>> from core.file_parser import FileParser
    >>> parser = FileParser()
    >>> text = parser.parse("공고문.hwp")
    >>> print(text[:200])
"""

import os
import re
import zlib
import struct
import zipfile
import logging
from typing import Optional
import xml.etree.ElementTree as ET

import olefile
import pdfplumber

# ── 로거 설정 ──
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 콘솔 핸들러가 아직 없는 경우에만 추가 (중복 방지)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
    ))
    logger.addHandler(_handler)


class FileParser:
    """
    첨부파일 심층 파서 클래스
    =========================
    파일 확장자를 자동으로 판별하여 적절한 파서를 호출하고,
    추출된 텍스트를 반환합니다.

    Attributes:
        supported_extensions (list): 지원하는 파일 확장자 목록
    """

    # 지원하는 파일 확장자
    SUPPORTED_EXTENSIONS = {".hwp", ".hwpx", ".pdf"}

    def __init__(self):
        """FileParser 초기화"""
        logger.info("FileParser 인스턴스가 생성되었습니다.")

    def parse(self, file_path: str) -> str:
        """
        파일 경로를 받아 확장자에 따라 적절한 파서를 호출합니다.

        Args:
            file_path (str): 파싱할 파일의 절대 또는 상대 경로

        Returns:
            str: 추출된 텍스트. 실패 시 에러 메시지가 포함된 문자열 반환.

        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
            ValueError: 지원하지 않는 파일 확장자인 경우
        """
        # 파일 존재 여부 확인
        if not os.path.exists(file_path):
            error_msg = f"파일을 찾을 수 없습니다: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # 확장자 추출 및 소문자로 변환
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        # 지원 여부 확인
        if ext not in self.SUPPORTED_EXTENSIONS:
            error_msg = f"지원하지 않는 파일 형식입니다: {ext} (지원: {', '.join(self.SUPPORTED_EXTENSIONS)})"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"파일 파싱 시작: {file_path} (형식: {ext})")

        # 확장자에 따라 적절한 파서 호출
        try:
            if ext == ".hwp":
                text = self._parse_hwp(file_path)
            elif ext == ".hwpx":
                text = self._parse_hwpx(file_path)
            elif ext == ".pdf":
                text = self._parse_pdf(file_path)
            else:
                text = ""
        except Exception as e:
            error_msg = f"파일 파싱 중 오류 발생 ({ext}): {e}"
            logger.exception(error_msg)
            return f"[파싱 오류] {error_msg}"

        # 결과 정리: 연속 공백/줄바꿈 제거
        text = self._clean_text(text)

        logger.info(f"파싱 완료: {len(text)}자 추출됨")
        return text

    # ═══════════════════════════════════════════════════════════
    # HWP (Legacy) 파서 - OLE 컨테이너 구조 분석
    # ═══════════════════════════════════════════════════════════

    def _parse_hwp(self, file_path: str) -> str:
        """
        HWP 파일에서 텍스트를 추출합니다.

        HWP는 Microsoft의 OLE(Object Linking and Embedding) 구조를 기반으로 합니다.
        내부에 BodyText/Section0, Section1, ... 형태의 스트림이 있으며,
        각 스트림은 zlib으로 압축된 바이너리 레코드들로 구성되어 있습니다.

        처리 과정:
        1. olefile로 OLE 컨테이너 열기
        2. 파일 헤더에서 압축 플래그 확인
        3. BodyText/Section* 스트림을 순차적으로 읽기
        4. 압축이 되어있다면 zlib 해제
        5. 바이너리 레코드를 파싱하여 HWPTAG_PARA_TEXT (TagID=67) 추출
        6. UTF-16LE 디코딩 및 제어 문자 필터링

        Args:
            file_path (str): HWP 파일 경로

        Returns:
            str: 추출된 텍스트
        """
        # OLE 파일 열기
        if not olefile.isOleFile(file_path):
            logger.warning(f"유효하지 않은 OLE 파일입니다: {file_path}")
            return "[파싱 오류] 유효하지 않은 HWP 파일입니다."

        ole = olefile.OleFileIO(file_path)
        extracted_texts = []

        try:
            # ── 1단계: 파일 헤더에서 압축 여부 확인 ──
            # FileHeader 스트림의 37번째 바이트(0-indexed 36) 확인
            is_compressed = False
            if ole.exists("FileHeader"):
                header_data = ole.openstream("FileHeader").read()
                if len(header_data) > 36:
                    # 비트 0이 1이면 압축됨
                    is_compressed = (header_data[36] & 0x01) != 0
                    logger.debug(f"HWP 압축 여부: {is_compressed}")

            # ── 2단계: BodyText 섹션 스트림 찾기 ──
            # BodyText/Section0, Section1, ... 순서로 읽기
            section_streams = []
            for stream_path in ole.listdir():
                # stream_path는 리스트 형태 (예: ['BodyText', 'Section0'])
                joined = "/".join(stream_path)
                if joined.startswith("BodyText/Section"):
                    section_streams.append(stream_path)

            # 섹션 번호순 정렬
            section_streams.sort(key=lambda x: int(
                re.search(r'(\d+)$', x[-1]).group(1)
                if re.search(r'(\d+)$', x[-1]) else 0
            ))

            if not section_streams:
                logger.warning("BodyText 섹션을 찾을 수 없습니다.")
                return "[파싱 오류] HWP 파일에 BodyText가 없습니다."

            # ── 3단계: 각 섹션에서 텍스트 추출 ──
            for stream_path in section_streams:
                raw_data = ole.openstream(stream_path).read()

                # 압축 해제 (필요한 경우)
                if is_compressed:
                    try:
                        raw_data = zlib.decompress(raw_data, -15)
                    except zlib.error as e:
                        logger.warning(
                            f"섹션 {'/'.join(stream_path)} 압축 해제 실패: {e}"
                        )
                        continue

                # 바이너리 레코드에서 텍스트 추출
                section_text = self._extract_text_from_hwp_records(raw_data)
                if section_text:
                    extracted_texts.append(section_text)

        finally:
            ole.close()

        return "\n".join(extracted_texts)

    def _extract_text_from_hwp_records(self, data: bytes) -> str:
        """
        HWP 바이너리 레코드 스트림에서 텍스트를 추출합니다.

        HWP 레코드 구조:
        - 헤더 (4바이트): TagID(10비트) | Level(10비트) | Size(12비트)
        - Size가 0xFFF(4095)인 경우: 추가 4바이트가 실제 크기를 나타냄
        - HWPTAG_PARA_TEXT의 TagID = 67 (HWPTAG_BEGIN + 51, HWPTAG_BEGIN = 16)

        텍스트 데이터는 UTF-16LE로 인코딩되어 있으며,
        0x0000~0x001F 범위의 제어 문자가 포함될 수 있습니다.

        Args:
            data (bytes): 압축 해제된 BodyText 섹션 바이너리 데이터

        Returns:
            str: 추출된 텍스트
        """
        texts = []
        offset = 0
        data_len = len(data)

        while offset < data_len:
            # 최소 4바이트(레코드 헤더)가 필요
            if offset + 4 > data_len:
                break

            # 레코드 헤더 읽기 (4바이트, little-endian unsigned int)
            header = struct.unpack_from("<I", data, offset)[0]
            offset += 4

            # 헤더에서 TagID, Level, Size 분리
            tag_id = header & 0x3FF           # 하위 10비트: TagID
            # level = (header >> 10) & 0x3FF  # 중간 10비트: Level (사용하지 않음)
            size = (header >> 20) & 0xFFF     # 상위 12비트: Size

            # Size가 0xFFF이면 추가 4바이트에서 실제 크기 읽기
            if size == 0xFFF:
                if offset + 4 > data_len:
                    break
                size = struct.unpack_from("<I", data, offset)[0]
                offset += 4

            # 데이터 범위 확인
            if offset + size > data_len:
                break

            # HWPTAG_PARA_TEXT (TagID = 67) 처리
            # HWPTAG_BEGIN = 16, HWPTAG_PARA_TEXT = HWPTAG_BEGIN + 51 = 67
            if tag_id == 67:
                text_data = data[offset:offset + size]
                text = self._decode_hwp_text(text_data)
                if text.strip():
                    texts.append(text)

            # 다음 레코드로 이동
            offset += size

        return "\n".join(texts)

    @staticmethod
    def _decode_hwp_text(data: bytes) -> str:
        """
        HWP 텍스트 데이터를 UTF-16LE로 디코딩하고 제어 문자를 처리합니다.

        HWP의 텍스트 레코드에는 다양한 제어 문자가 포함됩니다:
        - 0x0000~0x0002: 사용하지 않는 특수 문자
        - 0x0003: 필드 시작 (24바이트 확장)
        - 0x000D: 단락 끝 → 줄바꿈으로 변환
        - 기타 제어 문자: 무시

        Args:
            data (bytes): UTF-16LE 인코딩된 텍스트 바이너리

        Returns:
            str: 디코딩 및 정제된 텍스트
        """
        result = []
        i = 0

        while i < len(data) - 1:
            # 2바이트씩 UTF-16LE 코드 포인트 읽기
            code = struct.unpack_from("<H", data, i)[0]

            if code == 0x000D:
                # 단락 끝 → 줄바꿈
                result.append("\n")
                i += 2
            elif code <= 0x001F:
                # 제어 문자 처리
                if code in (0x0003, 0x0011, 0x0012, 0x0013,
                            0x0014, 0x0015, 0x0016, 0x0017, 0x0018):
                    # 확장 제어 문자: 추가 바이트 건너뛰기
                    # 이 제어 문자들은 뒤에 추가 데이터(보통 12~14 word)가 붙음
                    i += 2  # 기본 2바이트만 건너뛰기 (나머지는 이미 레코드 크기에 포함)
                else:
                    # 일반 제어 문자: 무시
                    i += 2
            else:
                # 일반 문자: UTF-16LE 디코딩
                try:
                    char = chr(code)
                    result.append(char)
                except (ValueError, OverflowError):
                    pass
                i += 2

        return "".join(result)

    # ═══════════════════════════════════════════════════════════
    # HWPX (XML 기반) 파서 - ZIP 압축 해제 + XML 파싱
    # ═══════════════════════════════════════════════════════════

    def _parse_hwpx(self, file_path: str) -> str:
        """
        HWPX 파일에서 텍스트를 추출합니다.

        HWPX는 OOXML 기반으로 ZIP 압축된 포맷입니다.
        내부 구조:
        - Contents/section0.xml, section1.xml, ...
        - 각 XML 파일은 hp: 네임스페이스를 사용
        - 텍스트는 <hp:t> 태그 안에 포함

        처리 과정:
        1. zipfile로 HWPX 압축 해제
        2. Contents/section*.xml 파일 목록 확보
        3. XML 파싱하여 <hp:t> 태그 내부 텍스트 추출

        Args:
            file_path (str): HWPX 파일 경로

        Returns:
            str: 추출된 텍스트
        """
        extracted_texts = []

        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # ZIP 내부 파일 목록 확인
                file_list = zf.namelist()
                logger.debug(f"HWPX 내부 파일: {file_list}")

                # Contents/section*.xml 파일 찾기
                section_files = sorted([
                    f for f in file_list
                    if re.match(r'Contents/section\d+\.xml', f, re.IGNORECASE)
                ])

                if not section_files:
                    # 대체 경로 탐색: Contents/ 아래의 모든 XML
                    section_files = sorted([
                        f for f in file_list
                        if f.startswith("Contents/") and f.endswith(".xml")
                    ])

                if not section_files:
                    logger.warning("HWPX 파일에서 section XML을 찾을 수 없습니다.")
                    return "[파싱 오류] HWPX 파일에 본문 섹션이 없습니다."

                # 각 섹션 XML에서 텍스트 추출
                for section_file in section_files:
                    xml_data = zf.read(section_file)
                    section_text = self._extract_text_from_hwpx_xml(xml_data)
                    if section_text:
                        extracted_texts.append(section_text)

        except zipfile.BadZipFile:
            logger.error(f"유효하지 않은 ZIP(HWPX) 파일: {file_path}")
            return "[파싱 오류] 유효하지 않은 HWPX 파일입니다."

        return "\n".join(extracted_texts)

    @staticmethod
    def _extract_text_from_hwpx_xml(xml_data: bytes) -> str:
        """
        HWPX 섹션 XML에서 텍스트를 추출합니다.

        HWPX의 XML 네임스페이스:
        - hp: http://www.hancom.co.kr/hwpml/2011/paragraph
        - 또는 버전에 따라 다른 네임스페이스 사용 가능

        <hp:t> 태그 내부의 텍스트를 모두 수집합니다.

        Args:
            xml_data (bytes): 섹션 XML 바이너리 데이터

        Returns:
            str: 추출된 텍스트
        """
        texts = []

        try:
            root = ET.fromstring(xml_data)

            # 방법 1: 네임스페이스를 명시적으로 지정하여 검색
            # HWPX에서 사용하는 알려진 네임스페이스 목록
            known_namespaces = [
                "http://www.hancom.co.kr/hwpml/2011/paragraph",
                "http://www.hancom.co.kr/hwpml/2016/paragraph",
                "urn:hancom:hwpml:paragraph",
            ]

            found = False
            for ns_uri in known_namespaces:
                ns = {"hp": ns_uri}
                elements = root.findall(".//hp:t", ns)
                if elements:
                    for elem in elements:
                        if elem.text:
                            texts.append(elem.text)
                    found = True
                    break

            # 방법 2: 네임스페이스 무시하고 로컬 이름으로 검색 (fallback)
            if not found:
                for elem in root.iter():
                    # 로컬 이름이 't'인 요소에서 텍스트 추출
                    local_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if local_name == "t" and elem.text:
                        texts.append(elem.text)

        except ET.ParseError as e:
            logger.error(f"HWPX XML 파싱 오류: {e}")
            return ""

        return "\n".join(texts)

    # ═══════════════════════════════════════════════════════════
    # PDF 파서 - pdfplumber 사용
    # ═══════════════════════════════════════════════════════════

    def _parse_pdf(self, file_path: str) -> str:
        """
        PDF 파일에서 텍스트를 추출합니다.

        pdfplumber를 사용하여 페이지 단위로 텍스트를 추출합니다.
        만약 텍스트 추출 결과가 비어있다면 (이미지 스캔본),
        '[수동 확인 필요]' 태그를 부착합니다.

        Args:
            file_path (str): PDF 파일 경로

        Returns:
            str: 추출된 텍스트. 이미지 기반 PDF인 경우 경고 메시지 포함.
        """
        extracted_texts = []

        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"PDF 페이지 수: {total_pages}")

                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        extracted_texts.append(page_text)
                    else:
                        logger.debug(f"PDF {i+1}페이지: 텍스트 없음 (이미지일 수 있음)")

        except Exception as e:
            logger.error(f"PDF 파싱 오류: {e}")
            return f"[파싱 오류] PDF 파일을 열 수 없습니다: {e}"

        if not extracted_texts:
            # 모든 페이지에서 텍스트를 추출하지 못한 경우
            # → 이미지 스캔본으로 판단
            logger.warning("PDF에서 텍스트를 추출할 수 없습니다 (이미지 스캔본 가능성)")
            return "[수동 확인 필요] 이 PDF는 이미지 기반 문서입니다. 텍스트를 추출할 수 없습니다."

        return "\n".join(extracted_texts)

    # ═══════════════════════════════════════════════════════════
    # 유틸리티 메서드
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        추출된 텍스트를 정리합니다.

        - 연속된 빈 줄을 하나로 축소
        - 줄 양쪽 공백 제거
        - 앞뒤 공백 제거

        Args:
            text (str): 정리할 텍스트

        Returns:
            str: 정리된 텍스트
        """
        if not text:
            return ""

        # 연속된 빈 줄을 하나로 축소
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 각 줄의 양쪽 공백 제거
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        # 전체 앞뒤 공백 제거
        return text.strip()

    @staticmethod
    def get_file_info(file_path: str) -> dict:
        """
        파일의 기본 정보를 반환합니다.

        Args:
            file_path (str): 파일 경로

        Returns:
            dict: 파일 정보 (이름, 확장자, 크기, 존재 여부)
        """
        exists = os.path.exists(file_path)
        _, ext = os.path.splitext(file_path)

        return {
            "file_name": os.path.basename(file_path),
            "extension": ext.lower(),
            "size_bytes": os.path.getsize(file_path) if exists else 0,
            "exists": exists,
            "supported": ext.lower() in FileParser.SUPPORTED_EXTENSIONS,
        }


# ── 모듈 직접 실행 시 간단한 테스트 ──
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python file_parser.py <파일 경로>")
        print(f"지원 형식: {', '.join(FileParser.SUPPORTED_EXTENSIONS)}")
        sys.exit(1)

    parser = FileParser()
    target_file = sys.argv[1]

    # 파일 정보 출력
    info = parser.get_file_info(target_file)
    print(f"\n{'='*60}")
    print(f"파일명:   {info['file_name']}")
    print(f"확장자:   {info['extension']}")
    print(f"크기:     {info['size_bytes']:,} bytes")
    print(f"지원여부: {'✅ 지원' if info['supported'] else '❌ 미지원'}")
    print(f"{'='*60}\n")

    # 파싱 실행
    result = parser.parse(target_file)
    print(result[:2000])  # 처음 2000자만 출력
    print(f"\n... (총 {len(result)}자)")
