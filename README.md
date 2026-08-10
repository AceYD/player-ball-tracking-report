# 3. 선수·공 이동 데이터 경기 리포트

좌표 데이터만으로는 이해하기 어려운 선수와 공의 움직임을 통계표, 이동경로, 히트맵과 자동 분석 문장으로 변환하는 오프라인 웹 대시보드입니다.

현재 저장소에 포함된 CSV·JSON만 사용하며 외부 API나 운영 데이터에 연결하지 않습니다.

## 구현 기능

- 샘플 CSV·JSON 선택 또는 사용자 파일 업로드
- 필수 열, 숫자 형식, 중복, 결측값과 코트 범위 검사
- 선수·팀과 분석 시간 범위 선택
- 12명 선수 이동경로 개별 켜기·끄기와 전체 켜기·끄기
- 원본 선수 ID를 유지한 화면 표시 이름 변경
- 두 선수의 이동거리·분당 이동거리·속도·관측시간·활동 범위 비교
- 비교 선수별 히트맵 나란히 표시
- 선수별 이동거리·평균 속도·최고 속도 계산
- 팀별 통계와 이동거리 비교
- 선수 이동경로와 활동 위치 히트맵
- 공 좌표가 존재하는 구간과 소유 선수 표시
- 외부 API 없이 검증된 수치로 만드는 자동 경기 요약
- 선수 통계 CSV, 팀 통계 CSV, 전체 분석 JSON 다운로드

## 사용 환경

이 컴퓨터에 설치된 Anaconda Python에는 실행에 필요한 라이브러리가 이미 준비되어 있습니다.

- Python: `C:\Anaconda\python.exe`
- 화면: Streamlit
- 데이터 처리: pandas, NumPy
- 차트: Plotly
- 테스트: pytest

VS Code에서 `Ctrl+Shift+P`를 누른 뒤 `Python: Select Interpreter`를 선택하고 `C:\Anaconda\python.exe`를 지정합니다.

## 실행 방법

VS Code에서 이 프로젝트 폴더를 연 뒤 터미널에서 다음 명령을 실행합니다.

```powershell
cd projects\03_tracking_report
& 'C:\Anaconda\python.exe' -m streamlit run app.py
```

브라우저가 자동으로 열리지 않으면 터미널에 표시되는 `http://localhost:8501` 주소를 엽니다.

화면 왼쪽의 `데이터 선택`에서 `샘플 CSV` 또는 `샘플 JSON`을 선택하면 바로 분석할 수 있습니다.

`선수 이동경로`에서 12명의 체크박스를 개별적으로 켜거나 끌 수 있습니다. `선수 이름 변경`을 펼쳐 이름을 입력하면 이동경로 범례, 통계표, 공 좌표 설명, 자동 경기 요약과 다운로드 결과에 새 이름이 표시됩니다. 원본 `P01~P12` ID는 데이터 연결을 위해 그대로 유지됩니다.

`선수 비교` 탭에서는 서로 다른 두 선수를 선택해 총 이동거리뿐 아니라 관측량 차이를 보정한 분당 이동거리, 평균·최고 속도, 유효 관측시간, 좌표·공 좌표 수, 가림 비율과 활동 범위를 비교할 수 있습니다. 두 선수의 히트맵도 같은 화면에 나란히 표시됩니다.

## 폴더 구성

```text
03_tracking_report/
├── app.py                       # Streamlit 대시보드
├── src/
│   ├── data_loader.py           # 파일 입력·검증·정제
│   ├── analytics.py             # 이동 구간·선수·팀 통계
│   ├── visualizations.py        # 경로·히트맵·팀 비교 차트
│   └── report_generator.py      # API 없는 자동 분석 문장
├── tests/                       # 데이터·계산 테스트
├── data/tracking/               # 실습 입력 데이터
├── examples/                    # 참고 결과 자료
├── requirements.txt
└── AI_USAGE.md                  # GPT·Codex 활용 및 검증 기록
```

## 데이터와 계산 기준

입력 필수 열은 다음과 같습니다.

```text
frame,time_sec,player_id,team,player_x,player_y,speed_mps,ball_x,ball_y,occluded
```

- 코트는 X `0~40m`, Y `0~20m`로 처리합니다.
- 범위 밖 좌표는 원본 열에 보존하고 계산·화면용 좌표만 코트 안으로 보정합니다.
- 기본적으로 시간 차가 1초를 넘는 두 선수 좌표는 서로 연결하지 않습니다.
- 가림 좌표는 기본적으로 이동거리와 속도 통계에 포함합니다. 화면에서 `가림 좌표를 거리·속도에서 제외`를 체크하면 가림 좌표 전후 구간을 제외합니다.
- 이동거리는 유효한 연속 좌표 사이의 유클리드 거리 합입니다.
- 분당 이동거리는 이동거리를 연결된 유효 관측시간으로 나눈 값입니다.
- 평균·최고 속도는 유효한 `speed_mps` 값으로 계산합니다.
- 공 X·Y가 모두 존재하는 행만 공 좌표로 사용합니다.
- 공 좌표가 있는 행의 `player_id`를 해당 시점의 소유 선수로 해석합니다.

시간 간격과 가림 제외 여부는 화면 왼쪽에서 변경할 수 있습니다.

## 테스트

프로젝트 폴더에서 다음 명령을 실행합니다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Anaconda\python.exe' -m pytest -p no:cacheprovider tests -q
```

검증 항목:

- CSV와 JSON이 동일한 3,995행·공 좌표 120행으로 변환되는지 확인
- 코트 범위 초과 좌표 경고와 보정 확인
- 불완전한 공 좌표 처리 확인
- 필수 열 누락 오류 확인
- 긴 시간 공백이 이동거리에서 제외되는지 확인
- 가림 좌표 포함·제외 설정 확인
- 변경한 선수 이름이 이동경로와 자동 요약에 반영되는지 확인

## 자동 경기 요약의 범위

OpenAI API 키가 없으므로 외부 GPT 호출은 사용하지 않습니다. 대시보드는 프로그램이 직접 검증한 통계만 조합하여 분석 문장을 생성합니다.

요약에는 이동거리 상위 선수, 최고 속도 선수, 공 좌표 기록 수, 팀별 관측량 차이와 데이터 품질 주의사항이 포함됩니다. 실제 점유율, 득점, 승패나 전술은 주어진 데이터만으로 확인할 수 없으므로 추측하지 않습니다.

## 제공 자료

```text
data/tracking/
├── tracking_sample.csv
└── tracking_sample.json
examples/
├── analysis_tracking.csv
├── analysis_tracking.json
├── analyzed_video_same_source.mp4
├── player_ball_detection_boxes.jpg
├── player_heatmap.jpg
└── player_movement_paths.jpg
```

`examples/`는 화면과 결과 파일의 형태를 이해하기 위한 참고 자료이며 분석 입력으로 사용하지 않습니다.

## MVP 제외 범위

- 회원가입·로그인과 서버 배포
- 실제 SPONJY 운영 API 연결
- 영상에서 좌표를 추출하는 선수·공 검출
- 외부 OpenAI API 호출
- 신규 AI 모델 학습
- 실시간 경기 분석, 의료 판단과 부상 진단
