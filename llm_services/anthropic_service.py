# Anthropic API integration will be implemented here 
from .base_llm import BaseLLM
import anthropic # 실제 Anthropic 라이브러리 import 필요
import re # For version and date sorting

# 알려진 주요 Anthropic 모델 목록
# 이름에 버전과 날짜가 포함되어 있어 정렬에 사용 가능
KNOWN_ANTHROPIC_MODELS = [
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "claude-3.5-sonnet-20240620", # 최신 모델 추가 예시 (실제 출시 여부 확인 필요)
    "claude-2.1",
    "claude-2.0",
    "claude-instant-1.2"
]

def anthropic_model_sort_key(model_name):
    # 예: claude-3-opus-20240229, claude-3.5-sonnet-20240620
    # 1. Claude 버전 (3.5 > 3 > 2 > 1)
    # 2. 모델 크기 (opus > sonnet > haiku/instant)
    # 3. 날짜 (최신순)
    version_major = 0
    version_minor = 0
    date_str = "00000000"
    size_priority = 3 # opus=0, sonnet=1, haiku/instant=2, other=3

    version_match = re.search(r"claude-(\d+)(?:\.(\d+))?", model_name.lower())
    if version_match:
        version_major = int(version_match.group(1))
        if version_match.group(2):
            version_minor = int(version_match.group(2))
    
    date_match = re.search(r"(\d{8})$", model_name)
    if date_match:
        date_str = date_match.group(1)

    if "opus" in model_name: size_priority = 0
    elif "sonnet" in model_name: size_priority = 1
    elif "haiku" in model_name or "instant" in model_name: size_priority = 2
    
    # 최신 버전, 큰 모델, 최신 날짜 순으로 정렬 (모두 내림차순이므로 음수 또는 not 사용)
    return (-version_major, -version_minor, size_priority, -int(date_str))

class AnthropicService(BaseLLM):
    def __init__(self, api_key):
        super().__init__(api_key)
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            print("Anthropic client initialized successfully.")
        except Exception as e:
            print(f"Error initializing Anthropic client: {e}")
            raise ConnectionError(f"Failed to initialize Anthropic client: {e}")

    def get_models(self):
        if not self.api_key:
            print("Anthropic API 키가 설정되지 않았습니다.")
            return []
        try:
            # 현재 Anthropic 라이브러리는 모델 목록 조회 API를 직접 제공하지 않음.
            # 따라서 하드코딩된 목록을 정렬하여 사용합니다.
            # 실제 사용 가능한 모델은 Anthropic 문서를 참조하세요.
            
            # 정렬된 모델 목록 반환
            sorted_models = sorted(KNOWN_ANTHROPIC_MODELS, key=anthropic_model_sort_key)
            print(f"Available Anthropic models (sorted): {sorted_models}")
            return sorted_models
        except Exception as e:
            print(f"Anthropic 모델 목록 처리 중 오류: {e}")
            # 비상시 기본 정렬되지 않은 목록 또는 최소한의 목록 반환 가능
            return sorted(KNOWN_ANTHROPIC_MODELS, reverse=True) 

    def translate(self, text, target_language, model_name):
        if not self.api_key:
            return "Error: Anthropic API key not set."
        try:
            response = self.client.messages.create(
                model=model_name,
                max_tokens=len(text) + 500, 
                messages=[
                    {
                        "role": "user",
                        "content": f"Translate the following English text to {target_language}. Provide ONLY the translated text, without any surrounding explanations, apologies, or introductory phrases like 'Here is the translation:'. Do not repeat the original text.\n\nOriginal text:\n{text}\n\nTranslated text in {target_language}:"
                    }
                ]
            )
            translated_text = response.content[0].text
            return translated_text.strip()
        except anthropic.APIError as e: 
            print(f"Anthropic API Error ({model_name}): {e}")
            if hasattr(e, 'status_code') and e.status_code == 401: 
                 return "Error: Anthropic API key is not valid or not authorized for this model."
            elif hasattr(e, 'status_code') and e.status_code == 429: 
                 return "Error: Anthropic API rate limit exceeded. Please try again later or check your plan."
            error_message = str(e.message) if hasattr(e, 'message') else str(e)
            return f"Anthropic API Error: {error_message}"
        except Exception as e:
            print(f"Anthropic 번역 실패 ({model_name}): {e}")
            return f"Translation error with Anthropic: {e}" 