from abc import ABC, abstractmethod

# Abstract base class for LLM services will be defined here

class BaseLLM(ABC):
    def __init__(self, api_key):
        self.api_key = api_key

    @abstractmethod
    def get_models(self):
        """Returns a list of available models."""
        pass

    @abstractmethod
    def translate(self, text, target_language, model_name):
        """Translates the given text to the target language."""
        pass 