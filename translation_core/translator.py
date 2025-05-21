from utils.file_handler import read_file # write_file은 GUI에서 직접 사용하거나 필요시 Translator에 추가
from llm_services.openai_service import OpenAIService
from llm_services.anthropic_service import AnthropicService
from llm_services.google_gemini_service import GoogleGeminiService
import re

# 지원하는 LLM 서비스 매핑
SUPPORTED_LLM_SERVICES = {
    "OpenAI": OpenAIService,
    "Anthropic": AnthropicService,
    "Google Gemini": GoogleGeminiService
}

CHUNK_SIZE = 2000 # 청크당 글자 수 (LLM API 제한 및 성능 고려)

# 키워드로 인식할 패턴들
KEYWORD_PATTERNS = [
    r'`[^`]+`',  # 백틱으로 둘러싸인 코드
    r'\{[^}]+\}',  # 중괄호로 둘러싸인 텍스트
    r'<[^>]+>',  # HTML/XML 태그
    r'\$[^$]+\$',  # 달러 기호로 둘러싸인 수식
    r'#\w+',  # 해시태그
    r'@\w+',  # 멘션
    r'https?://\S+',  # URL
    r'\b[A-Z][A-Z0-9_]*\b',  # 대문자로만 이루어진 상수
    r'\b[A-Za-z]+\.[A-Za-z]+(?:\.[A-Za-z]+)*\b',  # 점으로 구분된 식별자 (예: module.class.method)
    r'\b(?:[a-zA-Z]+_){2,}[a-zA-Z]+\b',  # 언더스코어로 구분된 식별자
]

class Translator:
    def __init__(self, llm_provider_name, api_key):
        self.llm_service = None
        self.llm_provider_name = llm_provider_name
        self.api_key = api_key
        self._initialize_llm_service()
        self.keyword_pattern = '|'.join(KEYWORD_PATTERNS)

    def _initialize_llm_service(self):
        if not self.api_key:
            # GUI에서 이미 API 키 유무를 확인하겠지만, 여기서도 방어적으로 처리
            print(f"Error: API key for {self.llm_provider_name} is missing.")
            # raise ValueError(f"API key for {self.llm_provider_name} is required.")
            self.llm_service = None
            return

        service_class = SUPPORTED_LLM_SERVICES.get(self.llm_provider_name)
        if service_class:
            try:
                self.llm_service = service_class(api_key=self.api_key)
                print(f"{self.llm_provider_name} service initialized successfully.")
            except ConnectionError as e:
                print(f"Error initializing {self.llm_provider_name} service: {e}")
                self.llm_service = None # 서비스 초기화 실패 처리
            except Exception as e:
                print(f"An unexpected error occurred while initializing {self.llm_provider_name} service: {e}")
                self.llm_service = None
        else:
            print(f"Error: Unsupported LLM provider: {self.llm_provider_name}")
            # raise ValueError(f"Unsupported LLM provider: {self.llm_provider_name}")
            self.llm_service = None

    def get_available_models(self):
        if self.llm_service:
            try:
                models = self.llm_service.get_models()
                print(f"Available models for {self.llm_provider_name}: {models}")
                return models
            except Exception as e:
                print(f"Error fetching models from {self.llm_provider_name}: {e}")
                return []
        else:
            print("LLM service not initialized. Cannot fetch models.")
            return []

    def get_all_models(self):
        """모든 사용 가능한 모델 목록을 반환 (최신 버전이 아닌 모델 포함)"""
        if self.llm_service:
            try:
                models = self.llm_service.get_all_models()
                print(f"All available models for {self.llm_provider_name}: {models}")
                return models
            except Exception as e:
                print(f"Error fetching all models from {self.llm_provider_name}: {e}")
                return self.get_available_models()  # 폴백: 최신 모델만이라도 반환
        else:
            print("LLM service not initialized. Cannot fetch models.")
            return []

    def _split_text_into_chunks(self, text, chunk_size=CHUNK_SIZE):
        """텍스트를 지정된 크기의 청크로 분할합니다."""
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        return chunks

    def _extract_keywords(self, text):
        """텍스트에서 키워드를 추출하고 플레이스홀더로 대체"""
        keywords = {}
        placeholder_counter = 0
        
        def replace_match(match):
            nonlocal placeholder_counter
            keyword = match.group(0)
            placeholder = f"__KEYWORD_{placeholder_counter}__"
            keywords[placeholder] = keyword
            placeholder_counter += 1
            return placeholder
        
        modified_text = re.sub(self.keyword_pattern, replace_match, text)
        return modified_text, keywords

    def _restore_keywords(self, translated_text, keywords):
        """번역된 텍스트에 원본 키워드 복원"""
        for placeholder, keyword in keywords.items():
            translated_text = translated_text.replace(placeholder, keyword)
        return translated_text

    def translate_file(self, input_file_path, output_language, selected_model, progress_callback=None):
        if not self.llm_service:
            message = "LLM service is not initialized. Please check API key and provider."
            if progress_callback: progress_callback(message)
            print(message)
            return f"Error: {message}"

        if progress_callback: progress_callback(f"Reading file: {input_file_path}")
        content = read_file(input_file_path)
        if content is None:
            message = f"Failed to read file: {input_file_path}"
            if progress_callback: progress_callback(message)
            return f"Error: {message}"

        if not content.strip():
            message = "Input file is empty."
            if progress_callback: progress_callback(message)
            return "" # 빈 파일은 빈 내용으로 번역

        chunks = self._split_text_into_chunks(content)
        translated_chunks = []
        total_chunks = len(chunks)

        if progress_callback: progress_callback(f"Starting translation of {total_chunks} chunk(s) using {self.llm_provider_name} ({selected_model})...")

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(f"Translating chunk {i + 1}/{total_chunks}...")
            try:
                # 키워드 추출 및 플레이스홀더 대체
                modified_chunk, keywords = self._extract_keywords(chunk)
                
                # 수정된 텍스트 번역
                translated_chunk = self.llm_service.translate(modified_chunk, output_language, selected_model)
                
                if "Translation error:" in translated_chunk or "Error:" in translated_chunk:
                    error_message = f"Error translating chunk {i+1}: {translated_chunk}"
                    if progress_callback: progress_callback(error_message)
                    translated_chunks.append(f"[CHUNK_ERROR: {translated_chunk}]\n")
                else:
                    # 번역된 텍스트에 키워드 복원
                    restored_chunk = self._restore_keywords(translated_chunk, keywords)
                    translated_chunks.append(restored_chunk)

            except Exception as e:
                error_message = f"Exception during translation of chunk {i + 1}/{total_chunks}: {e}"
                if progress_callback: progress_callback(error_message)
                translated_chunks.append(f"[CHUNK_EXCEPTION: {str(e)}]\n")

        full_translated_text = "\n".join(translated_chunks)
        
        if progress_callback: progress_callback("Translation complete.")
        return full_translated_text

# Translation logic will be implemented here 