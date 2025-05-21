from .base_llm import BaseLLM
import openai # Import actual OpenAI library

# Preferred latest OpenAI models order (for Chat Completions)
PREFERRED_OPENAI_MODELS_ORDER = [
    "gpt-4-turbo", # Generally one of the latest and most powerful models
    "gpt-4-turbo-preview", # If preview version exists
    "gpt-4o", # Latest Omni model
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
            print("OpenAI API key is not set.")
            return []
        try:
            models_response = self.client.models.list()
            available_models_from_api = {model.id for model in models_response.data}
            
            # Filter available models from API against preferred list and maintain order
            ordered_models = []
            for preferred_model_base in PREFERRED_OPENAI_MODELS_ORDER:
                # Find exact ID or model starting with base in API response
                # (e.g., "gpt-4-turbo-2024-04-09" starts with "gpt-4-turbo")
                found_model = None
                if preferred_model_base in available_models_from_api:
                    found_model = preferred_model_base
                else: # Partial match search (e.g., gpt-4-turbo-XYZ)
                    for api_model_id in available_models_from_api:
                        if api_model_id.startswith(preferred_model_base):
                            found_model = api_model_id
                            break
                if found_model and found_model not in ordered_models: # Prevent duplicates
                    ordered_models.append(found_model)

            # Add GPT models that support Chat Completions, are not instruct models, and not in preferred list
            other_gpt_models = sorted([
                model.id for model in models_response.data 
                if "gpt" in model.id and 
                   ("turbo" in model.id or "gpt-4" in model.id or model.id.startswith("gpt-3.5")) and 
                   not "instruct" in model.id and 
                   model.id not in ordered_models # Exclude already added preferred models
            ], reverse=True) # Rough sort by newest based on name

            final_model_list = ordered_models + other_gpt_models

            if not final_model_list:
                print("No suitable OpenAI models found after filtering. Returning default.")
                return ["gpt-3.5-turbo"] # Default for emergency
            
            print(f"Available OpenAI models (ordered): {final_model_list}")
            return final_model_list
        except Exception as e:
            print(f"Failed to get OpenAI model list: {e}")
            return ["gpt-3.5-turbo"] 

    def translate(self, text, target_language, model_name):
        if not self.api_key:
            return "Error: OpenAI API key not set."
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": f"""You are a helpful assistant that translates text into {target_language}. 
Follow these rules strictly:
1. Provide ONLY the translated text itself, without any additional explanations or remarks
2. Do not include the original text in your response
3. IMPORTANT: Do not translate any text between __KEYWORD_X__ markers (where X is a number)
4. Keep all __KEYWORD_X__ markers exactly as they appear in the original text
5. Maintain the exact same formatting and spacing around the keywords"""},
                    {"role": "user", "content": text}
                ],
                max_tokens=len(text) + 500,
                temperature=0.7,
            )
            translated_text = response.choices[0].message.content.strip()
            return translated_text
        except openai.APIError as e:
            print(f"OpenAI API Error ({model_name}): {e}")
            if "Invalid API key" in str(e) or (hasattr(e, 'http_status') and e.http_status == 401):
                 return "Error: OpenAI API key is not valid. Please check your API key."
            elif hasattr(e, 'http_status') and e.http_status == 429:
                 return "Error: OpenAI API rate limit exceeded. Please try again later or check your plan."
            error_message = str(e.message) if hasattr(e, 'message') else str(e)
            error_code = str(e.code) if hasattr(e, 'code') else 'N/A'
            return f"OpenAI API Error: {error_code} - {error_message}"
        except Exception as e:
            print(f"Translation failed with OpenAI ({model_name}): {e}")
            return f"Translation error with OpenAI: {e}" 