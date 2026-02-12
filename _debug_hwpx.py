import os
import sys
from core.file_parser import FileParser

def debug_hwpx_parsing():
    target_file = r"c:\Users\Stratio\Documents\Workspace\exam_file\붙임 1. 2026년 AI+S&T 혁신 기술개발(R&D) 신규과제 공고문.hwpx"
    
    if not os.path.exists(target_file):
        print(f"❌ 파일 없음: {target_file}")
        return

    print(f"파일 파싱 시작: {target_file}")
    parser = FileParser()
    try:
        text = parser.parse(target_file)
        print(f"파싱 성공: {len(text)}자")
        
        # 결과 저장
        output_path = "debug_output.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"결과 저장됨: {output_path}")

        # "과제" 키워드 주변 출력
        print("\n'과제' 키워드 주변 텍스트 (최대 10곳):")
        indices = [i for i in range(len(text)) if text.startswith("과제", i)]
        for i in indices[:10]:
            snippet = text[i:i+100].replace("\n", " ")
            print(f"- ...{snippet}...")

        # 앞부분 출력
        print("\n텍스트 앞부분 (1000자):")
        print(text[:1000])

    except Exception as e:
        print(f"파싱 오류: {e}")

if __name__ == "__main__":
    debug_hwpx_parsing()
