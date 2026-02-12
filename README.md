# 🌐 Biz-Intelligence System 배포 가이드

이 프로젝트는 **Streamlit Community Cloud**에 최적화되어 있습니다.
데이터베이스로 **SQLite**를 사용하지만, 배포 환경의 특성(서버리스)상 데이터가 영구 보존되지 않을 수 있습니다.

---

## 🚀 1. 빠른 배포 (데이터 초기화 가능)
**테스트 목적**이나 **데모 시연용**으로 가장 빠르게 배포하는 방법입니다.

### 1단계: GitHub 저장소 업로드
1.  이 프로젝트 폴더 전체를 GitHub의 **Private Repository**에 업로드합니다.
2.  `projects.db` 파일이 `.gitignore`에 포함되어 있다면 제거하거나 강제로 포함시킵니다. (데이터 유지가 필요한 경우)
    *   *Tip:* `git add -f projects.db` (로컬 데이터 포함)

### 2단계: Streamlit Cloud 연결
1.  [Streamlit Cloud](https://streamlit.io/cloud)에 접속 및 로그인.
2.  **New app** 클릭.
3.  **Repository**: 방금 업로드한 저장소 선택.
4.  **Main file path**: `app.py` 입력.
5.  **Deploy!** 클릭.

### 3단계: API 키 설정 (필수!)
최초 배포 시 에러가 날 수 있습니다. **Secrets** 설정이 필요합니다.
1.  배포된 앱 우측 하단의 **Manage app** 클릭.
2.  **Settings** (점 3개 아이콘) -> **Secrets** 메뉴로 이동.
3.  다음 내용을 복사하여 붙여넣고 저장합니다.
    ```toml
    OPENAI_API_KEY = "sk-..."
    OPENAI_MODEL = "gpt-4o-mini"
    ```

---

## 🔒 2. 데이터 영구 보존 (권장)
배포 후 분석한 데이터가 사라지지 않게 하려면 **외부 DB**를 연결해야 합니다.

### 방법 A: Supabase (가장 추천)
1.  [Supabase](https://supabase.com) 가입 및 새 프로젝트 생성.
2.  **Project Settings -> Database**에서 `Connection String (URI)` 복사.
3.  Streamlit Cloud의 **Secrets**에 추가:
    ```toml
    # .streamlit/secrets.toml
    [connections.supabase]
    dialect = "postgresql"
    host = "aws-0-ap-northeast-2..."
    port = "5432"
    database = "postgres"
    username = "postgres"
    password = "your-password"
    ```
4.  `dao.py` 코드 수정 필요 (SQLite -> st.connection).

### 방법 B: Google Sheets (가장 쉬움)
1.  구글 시트 생성 및 API 연동.
2.  `st.connection("gsheets", type=GSheetsConnection)` 사용.

---

## 📦 필수 파일 확인
배포 전 다음 파일들이 루트 경로에 있는지 확인하세요.
1.  `app.py`: 메인 실행 파일
2.  `requirements.txt`: 필수 패키지 목록 (`openai`, `streamlit`, `hwpx` 등)
## 💻 3. 터미널 수동 배포 (Git 설치 필요)
이 환경에서 Git 명령어가 실행되지 않는 경우, 다음 명령어를 터미널(`cmd` 또는 `PowerShell`)에 직접 복사 -> 붙여넣기 하세요.

```bash
# 1. 초기 설정
git init
git remote remove origin
git remote add origin https://github.com/belltheone/bizfinder.git

# 2. 커밋 및 푸시
git add .
git commit -m "초기 배포: Streamlit AI 분석 시스템 v1.0"
git push -u origin main
```
