from abc import ABC, abstractmethod

# Abstract base class for LLM services will be defined here

class BaseLLM(ABC):
    def __init__(self, api_key):
        self.api_key = api_key

    @abstractmethod
    def get_models(self):
        """사용 가능한 모델 목록을 반환합니다."""
        pass

    @abstractmethod
    def translate(self, text, target_language, model_name):
        """주어진 텍스트를 대상 언어로 번역합니다."""
        pass 