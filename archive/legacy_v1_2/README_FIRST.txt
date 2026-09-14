SUNO 15SET MASTERING FINAL v1.2 - WINDOWS FIX
=================================================

이번 버전은 Windows CMD에서 한글/UTF-8 배치파일이 깨지는 문제를 피하기 위해
설치/실행 배치파일의 파일명과 내부 명령을 전부 영문 ASCII로 변경했습니다.

가장 쉬운 사용법
----------------
1. ZIP 압축을 완전히 풉니다.
2. 폴더 안의 START_HERE.bat 를 더블클릭합니다.
3. Python이 이미 설치되어 있으면 자동으로 필요한 환경을 만듭니다.
4. Python이 없으면 winget으로 Python 3.12 설치를 시도합니다.
5. Python을 새로 설치했다면 창을 닫고 START_HERE.bat 를 한 번 더 실행합니다.
6. 이후에는 START_HERE.bat 또는 RUN.bat 만 사용하면 됩니다.

중요
----
- ZIP 안에서 직접 실행하지 말고 반드시 압축을 푼 뒤 실행하세요.
- 예전 v1.1의 설치 BAT 파일은 사용하지 마세요.
- 가능하면 C:\SUNO_MASTER 같이 짧은 영문 폴더에 압축을 풀어 사용하면 가장 안전합니다.

파일 설명
---------
START_HERE.bat : 처음 설치/이후 실행을 자동 판단. 평소 이 파일만 사용.
INSTALL.bat    : 설치만 다시 할 때 사용.
RUN.bat        : 설치 완료 후 프로그램 실행.
RESET_INSTALL.bat : 설치가 꼬였을 때 .venv만 삭제. 음악/MASTER 결과는 삭제하지 않음.

오류가 계속되면
---------------
START_HERE.bat 실행 화면 전체를 캡처해서 보내주세요.
