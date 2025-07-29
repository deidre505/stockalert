
# 주식 알림 애플리케이션 - 설계 문서

이 문서는 주식 알림 애플리케이션의 설계 및 아키텍처에 대해 설명합니다. 이 애플리케이션은 사용자 정의 기준에 따라 주가를 모니터링하고 알림을 제공하는 데스크탑 도구입니다.

## 1. 핵심 기능

*   **주식 포트폴리오 관리:** 사용자는 자신의 포트폴리오에 주식을 추가, 제거, 조회할 수 있습니다. 주식별 보유 수량, 매입가, 통화 정보를 추적합니다.
*   **실시간 주가 추적:** Yahoo Finance로부터 실시간 주가를 가져와 표시합니다.
*   **사용자 정의 알림:** 다음과 같은 다양한 유형의 알림을 설정할 수 있습니다:
    *   **목표가 이상 상승 시:** 주가가 특정 목표를 초과할 경우 발동
    *   **목표가 이하 하락 시:** 주가가 특정 목표 이하로 떨어질 경우 발동
    *   **최근 고점 대비 하락:** 주가가 최근 고점에서 일정 비율 이상 하락할 경우
    *   **최근 저점 대비 상승:** 주가가 최근 저점에서 일정 비율 이상 상승할 경우
*   **알림 제공:** 알림이 발동되면 화면상 알림 및 모바일 푸시 알림(Pushover 또는 Pushbullet)을 제공합니다.
*   **GUI 대시보드:** CustomTkinter로 제작된 사용자 친화적인 그래픽 인터페이스에서 포트폴리오, 손익(P/L, P/L %) 및 알림 설정 정보를 표시합니다.
*   **시스템 트레이 통합:** 애플리케이션을 시스템 트레이에 최소화하여 백그라운드 실행이 가능합니다.

## 2. 아키텍처

애플리케이션은 기능별로 구분된 모듈형 구조를 따릅니다.

### 2.1. 메인 애플리케이션 (`main.py`)

*   **프레임워크:** GUI는 CustomTkinter 기반
*   **주요 기능:**
    *   메인 애플리케이션 창과 탭(Dashboard, Add Stock, Alerts, Settings) 초기화
    *   애플리케이션 상태(`is_running`, `is_quitting`) 관리
    *   주식 추가, 알림 생성, 설정 구성 등 사용자 인터랙션 처리
    *   알림 및 대시보드 새로고침을 위한 백그라운드 쓰레드 관리
    *   시스템 트레이 아이콘 및 동작 관리
    *   디버그 패널 제공 (`Ctrl+Shift+D`로 가짜 데이터 주입 가능)

### 2.2. 알림 모듈 (`alerter.py`)

*   **주요 기능:**
    *   별도 백그라운드 쓰레드에서 지속적으로 알림 조건 확인
    *   데이터베이스로부터 활성 알림 목록을 가져옴
    *   `yfinance_client`를 통해 실시간 주가 조회
    *   현재 주가와 알림 조건을 비교하여 처리
    *   퍼센트 기반 알림의 상태 유지(e.g., "watching_for_peak", "watching_for_drop")
    *   알림이 발생하면 `notifier` 모듈을 통해 알림 전송
    *   UI 표시용으로 `ui_alert_queue`를 통해 알림을 메인 쓰레드에 전달

### 2.3. 데이터베이스 (`database.py`)

*   **프레임워크:** SQLite 사용
*   **주요 기능:**
    *   데이터 지속성 관리. 데이터베이스 파일은 사용자의 `APPDATA` 디렉토리에 저장
    *   `stocks`, `alerts`, `settings` 테이블 정의
    *   CRUD 기능 제공 (생성, 조회, 수정, 삭제)
    *   애플리케이션 버전 변경 시 스키마 마이그레이션 수행

### 2.4. Yahoo Finance 클라이언트 (`yfinance_client.py`)

*   **프레임워크:** `requests` 라이브러리로 Yahoo Finance API 호출
*   **주요 기능:**
    *   실시간 주가 데이터 요청
    *   API 요청에 대한 예외 처리 및 재시도 기능 포함
    *   성능 향상을 위한 응답 캐싱 기능 포함

### 2.5. 알림 발송기 (`notifier.py`)

*   **프레임워크:** `requests` 사용
*   **주요 기능:**
    *   외부 서비스(Pushover, Pushbullet)를 통해 모바일 알림 전송
    *   API 호출 처리 및 오류 관리

## 3. 데이터 모델

애플리케이션 데이터는 SQLite 데이터베이스에 저장됩니다.

### `stocks` 테이블

| 컬럼           | 타입    | 설명                                    |
| -------------- | ------- | --------------------------------------- |
| `id`           | INTEGER | 기본 키                                 |
| `ticker`       | TEXT    | 주식 티커 심볼 (예: "AAPL")            |
| `full_name`    | TEXT    | 주식 전체 이름                         |
| `shares`       | REAL    | 보유 수량                               |
| `purchase_price`| REAL    | 평균 매입 단가                          |
| `currency`     | TEXT    | 통화 단위 (예: "USD")                   |

### `alerts` 테이블

| 컬럼                   | 타입    | 설명                                                  |
| ---------------------- | ------- | ----------------------------------------------------- |
| `id`                   | INTEGER | 기본 키                                               |
| `stock_id`             | INTEGER | `stocks` 테이블을 참조하는 외래 키                   |
| `alert_type`           | TEXT    | 알림 유형 (예: "Price Rises Above")                  |
| `threshold_percent`    | REAL    | 퍼센트 기반 알림용 임계치                            |
| `target_price`         | REAL    | 목표 가격 기반 알림용 설정값                         |
| `is_active`            | INTEGER | 현재 활성 여부 (1 = 활성, 0 = 비활성)                |
| `last_benchmark_price` | REAL    | 퍼센트 기반 알림을 위한 마지막 기준 가격             |
| `current_state`        | TEXT    | 현재 알림 상태 (예: "watching_for_peak")             |

### `settings` 테이블

애플리케이션 설정을 저장하는 key-value 형태의 테이블입니다.

| 키                         | 값                                                                  |
| -------------------------- | ------------------------------------------------------------------- |
| `notification_service`     | "None", "Pushover", 또는 "Pushbullet"                               |
| `pushover_user_key`        | 사용자 Pushover 키                                                  |
| `pushover_api_token`       | 애플리케이션의 Pushover API 토큰                                   |
| `pushbullet_api_token`     | 사용자의 Pushbullet 액세스 토큰                                    |
| `dashboard_refresh_interval`| 대시보드 새로고침 간격 (초 단위)                                   |
| `minimize_to_tray`         | "True" 또는 "False"                                                 |
| `column_widths`            | 대시보드 테이블 열 너비 정보(JSON 문자열 형태)                     |

## 4. 의존성

이 애플리케이션은 `requirements.txt`에 다음 파이썬 라이브러리에 의존합니다:

*   `yfinance`: 주식 데이터 수집용
*   `requests`: 외부 API 호출용
*   `customtkinter`: GUI 프레임워크
*   `requests-cache`: 응답 캐싱
*   `pystray`: 시스템 트레이 아이콘 관리
*   `Pillow`: 애플리케이션 아이콘 처리용
