# 게임 번역 프로그램

LLM API를 활용하여 긴 게임 파일을 번역하는 프로그램입니다.

## 주요 기능

*   다양한 LLM 선택 (OpenAI, Anthropic, Google Gemini 등)
*   API 키 입력
*   LLM 모델 자동 감지 및 선택
*   다양한 출력 언어 선택
*   파일 입력 및 번역된 파일 내보내기

## 폴더 구조

```
translation_project/
├── main.py
├── gui/
│   ├── __init__.py
│   ├── main_window.py
│   └── widgets.py
├── llm_services/
│   ├── __init__.py
│   ├── base_llm.py
│   ├── openai_service.py
│   ├── anthropic_service.py
│   └── google_gemini_service.py
├── translation_core/
│   ├── __init__.py
│   └── translator.py
├── utils/
│   ├── __init__.py
│   ├── file_handler.py
│   └── config_manager.py
├── assets/
└── README.md
└── requirements.txt
```

## 설치

1.  저장소를 클론합니다.
2.  가상 환경을 생성하고 활성화합니다. (권장)
3.  `pip install -r requirements.txt` 명령으로 의존성 라이브러리를 설치합니다.

## 사용법

`python main.py` 명령으로 프로그램을 실행합니다. 