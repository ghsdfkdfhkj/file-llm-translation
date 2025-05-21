# Google Gemini API integration will be implemented here 
from .base_llm import BaseLLM
import google.generativeai as genai # Import actual Google Gemini library
import re # For version sorting
from collections import defaultdict

# Known latest and major Gemini models (focusing on models likely to support translation)
# Actual availability may vary depending on API key and region
KNOWN_GEMINI_MODELS = {
    "gemini-1.0-pro",  # Most stable model
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash-latest",
}
# Model name patterns to explicitly exclude (compared in lowercase)
EXCLUDED_MODEL_PATTERNS = [
    "vision",
    "embedcontent",
    "aqa",
    "text-bison",
    "text-unicorn",
    "chat-bison",
    "codechat-bison",
    "textembedding-gecko",
    "-preview-",
    "-exp-",
    "experimental",
    "flash-thinking",
    "pro-exp"
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

# Key generation function for sorting and latest model selection
def get_gemini_model_key_components(model_name_full):
    # Example: "gemini-1.5-pro-latest", "gemini-1.0-pro-001", "gemini-1.5-flash-20240515"
    name = model_name_full.replace("models/", "")
    
    base_name_match = re.match(r"(gemini-\d+\.?\d*-(?:pro|flash|ultra))", name)
    if not base_name_match:
        # Consider cases where -flash or -pro is not in the middle of the name, like 1.0-pro
        base_name_match = re.match(r"(gemini-\d+\.?\d*-pro)", name)
        if not base_name_match:
            # Otherwise basic form like "gemini-1.0-pro"
            if name in ["gemini-1.0-pro", "gemini-pro"]:
                 base_name = "gemini-1.0-pro" # Normalize
            else: # If basic pattern not found, use entire name as base (treat as single model)
                base_name = name 
        else:
            base_name = base_name_match.group(1)
    else:
        base_name = base_name_match.group(1)

    is_latest = "-latest" in name
    # Version number (e.g., -001), specific date (e.g., -20240515), or other suffix
    # Simply prioritize -latest first, then string sort (larger numbers or later dates are better)
    # For more sophisticated approach, need to parse numbers or dates like -001, -002
    version_suffix = name.replace(base_name, "").lstrip('-')
    if is_latest: version_suffix = "zzzzzzz_latest" # Make latest always come last (first when reverse sorted)
    
    # Return base name, latest flag (True is better), version suffix (string reverse sort)
    return base_name, is_latest, version_suffix

# Default stable model to use as fallback
DEFAULT_MODEL = "gemini-1.0-pro"

class GoogleGeminiService(BaseLLM):
    def __init__(self, api_key):
        super().__init__(api_key)
        try:
            genai.configure(api_key=self.api_key)
            print("Google Gemini API key configured successfully.")
        except Exception as e:
            print(f"Error configuring Google Gemini API key: {e}")
            # Consider how to handle service initialization failure in GUI,
            # or how to clearly indicate service unavailability.
            # Here we raise ConnectionError for Translator to handle.
            raise ConnectionError(f"Failed to configure Google Gemini API key: {e}")

    def get_models(self):
        if not self.api_key: 
            print("Google Gemini API key is not set.")
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

            # Select latest model per group
            grouped_models = defaultdict(list)
            for model_name in all_candidate_models:
                base_name, _, _ = get_gemini_model_key_components(model_name)
                grouped_models[base_name].append(model_name)
            
            representative_models = []
            for base_name, model_list in grouped_models.items():
                if not model_list: continue
                # Sort within each group and select the latest model
                # Sort by: is_latest (True first), version_suffix (string descending)
                # get_gemini_model_key_components returns (base, is_latest, suffix)
                # suffix starts with zzz for latest to sort last. is_latest True is better (False first when reversed)
                best_model_in_group = sorted(model_list, key=lambda m: (not get_gemini_model_key_components(m)[1], get_gemini_model_key_components(m)[2]), reverse=True)[0]
                representative_models.append(best_model_in_group)

            # Sort final representative model list again (by base model name, latest flag, version)
            final_model_list = sorted(representative_models, key=get_gemini_model_key_components)
            
            # If "gemini-pro" is preferred over "gemini-1.0-pro", adjust here (currently keeps 1.0-pro)
            # Example: if "gemini-1.0-pro" in final_model_list and "gemini-pro" in final_model_list: final_model_list.remove("gemini-pro")

            print(f"Available Google Gemini models (representatives): {final_model_list}")
            return final_model_list
        except Exception as e:
            print(f"Failed to get Google Gemini model list: {e}")
            # Return empty list if model list query fails due to API key error etc.
            return []

    def get_all_models(self):
        """Returns all available models (including non-latest versions)"""
        if not self.api_key: 
            print("Google Gemini API key is not set.")
            return []
        try:
            listed_models_api = genai.list_models()
            all_models = set()

            for m in listed_models_api:
                model_id = m.name.replace("models/", "")
                if 'generateContent' in m.supported_generation_methods and \
                   not any(pattern in model_id.lower() for pattern in EXCLUDED_MODEL_PATTERNS):
                    all_models.add(model_id)
            
            for known_model in KNOWN_GEMINI_MODELS:
                if not any(pattern in known_model.lower() for pattern in EXCLUDED_MODEL_PATTERNS):
                     all_models.add(known_model.replace("models/", ""))

            if not all_models:
                print("No suitable Gemini models found.")
                return []

            # Sort all models by version
            final_model_list = sorted(all_models, key=get_gemini_model_key_components)
            
            print(f"All available Google Gemini models: {final_model_list}")
            return final_model_list
        except Exception as e:
            print(f"Failed to get complete Google Gemini model list: {e}")
            return []

    def translate(self, text, target_language, model_name):
        if not self.api_key:
            return "Error: Google Gemini API key not set."
        
        model_to_use = f'models/{model_name}' if not model_name.startswith('models/') else model_name
        
        try:
            model = genai.GenerativeModel(model_to_use)
            prompt = f"""Translate the following text into {target_language}.

Rules to follow strictly:
1. Provide ONLY the translated text itself, without any explanations or remarks
2. Do not include the original text in your response
3. IMPORTANT: Do not translate any text between __KEYWORD_X__ markers (where X is a number)
4. Keep all __KEYWORD_X__ markers exactly as they appear in the original text
5. Maintain the exact same formatting and spacing around the keywords

Original text: {text}

Translated text:"""

            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            response = model.generate_content(prompt, safety_settings=safety_settings)
            if response and response.text and response.text.strip():
                return response.text.strip()
            else:
                error_msg = "Empty response from model"
                print(error_msg)
                return f"Error: {error_msg}"

        except Exception as e:
            error_msg = f"Translation error with model {model_name}: {str(e)}"
            print(error_msg)
            return f"Error: {error_msg}" 