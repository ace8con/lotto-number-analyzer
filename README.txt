로또 번호 분석 웹사이트 - 배포용

이 프로젝트는 GitHub + Render로 웹사이트를 게시하기 위한 파일입니다.
start.command를 실행하지 않습니다.

게시 순서
1. GitHub 계정을 만들거나 로그인합니다.
2. 새 Repository(저장소)를 만듭니다. 이름 예: lotto-number-analyzer
3. 이 폴더 안의 파일을 저장소에 업로드합니다. app.py, requirements.txt, render.yaml, templates/index.html
4. Render 계정으로 로그인하고 New > Web Service를 선택한 뒤 GitHub 저장소를 연결합니다.
5. render.yaml 설정을 사용하거나 아래처럼 입력합니다.
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app
6. 배포가 완료되면 Render가 제공하는 주소를 Safari에서 엽니다.

참고
- 이 서비스는 동행복권의 공개 당첨번호 API를 서버에서 조회합니다.
- 첫 데이터 조회는 다소 시간이 걸릴 수 있습니다.
- 무료 호스팅의 상태와 서비스 정책은 변경될 수 있습니다.
