from utils.file_handler import read_file # write_file은 GUI에서 직접 사용하거나 필요시 Translator에 추가
from llm_services.openai_service import OpenAIService
from llm_services.anthropic_service import AnthropicService
from llm_services.google_gemini_service import GoogleGeminiService

# 지원하는 LLM 서비스 매핑
SUPPORTED_LLM_SERVICES = {
    "OpenAI": OpenAIService,
    "Anthropic": AnthropicService,
    "Google Gemini": GoogleGeminiService
}

CHUNK_SIZE = 2000 # 청크당 글자 수 (LLM API 제한 및 성능 고려)

class Translator:
    def __init__(self, llm_provider_name, api_key):
        self.llm_service = None
        self.llm_provider_name = llm_provider_name
        self.api_key = api_key
        self._initialize_llm_service()

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
                return [] # 오류 발생 시 빈 리스트 반환
        else:
            print("LLM service not initialized. Cannot fetch models.")
            return []

    def _split_text_into_chunks(self, text, chunk_size=CHUNK_SIZE):
        """텍스트를 지정된 크기의 청크로 분할합니다."""
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        return chunks

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
                translated_chunk = self.llm_service.translate(chunk, output_language, selected_model)
                if "Translation error:" in translated_chunk or "Error:" in translated_chunk: # LLM 서비스에서의 오류 메시지 확인
                    error_message = f"Error translating chunk {i+1}: {translated_chunk}"
                    if progress_callback: progress_callback(error_message)
                    # 전체 번역을 중단할지, 아니면 오류 청크를 건너뛸지 결정할 수 있습니다.
                    # 여기서는 오류 메시지를 포함하고 계속 진행합니다.
                    translated_chunks.append(f"[CHUNK_ERROR: {translated_chunk}]\n") 
                else:
                    translated_chunks.append(translated_chunk)
                
                # LLM API 정책에 따른 요청 간 지연 시간 추가 (필요한 경우)
                # import time
                # time.sleep(1) # 예: 1초 대기

            except Exception as e:
                error_message = f"Exception during translation of chunk {i + 1}/{total_chunks}: {e}"
                if progress_callback: progress_callback(error_message)
                translated_chunks.append(f"[CHUNK_EXCEPTION: {str(e)}]\n")
                # 심각한 예외 발생 시 (예: 네트워크 오류), 루프를 중단할 수도 있습니다.
                # break 

        full_translated_text = "\n".join(translated_chunks) # 청크들을 줄바꿈으로 합침 (또는 원본 구조에 맞게)
        
        if progress_callback: progress_callback("Translation complete.")
        return full_translated_text

# Translation logic will be implemented here 