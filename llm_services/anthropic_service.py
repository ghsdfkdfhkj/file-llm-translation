# Anthropic API integration will be implemented here 
from .base_llm import BaseLLM
import anthropic # Import actual Anthropic library
import re # For version and date sorting

# List of known major Anthropic models
# Names include version and date for sorting
KNOWN_ANTHROPIC_MODELS = [
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "claude-3.5-sonnet-20240620", # Example of latest model (verify actual release)
    "claude-2.1",
    "claude-2.0",
    "claude-instant-1.2"
]

def anthropic_model_sort_key(model_name):
    # Example: claude-3-opus-20240229, claude-3.5-sonnet-20240620
    # 1. Claude version (3.5 > 3 > 2 > 1)
    # 2. Model size (opus > sonnet > haiku/instant)
    # 3. Date (newest first)
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
    
    # Sort by newest version, larger model, latest date (all descending, so use negative or not)
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
            print("Anthropic API key is not set.")
            return []
        try:
            # Currently, Anthropic library doesn't provide direct API for model listing.
            # Therefore, we use a hardcoded list and sort it.
            # Please refer to Anthropic documentation for actually available models.
            
            # Return sorted model list
            sorted_models = sorted(KNOWN_ANTHROPIC_MODELS, key=anthropic_model_sort_key)
            print(f"Available Anthropic models (sorted): {sorted_models}")
            return sorted_models
        except Exception as e:
            print(f"Error processing Anthropic model list: {e}")
            # In case of emergency, return unsorted list or minimal list
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
                        "content": f"""Translate the following text into {target_language}.

Rules to follow strictly:
1. Provide ONLY the translated text itself, without any explanations or remarks
2. Do not include the original text in your response
3. IMPORTANT: Do not translate any text between __KEYWORD_X__ markers (where X is a number)
4. Keep all __KEYWORD_X__ markers exactly as they appear in the original text
5. Maintain the exact same formatting and spacing around the keywords

Original text:
{text}

Translated text in {target_language}:"""
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
            print(f"Translation failed with Anthropic ({model_name}): {e}")
            return f"Translation error with Anthropic: {e}" 

    def get_completion(self, prompt, temperature=0.3):
        """
        Get a completion from Anthropic.
        
        Args:
            prompt (str): The prompt to send to the model
            temperature (float, optional): Controls randomness of output. Defaults to 0.3.
            
        Returns:
            str: The generated completion text
        """
        if not self.api_key:
            raise ValueError("API key is required for Anthropic")
        
        try:
            # Use the model that was set, or fall back to a default model
            model_name = self.model or 'claude-3-haiku-20240307'
            
            message = self.client.messages.create(
                model=model_name,
                max_tokens=4000,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return message.content[0].text
        except Exception as e:
            print(f"Error in Anthropic service: {e}")
            raise 