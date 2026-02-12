import os
import subprocess
import sys

# Git 절대 경로 (자동 탐색)
GIT_PATH = r"C:\Program Files\Git\cmd\git.exe"
if not os.path.exists(GIT_PATH):
    GIT_PATH = "git"  # 없으면 PATH 사용

def run_git(command):
    # 'git' 명령어를 절대 경로로 치환
    if command.startswith("git "):
        command = f'"{GIT_PATH}" {command[4:]}'
        
    print(f"Executing: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print(f"Output: {result.stdout}")
    return True

def main():
    # 1. Git 설치 확인
    if not run_git("git --version"):
        print("Git is not installed or not in PATH.")
        sys.exit(1)

    # 2. 초기화 및 설정
    run_git("git init")
    run_git('git config user.email "bizfinder@bot.com"')
    run_git('git config user.name "BizFinder Bot"')

    # 3. 원격 저장소 연결 (add 실패 시 set-url 시도)
    if not run_git("git remote add origin https://github.com/belltheone/bizfinder.git"):
        print("Remote add failed, trying set-url...")
        run_git("git remote set-url origin https://github.com/belltheone/bizfinder.git")

    # 4. 파일 추가
    if not run_git("git add ."):
        sys.exit(1)

    # 5. 커밋
    run_git('git commit -m "Deploy: Streamlit App v1.0"')

    # 6. 푸시
    if run_git("git push -u origin main"):
        print("[SUCCESS] Deploy completed!")
    else:
        print("[FAIL] Push failed. Check your internet or repo permission.")

if __name__ == "__main__":
    main()
