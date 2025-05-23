from abc import ABC, abstractmethod

# Abstract base class for LLM services will be defined here

class BaseLLM(ABC):
    def __init__(self, api_key):
        self.api_key = api_key
        self.model = None

    @abstractmethod
    def get_models(self):
        """Returns a list of available models."""
        pass

    @abstractmethod
    def translate(self, text, target_language, model_name):
        """Translates the given text to the target language."""
        pass

    def get_completion(self, prompt):
        """Get a completion from the LLM."""
        raise NotImplementedError("Subclasses must implement get_completion")

    def get_all_models(self):
        """Get all available models including non-latest versions."""
        return self.get_models()  # Default implementation falls back to get_models

    def set_model(self, model_name):
        """Set the current model to use for completions."""
        self.model = model_name 