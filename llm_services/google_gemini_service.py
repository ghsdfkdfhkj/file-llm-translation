# Google Gemini API integration will be implemented here 
from .base_llm import BaseLLM
import google.generativeai as genai # 실제 Google Gemini 라이브러리 import 필요
import re # For version sorting
from collections import defaultdict

# 알려진 최신 및 주요 Gemini 모델 (번역 지원 가능성 높은 모델 위주)
# 실제 사용 가능성은 API 키와 리전에 따라 달라질 수 있습니다.
KNOWN_GEMINI_MODELS = {
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash-latest",
    "gemini-1.0-pro", # "gemini-pro"는 "gemini-1.0-pro"의 별칭일 수 있음
    # "gemini-experimental" # 필요한 경우
}
# 명시적으로 제외할 모델 이름의 일부 또는 전체 (소문자로 비교)
EXCLUDED_MODEL_PATTERNS = [
    "vision", # 일반적으로 번역보다는 멀티모달 작업용
    "embedcontent",
    "aqa",
    "text-bison", # 구형 PaLM 모델
    "text-unicorn",
    "chat-bison",
    "codechat-bison",
    "textembedding-gecko",
    "-preview-", # 일반적으로 preview 모델은 제외
    "-exp-"      # experimental 모델도 일반적으로 제외
]

# Helper for sorting models by version and 'latest' tag
def gemini_model_sort_key(model_name):
    is_latest = "-latest" in model_name
    version_match = re.search(r"gemini-(\d+\.?\d*)", model_name)
    version_number = 0.0
    if version_match:
        try:
            version_number = float(version_match.group(1))
        except ValueError:
            pass # Should not happen with current regex
    # Sort order: latest first, then higher version, then alphabetically
    return (not is_latest, -version_number, model_name)

# 정렬 및 최신 모델 선택을 위한 키 생성 함수
def get_gemini_model_key_components(model_name_full):
    # 예: "gemini-1.5-pro-latest", "gemini-1.0-pro-001", "gemini-1.5-flash-20240515"
    name = model_name_full.replace("models/", "")
    
    base_name_match = re.match(r"(gemini-\d+\.?\d*-(?:pro|flash|ultra))", name)
    if not base_name_match:
        # 1.0-pro 같이 -flash나 -pro가 이름 중간에 없는 경우도 고려
        base_name_match = re.match(r"(gemini-\d+\.?\d*-pro)", name)
        if not base_name_match:
            # 그 외 "gemini-1.0-pro" 같은 기본 형태
            if name in ["gemini-1.0-pro", "gemini-pro"]:
                 base_name = "gemini-1.0-pro" # 정규화
            else: # 기본 패턴을 못찾으면 전체 이름을 base로 사용 (단일 모델로 취급)
                base_name = name 
        else:
            base_name = base_name_match.group(1)
    else:
        base_name = base_name_match.group(1)

    is_latest = "-latest" in name
    # 버전 번호 (예: -001), 특정 날짜 (예: -20240515), 또는 기타 접미사
    # 간단하게는 -latest를 가장 우선하고, 그 외에는 문자열 정렬 (숫자가 크거나, 날짜가 뒤일수록 좋음)
    # 좀 더 정교하게 하려면 -001, -002 같은 숫자나 날짜를 파싱해야 함
    version_suffix = name.replace(base_name, "").lstrip('-')
    if is_latest: version_suffix = "zzzzzzz_latest" # latest가 항상 가장 뒤에 오도록 (역정렬 시 가장 앞)
    
    # 기본 이름, 최신 여부(True가 더 좋음), 버전 접미사(문자열 역정렬) 반환
    return base_name, is_latest, version_suffix

