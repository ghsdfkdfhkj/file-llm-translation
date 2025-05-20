from .base_llm import BaseLLM
import openai # 실제 OpenAI 라이브러리 import 필요

# 선호하는 최신 OpenAI 모델 순서 (Chat Completions용)
PREFERRED_OPENAI_MODELS_ORDER = [
    "gpt-4-turbo", # 일반적으로 가장 최신이고 강력한 모델 중 하나
    "gpt-4-turbo-preview", # Preview 버전이 있다면
    "gpt-4o", # 최신 Omni 모델
    "gpt-4",
    "gpt-3.5-turbo",
]

# OpenAI API integration will be implemented here

class OpenAIService(BaseLLM):
    def __init__(self, api_key):
        super().__init__(api_key)
        try:
            self.client = openai.OpenAI(api_key=self.api_key)
            print("OpenAI client initialized successfully.")
        except Exception as e:
            print(f"Error initializing OpenAI client: {e}")
            raise ConnectionError(f"Failed to initialize OpenAI client: {e}")

    def get_models(self):
        if not self.api_key:
            print("OpenAI API 키가 설정되지 않았습니다.")
            return []
        try:
            models_response = self.client.models.list()
            available_models_from_api = {model.id for model in models_response.data}
            
            # 선호 목록 중 API에서 사용 가능한 모델만 필터링하고 순서 유지
            ordered_models = []
            for preferred_model_base in PREFERRED_OPENAI_MODELS_ORDER:
                # API 응답에서 전체 ID 또는 해당 base로 시작하는 모델 찾기
                # (예: "gpt-4-turbo-2024-04-09"는 "gpt-4-turbo"로 시작)
                found_model = None
                if preferred_model_base in available_models_from_api:
                    found_model = preferred_model_base
                else: # 부분 일치 검색 (예: gpt-4-turbo-XYZ)
                    for api_model_id in available_models_from_api:
                        if api_model_id.startswith(preferred_model_base):
                            found_model = api_model_id
                            break
                if found_model and found_model not in ordered_models: # 중복 방지
                    ordered_models.append(found_model)

            # Chat Completions를 지원하고, instruct가 아니며, 위 선호 목록에 없는 GPT 모델 추가
            other_gpt_models = sorted([
                model.id for model in models_response.data 
                if "gpt" in model.id and 
                   ("turbo" in model.id or "gpt-4" in model.id or model.id.startswith("gpt-3.5")) and 
                   not "instruct" in model.id and 
                   model.id not in ordered_models # 이미 추가된 선호 모델 제외
            ], reverse=True) # 이름으로 대략적인 최신순 정렬

            final_model_list = ordered_models + other_gpt_models

            if not final_model_list:
                print("No suitable OpenAI models found after filtering. Returning default.")
                return ["gpt-3.5-turbo"] # 비상시 기본값
            
            print(f"Available OpenAI models (ordered): {final_model_list}")
            return final_model_list
        except Exception as e:
            print(f"OpenAI 모델 목록 가져오기 실패: {e}")
            return ["gpt-3.5-turbo"] 

    def translate(self, text, target_language, model_name):
        if not self.api_key:
            return "Error: OpenAI API key not set."
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": f"You are a helpful assistant that translates text into {target_language}. Provide ONLY the translated text itself, without any additional explanations, introductory phrases, or conversational remarks. Do not include the original text in your response."},
                    {"role": "user", "content": text}
                ],
                max_tokens=len(text) + 500, # 원본 텍스트 길이에 기반하여 토큰 수 유동적으로 설정 (번역 시 약간 더 길어질 수 있음 고려)
                temperature=0.7, # 번역 작업에는 일관성을 위해 낮은 값 (0.2 ~ 0.7) 선호
            )
            translated_text = response.choices[0].message.content.strip()
            return translated_text
        except openai.APIError as e: # OpenAI API 오류 세분화
            print(f"OpenAI API Error ({model_name}): {e}")
            if "Invalid API key" in str(e) or (hasattr(e, 'http_status') and e.http_status == 401):
                 return "Error: OpenAI API key is not valid. Please check your API key."
            elif hasattr(e, 'http_status') and e.http_status == 429: # Rate limit
                 return "Error: OpenAI API rate limit exceeded. Please try again later or check your plan."
            error_message = str(e.message) if hasattr(e, 'message') else str(e)
            error_code = str(e.code) if hasattr(e, 'code') else 'N/A'
            return f"OpenAI API Error: {error_code} - {error_message}"
        except Exception as e:
            print(f"OpenAI 번역 실패 ({model_name}): {e}")
            return f"Translation error with OpenAI: {e}" 