class GoogleGeminiService(BaseLLM):
    def __init__(self, api_key):
        super().__init__(api_key)
        try:
            genai.configure(api_key=self.api_key)
            print("Google Gemini API key configured successfully.")
        except Exception as e:
            print(f"Error configuring Google Gemini API key: {e}")
            # GUI에서 이 오류를 처리할 수 있도록 예외를 다시 발생시키거나, 
            # 서비스 사용 불가능 상태를 명확히 표시할 수 있는 방법을 고려해야 합니다.
            # 여기서는 ConnectionError를 발생시켜 Translator에서 처리하도록 합니다.
            raise ConnectionError(f"Failed to configure Google Gemini API key: {e}")

    def get_models(self):
        if not self.api_key: 
            print("Google Gemini API 키가 설정되지 않았습니다.")
            return []
        try:
            listed_models_api = genai.list_models()
            all_candidate_models = set()

            for m in listed_models_api:
                model_id = m.name.replace("models/", "")
                if 'generateContent' in m.supported_generation_methods and \
                   not any(pattern in model_id.lower() for pattern in EXCLUDED_MODEL_PATTERNS):
                    all_candidate_models.add(model_id)
            
            for known_model in KNOWN_GEMINI_MODELS:
                if not any(pattern in known_model.lower() for pattern in EXCLUDED_MODEL_PATTERNS):
                     all_candidate_models.add(known_model.replace("models/", ""))

            if not all_candidate_models:
                print("No suitable Gemini models found initially.")
                return []

            # 그룹별 최신 모델 선택
            grouped_models = defaultdict(list)
            for model_name in all_candidate_models:
                base_name, _, _ = get_gemini_model_key_components(model_name)
                grouped_models[base_name].append(model_name)
            
            representative_models = []
            for base_name, model_list in grouped_models.items():
                if not model_list: continue
                # 각 그룹 내에서 정렬하여 가장 최신 모델 선택
                # 정렬: is_latest (True가 우선), version_suffix (문자열 내림차순)
                # get_gemini_model_key_components의 반환값 (base, is_latest, suffix)
                # suffix는 latest일 경우 zzz로 시작해서 가장 뒤로 감. is_latest는 True가 더 좋음(역정렬 시 False가 앞)
                best_model_in_group = sorted(model_list, key=lambda m: (not get_gemini_model_key_components(m)[1], get_gemini_model_key_components(m)[2]), reverse=True)[0]
                representative_models.append(best_model_in_group)

            # 최종 대표 모델 목록을 다시 한번 정렬 (기본 모델명, 최신여부, 버전 순)
            final_model_list = sorted(representative_models, key=get_gemini_model_key_components)
            
            # "gemini-pro" 가 "gemini-1.0-pro" 보다 선호된다면, 여기서 조정 가능 (현재는 1.0-pro가 남음)
            # 예: if "gemini-1.0-pro" in final_model_list and "gemini-pro" in final_model_list: final_model_list.remove("gemini-pro")

            print(f"Available Google Gemini models (representatives): {final_model_list}")
            return final_model_list
        except Exception as e:
            print(f"Google Gemini 모델 목록 가져오기 실패: {e}")
            # API 키 오류 등으로 모델 목록 조회 실패 시 빈 리스트 반환
            return []

    def translate(self, text, target_language, model_name):
        if not self.api_key:
            return "Error: Google Gemini API key not set."
        model_to_use = model_name 
        try:
            if not model_name.startswith('models/'):
                if "1.5" in model_name or "experimental" in model_name or model_name.endswith("-latest") or "1.0-pro" in model_name: # 1.0-pro도 명시적으로 추가
                     model_to_use = f'models/{model_name}'

            model = genai.GenerativeModel(model_to_use)
            prompt = f"Translate the following text into {target_language}. Provide ONLY the translated text itself, without any additional explanations, introductory phrases, or conversational remarks. Do not include the original text in your response.\n\nOriginal text: {text}\n\nTranslated text:"
            
            # 안전 설정 (필요에 따라 조정)
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            response = model.generate_content(prompt, safety_settings=safety_settings)
            
            # 응답에서 텍스트 추출 (Gemini API 응답 구조에 따라 다를 수 있음)
            if response.parts:
                translated_text = ''.join(part.text for part in response.parts if hasattr(part, 'text'))
            elif hasattr(response, 'text'): # 경우에 따라 text 속성에 바로 있을 수도 있음
                translated_text = response.text
            else: # 응답 구조가 예상과 다를 경우, 전체 응답을 로깅하고 오류 반환
                print(f"Unexpected Gemini API response structure: {response}")
                # 사용자가 어떤 내용을 받았는지 확인하기 위해 candidates라도 확인
                if response.candidates and response.candidates[0].content.parts:
                     translated_text = ''.join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text')) 
                else:
                    return "Error: Could not extract translated text from Gemini API response."
            
            return translated_text.strip()
        except Exception as e:
            print(f"Google Gemini 번역 실패 ({model_name} / {model_to_use if 'model_to_use' in locals() else ''}): {e}")
            if "API key not valid" in str(e):
                return "Error: Google Gemini API key is not valid. Please check your API key."
            elif "billing account" in str(e):
                 return "Error: Billing account issue with Google Cloud. Please check your Google Cloud project."
            elif "Resourc Exhausted" in str(e) or "429" in str(e):
                 return "Error: Google Gemini API quota exceeded. Please try again later or check your quota."
            elif "permission" in str(e).lower() or "denied" in str(e).lower():
                 return f"Error: Permission denied for model {model_name}. Check API key permissions."
            return f"Translation error with Gemini: {e}" 