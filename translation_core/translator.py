from utils.file_handler import read_file # write_file is used directly in GUI or can be added to Translator if needed
from llm_services.openai_service import OpenAIService
from llm_services.anthropic_service import AnthropicService
from llm_services.google_gemini_service import GoogleGeminiService
import re
import unicodedata
import string
import warnings
import time
import random
import json

# Language detection libraries
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

# Use langdetect as the main detection library (based on Google's language-detection)
from langdetect import detect, DetectorFactory, detect_langs
from langdetect.detector_factory import LangDetectException

# Set seed for consistent language detection results
DetectorFactory.seed = 0

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langdetect")

# Mapping of supported LLM services
SUPPORTED_LLM_SERVICES = {
    "OpenAI": OpenAIService,
    "Anthropic": AnthropicService,
    "Google Gemini": GoogleGeminiService
}

# Default values for translation settings
DEFAULT_CHUNK_SIZE = 1000  # Default chunk size
MIN_CHUNK_SIZE = 100  # Minimum allowed chunk size
MAX_CHUNK_SIZE = 5000  # Maximum allowed chunk size
BASE_DELAY = 3  # Base delay in seconds
MAX_DELAY = 10 # Maximum delay in seconds
MAX_RETRIES = 5  # Maximum number of retries for failed requests (increased)
QUOTA_RETRY_MULTIPLIER = 2  # Additional multiplier for quota exceeded errors

def get_exponential_backoff(retry_count, api_retry_delay=None, jitter=True):
    """
    Calculate exponential backoff delay with optional jitter and API retry delay.
    
    Args:
        retry_count: Number of retry attempts so far
        api_retry_delay: Optional retry delay suggested by the API
        jitter: Whether to add random jitter
    """
    if api_retry_delay:
        # Use API's suggested delay as the base, but add some margin
        delay = api_retry_delay + (10 * retry_count)  # Increased margin
    else:
        # Standard exponential backoff
        delay = min(MAX_DELAY, BASE_DELAY * (2 ** retry_count))
    
    if jitter:
        # Add random jitter between 0-2 seconds
        delay += random.uniform(0, 2)
    
    return min(MAX_DELAY, delay)

def extract_retry_delay_from_error(error_str):
    """Extract retry delay from API error message if available."""
    try:
        if "retry_delay" in error_str:
            # Try to parse the JSON-like structure in the error message
            retry_info = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)', error_str)
            if retry_info:
                return int(retry_info.group(1))
    except:
        pass
    return None

def detect_language_advanced(text, confidence_threshold=0.3):  # Even lower threshold
    """
    Advanced language detection using langdetect (Google's language-detection based) 
    and textblob for maximum accuracy. More sensitive to catch all non-target languages.
    
    Args:
        text: Text to analyze
        confidence_threshold: Minimum confidence required
        
    Returns:
        tuple: (detected_language, confidence)
    """
    if not text.strip() or len(text.strip()) < 1:  # Accept even single characters
        return 'unknown', 0.0
    
    # Minimal text cleaning to preserve language characteristics
    clean_text = text.strip()
    # Only remove excessive whitespace, keep all other characters
    clean_text = ' '.join(clean_text.split())
    
    if len(clean_text) < 1:
        return 'unknown', 0.0
    
    results = []
    
    # Primary: Use langdetect with aggressive detection
    langdetect_results = []
    for _ in range(7):  # Even more attempts for maximum accuracy
        try:
            # Get detailed language probabilities
            lang_probs = detect_langs(clean_text)
            if lang_probs:
                # Consider top 3 languages for better coverage
                for lang_prob in lang_probs[:3]:
                    if lang_prob.prob > 0.1:  # Very low threshold
                        langdetect_results.append((lang_prob.lang, lang_prob.prob))
        except LangDetectException:
            pass
    
    # Use most consistent langdetect result
    if langdetect_results:
        # Get the most frequent language detection
        lang_counts = {}
        for lang, prob in langdetect_results:
            if lang in lang_counts:
                lang_counts[lang].append(prob)
            else:
                lang_counts[lang] = [prob]
        
        # Choose language with highest average probability
        best_lang = None
        best_avg_prob = 0
        for lang, probs in lang_counts.items():
            avg_prob = sum(probs) / len(probs)
            # Give bonus for consistency (same language detected multiple times)
            consistency_bonus = len(probs) * 0.03  # 3% bonus per detection
            final_prob = min(1.0, avg_prob + consistency_bonus)
            
            if final_prob > best_avg_prob:
                best_lang = lang
                best_avg_prob = final_prob
        
        if best_lang and best_avg_prob > 0.1:  # Very low minimum threshold
            # Boost confidence for longer texts and consistent detections
            confidence_boost = 0.1 if len(clean_text) > 8 else 0
            consistency_boost = 0.15 if len(set(r[0] for r in langdetect_results if r[0] == best_lang)) >= 3 else 0
            final_confidence = min(1.0, best_avg_prob + confidence_boost + consistency_boost)
            results.append((best_lang, final_confidence, 'langdetect'))
    
    # Secondary: TextBlob for verification (very aggressive)
    if TEXTBLOB_AVAILABLE and len(clean_text) > 1:  # Accept even very short text
        try:
            blob = TextBlob(clean_text)
            detected_lang = blob.detect_language()
            
            # Calculate confidence based on text characteristics and language patterns
            base_confidence = 0.4 if len(clean_text) > 5 else 0.2  # Lower base confidence
            
            # Boost confidence for specific language characteristics
            if detected_lang == 'ko' and any('\uAC00' <= c <= '\uD7A3' for c in clean_text):
                base_confidence += 0.5
            elif detected_lang == 'ja' and any('\u3040' <= c <= '\u309F' for c in clean_text):
                base_confidence += 0.5
            elif detected_lang == 'zh' and any('\u4E00' <= c <= '\u9FFF' for c in clean_text):
                base_confidence += 0.5
            elif detected_lang in ['en', 'de', 'fr', 'es', 'it', 'pl', 'ru', 'cs', 'sk', 'hr', 'sr', 'bg', 'sl', 'hu', 'ro', 'lt', 'lv', 'et'] and any(c.isalpha() and ord(c) < 256 for c in clean_text):
                base_confidence += 0.3
            
            confidence = min(1.0, base_confidence)
            if confidence > 0.1:  # Very low threshold for inclusion
                results.append((detected_lang, confidence, 'textblob'))
        except Exception:
            pass
    
    # Choose the best result
    if results:
        # If both detectors agree, boost confidence significantly
        if len(results) >= 2 and results[0][0] == results[1][0]:
            best_lang = results[0][0]
            combined_confidence = min(1.0, (results[0][1] + results[1][1]) / 2 + 0.25)  # Higher boost
            return best_lang, combined_confidence
        else:
            # Use the result with highest confidence
            results.sort(key=lambda x: x[1], reverse=True)
            return results[0][0], results[0][1]
    
    return 'unknown', 0.0

# Patterns to recognize as keywords
KEYWORD_PATTERNS = [
    r'`[^`]+`',  # Code surrounded by backticks
    r'<[^>]+>',  # HTML/XML tags
    r'#\w+',  # Hashtags
    r'@\w+',  # Mentions
    r'https?://\S+',  # URLs
    r'\b[A-Z][A-Z0-9_]*\b',  # Constants in all caps
    r'\b[A-Za-z]+\.[A-Za-z]+(?:\.[A-Za-z]+)*\b',  # Dot-separated identifiers
    r'\b(?:[a-zA-Z]+_){2,}[a-zA-Z]+\b',  # Underscore-separated identifiers with multiple parts
    r'\b[a-z]+_[a-z_]+_[a-z_]+(?::[0-9]+)?\b',  # Words with multiple underscores
    r'\b[a-z]+_[a-z_]+(?::[0-9]+)?\b',  # Words with underscores
    r'\b[a-z][a-z0-9_]*_[a-z0-9_]+\b',  # Words containing underscore
    r'(?<!["\'])\b\w+(?:\s*:(?:0|[1-9][0-9]*))(?=\s*["\'])',  # Keys in key:0 "value" format
    r'(?<!["\'])\b\w+(?:\s*:(?!//))(?=\s*["\'])',  # Keys in key-value pairs (not followed by //)
    r'(?<!["\'])\b\w+(?:\s*=(?!=))(?=\s*["\'])',  # Keys in key=value pairs (not ==)
    r'\b(?:Value|KEY|ID|NAME|TYPE|FIELD|PROPERTY|ATTRIBUTE|PARAMETER|VARIABLE|CONST|ENUM)\b',  # Common value placeholders
    r'\b[A-Z]+(?:_[A-Z]+)*_(?:VALUE|KEY|ID|NAME|TYPE)\b',  # Pattern like SOME_VALUE, CONFIG_KEY
    r'__KEYWORD_\d+__',  # Existing keyword placeholders
]

class Translator:
    def __init__(self, llm_provider_name, api_key):
        self.llm_service = None
        self.llm_provider_name = llm_provider_name
        self.api_key = api_key
        self.current_model = None
        self.chunk_size = DEFAULT_CHUNK_SIZE  # Add chunk_size as instance variable
        self._initialize_llm_service()
        self.keyword_pattern = '|'.join(KEYWORD_PATTERNS)
        
        # Define special tokens
        self.LINE_BREAK_TOKEN = "__LINE_BREAK_TOKEN_7f8a31c2__"
        self.KEY_VALUE_SEPARATOR = "__KEY_VALUE_SEP__"

    def set_chunk_size(self, size):
        """Set the chunk size for translation, with validation."""
        if size < MIN_CHUNK_SIZE:
            self.chunk_size = MIN_CHUNK_SIZE
            return f"Chunk size too small, using minimum size of {MIN_CHUNK_SIZE} characters"
        elif size > MAX_CHUNK_SIZE:
            self.chunk_size = MAX_CHUNK_SIZE
            return f"Chunk size too large, using maximum size of {MAX_CHUNK_SIZE} characters"
        else:
            self.chunk_size = size
            return f"Chunk size set to {size} characters"

    def get_chunk_size(self):
        """Get the current chunk size."""
        return self.chunk_size

    def _initialize_llm_service(self):
        if not self.api_key:
            # GUI already checks for API key, but handle defensively here too
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
                self.llm_service = None # Handle service initialization failure
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
        """Returns all available models (including non-latest versions)"""
        if self.llm_service:
            try:
                models = self.llm_service.get_all_models()
                print(f"All available models for {self.llm_provider_name}: {models}")
                return models
            except Exception as e:
                print(f"Error fetching all models from {self.llm_provider_name}: {e}")
                return self.get_available_models()  # Fallback: return at least latest models
        else:
            print("LLM service not initialized. Cannot fetch models.")
            return []

    def _split_text_into_chunks(self, lines, chunk_size=DEFAULT_CHUNK_SIZE):
        """Split lines into chunks, preserving line integrity."""
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line)
            
            # If there's a blank line, add it to current chunk 
            # (unless it would be the first line of a new chunk)
            if not line.strip() and current_chunk:
                current_chunk.append(line)
                current_size += line_size
                continue
                
            # If a single line exceeds chunk size, split it into multiple chunks
            if line_size > chunk_size:
                # If there is content in the current chunk, save it first
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_size = 0
                    
                # Process long lines as individual chunks
                chunks.append([line])
            # If adding the line to the current chunk exceeds the size, start a new chunk
            elif current_size + line_size > chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = [line]
                current_size = line_size
            # Add line to current chunk
            else:
                current_chunk.append(line)
                current_size += line_size
        
        # Add the last chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        # Double check that the key-value pairs don't get split across chunks
        # and that each chunk has an appropriate number of lines
        fixed_chunks = []
        for chunk in chunks:
            # Balance chunks with too few or too many lines
            if len(chunk) < 3 and len(fixed_chunks) > 0:
                # Merge very small chunks with the previous chunk
                fixed_chunks[-1].extend(chunk)
            elif len(chunk) > 50:
                # If a chunk is too large, split it further based on key-value patterns
                # Find good splitting points (like blank lines)
                split_points = []
                for i, line in enumerate(chunk):
                    if i > 0 and not line.strip():  # Find blank lines
                        split_points.append(i)
                
                if split_points and len(split_points) > 1:
                    # Calculate roughly equal segments
                    ideal_split = len(chunk) / (len(split_points) + 1)
                    best_splits = []
                    
                    # Try to find split points that create roughly equal segments
                    last_pos = 0
                    for i in range(1, len(split_points)):
                        if split_points[i] - last_pos >= ideal_split:
                            best_splits.append(split_points[i])
                            last_pos = split_points[i]
                    
                    # Split the chunk using the selected points
                    start = 0
                    for pos in best_splits:
                        fixed_chunks.append(chunk[start:pos])
                        start = pos
                    fixed_chunks.append(chunk[start:])
                else:
                    # If no good split points, just add the chunk
                    fixed_chunks.append(chunk)
            else:
                fixed_chunks.append(chunk)
        
        return fixed_chunks

    def _extract_keywords_smart(self, text):
        """
        Extract keywords from text and handle key-value pairs specially.
        Keys are preserved while values can be translated.
        """
        keywords = {}
        placeholder_counter = 0
        
        def replace_match(match):
            nonlocal placeholder_counter
            keyword_val = match.group(0)
            
            # Skip if it's already a placeholder
            if re.fullmatch(r"__KEYWORD_\d+__", keyword_val):
                return keyword_val
            
            # Special handling for common game file patterns (key:0 "value")
            if re.match(r'\w+:[0-9]', keyword_val):
                return keyword_val  # Keep these exactly as is
                
            # Special handling for key-value pairs
            if ':' in keyword_val or '=' in keyword_val:
                return keyword_val  # Keep the key as is
                
            placeholder = f"__KEYWORD_{placeholder_counter}__"
            keywords[placeholder] = keyword_val
            placeholder_counter += 1
            return placeholder
            
        # First pass: handle key-value pairs
        def handle_key_value_pairs(text):
            # Pattern for key-value pairs with quoted values
            kv_pattern = r'(\b\w+\s*(?::|=)\s*)(["\'][^"\']*["\'])'
            
            def replace_kv(match):
                key_part = match.group(1)  # This includes the : or =
                value_part = match.group(2)  # This includes the quotes
                
                # Extract the value content between quotes for translation
                value_content = value_part[1:-1]  # Remove quotes
                quote_char = value_part[0]  # Save quote character (' or ")
                
                # Check if value content is a placeholder that shouldn't be translated
                placeholder_indicators = ['Value', 'KEY', 'ID', 'NAME', 'TYPE', 'FIELD', 'PROPERTY', 
                                        'ATTRIBUTE', 'PARAMETER', 'VARIABLE', 'CONST', 'ENUM',
                                        'placeholder', 'example', 'sample', 'default']
                
                is_placeholder = any(indicator in value_content for indicator in placeholder_indicators)
                
                # Only mark the key part as a keyword (to preserve it)
                nonlocal placeholder_counter
                placeholder = f"__KEYWORD_{placeholder_counter}__"
                keywords[placeholder] = key_part
                placeholder_counter += 1
                
                # If value is a placeholder, protect it too
                if is_placeholder:
                    value_placeholder = f"__KEYWORD_{placeholder_counter}__"
                    keywords[value_placeholder] = value_part
                    placeholder_counter += 1
                    return f"{placeholder}{value_placeholder}"
                else:
                    # Return the placeholder for key and the original quoted value for translation
                    return f"{placeholder}{quote_char}{value_content}{quote_char}"
                
            return re.sub(kv_pattern, replace_kv, text)
            
        # Apply key-value handling first
        modified_text = handle_key_value_pairs(text)
        
        # Then apply other keyword patterns
        modified_text = re.sub(self.keyword_pattern, replace_match, modified_text)
        
        return modified_text, keywords

    def _restore_keywords(self, translated_text, keywords):
        """Restore original keywords in translated text"""
        # Replace placeholders with original keywords
        for placeholder, keyword in keywords.items():
            translated_text = translated_text.replace(placeholder, keyword)
            
        return translated_text

    def _reinitialize_llm_service(self):
        """Reinitialize the LLM service with current settings"""
        if self.llm_provider_name and self.api_key:
            service_class = SUPPORTED_LLM_SERVICES.get(self.llm_provider_name)
            if service_class:
                try:
                    # If there is an existing service, try closing it
                    if self.llm_service and hasattr(self.llm_service, 'close'):
                        try:
                            self.llm_service.close()
                        except:
                            pass  # Continue even if closing fails
                    
                    # Create a new service instance
                    self.llm_service = service_class(api_key=self.api_key)
                    return True
                except Exception as e:
                    print(f"Error reinitializing {self.llm_provider_name} service: {e}")
                    return False
        return False

    def translate_file(self, input_file_path, output_language, selected_model, chunk_size=None, progress_callback=None, update_callback=None):
        """
        Translate a file to the specified language using the selected LLM model.
        
        Args:
            input_file_path (str): Path to the input file
            output_language (str): Target language for translation
            selected_model (str): The model to use for translation
            chunk_size (int, optional): Override the default chunk size
            progress_callback (function, optional): Function to call with progress updates
            update_callback (function, optional): Function to call with intermediate results
            
        Returns:
            str: The translated text
        """
        # Set the current model
        self.current_model = selected_model
        
        if self.llm_service:
            self.llm_service.set_model(selected_model)
        
        # Read input file
        if progress_callback: progress_callback(f"Reading file: {input_file_path}")
        content = read_file(input_file_path)
        if content is None:
            message = f"Failed to read file: {input_file_path}"
            if progress_callback: progress_callback(message)
            return f"Error: {message}"

        if not content.strip():
            message = "Input file is empty."
            if progress_callback: progress_callback(message)
            return "" # Return empty content for empty file

        # Split file into lines
        lines = content.splitlines(True)  # Keep newline characters
        
        # Use provided chunk size or instance chunk size
        actual_chunk_size = chunk_size if chunk_size is not None else self.chunk_size
        
        # Validate chunk size
        validation_message = self.set_chunk_size(actual_chunk_size)
        if progress_callback: progress_callback(validation_message)
        actual_chunk_size = self.chunk_size  # Use validated chunk size
        
        # Create chunks split by lines
        chunks = self._split_text_into_chunks(lines, actual_chunk_size)
        translated_lines_all = []
        total_chunks = len(chunks)
        failed_chunks = []  # Track failed chunks for reporting
        quota_exceeded = False  # Track if we hit quota limits

        if progress_callback: 
            progress_callback(f"Starting translation of {total_chunks} chunk(s) using {self.llm_provider_name} ({selected_model})")
            progress_callback(f"Using chunk size: {actual_chunk_size} characters")

        for i, chunk_lines in enumerate(chunks):
            # Check if we've hit quota limits
            if quota_exceeded:
                if progress_callback:
                    progress_callback(f"Skipping remaining chunks due to API quota limits. Will retry later.")
                failed_chunks.extend(range(i+1, total_chunks+1))
                translated_lines_all.extend(chunk_lines)  # Keep original content
                continue

            # Add initial delay between chunks
            if i > 0:
                time.sleep(BASE_DELAY)
            
            # Retry logic for failed requests
            retries = 0
            success = False
            last_error = None
            
            while not success and retries < MAX_RETRIES:
                try:
                    # Reinitialize LLM service for each chunk
                    if not self._reinitialize_llm_service():
                        error_message = f"[CHUNK_ERROR:{i+1}] Failed to reinitialize LLM service"
                        if progress_callback: progress_callback(error_message)
                        failed_chunks.append(i+1)
                        translated_lines_chunk = chunk_lines
                        translated_lines_all.extend(translated_lines_chunk)
                        break

                    if progress_callback:
                        progress_callback(f"Translating chunk {i + 1}/{total_chunks}...")
                        if retries > 0:
                            progress_callback(f"Retry attempt {retries + 1} for chunk {i + 1}")
                    
                    translated_lines_chunk = [] # Use a temporary list for the current chunk's lines
                    
                    # Translate each line within the chunk
                    if len(chunk_lines) == 1:
                        line = chunk_lines[0]
                        # If the line is empty or contains only whitespace, add it as is
                        if not line.strip():
                            translated_lines_chunk.append(line)
                        else:
                            # Separate leading whitespace
                            match = re.match(r"(\s*)(.*)", line, re.DOTALL)
                            leading_space = match.group(1) if match else ""
                            content_to_translate = match.group(2) if match else line

                            if not content_to_translate.strip(): # If there is no content after removing leading whitespace
                                translated_lines_chunk.append(line)
                            else:
                                # Extract keywords (excluding those inside quotes) and replace with placeholders
                                modified_content, keywords = self._extract_keywords_smart(content_to_translate)
                                
                                # Log the content being sent for translation if there's a callback
                                if progress_callback:
                                    progress_callback(f"Processing content (chunk {i + 1}): {modified_content[:100]}...")
                                
                                # Simplified instruction for single lines
                                single_line_instruction = f"""You are a professional translator. Translate the following text to {output_language} with these STRICT requirements:

PRESERVATION RULES (NEVER translate these):
- Keep __KEYWORD_X__ placeholders exactly as they are
- Keep technical identifiers like file_name:0, config_key, etc.
- Keep symbols : = exactly as they are
- Keep words like Value, KEY, ID, NAME, TYPE unchanged when they are placeholders
- Keep all formatting, punctuation, and special characters

TRANSLATION RULES:
- Only translate actual content text, especially text in quotes
- For quoted strings: translate the content but keep the quote marks
- For proper nouns without standard translations: use phonetic transliteration in {output_language}
- Maintain natural fluency in {output_language}
- Keep the same meaning and tone as the original

Text to translate:
{modified_content}

Expected output: Translated text with all technical elements preserved exactly."""
                                
                                text_for_llm = single_line_instruction
                                
                                try:
                                    translated_content = self.llm_service.translate(text_for_llm, output_language, selected_model)
                                    
                                    # Remove instruction from translated text if it was included
                                    if "Translate the following text to" in translated_content:
                                        instruction_end = translated_content.find("Text to translate:")
                                        if instruction_end > 0:
                                            translated_content = translated_content[instruction_end + len("Text to translate:"):].strip()
                                    
                                    # Restore keywords
                                    if "Translation error:" in translated_content or "Error:" in translated_content:
                                        error_message = f"[CHUNK_ERROR:{i+1}] Error translating line: {translated_content}"
                                        if progress_callback: progress_callback(error_message)
                                        failed_chunks.append(i+1)
                                        translated_lines_chunk.append(line)  # Keep original line on error
                                    else:
                                        restored_content = self._restore_keywords(translated_content, keywords)
                                        translated_lines_chunk.append(leading_space + restored_content)
                                except Exception as e:
                                    error_message = f"[LINE_ERROR:{i+1}] Exception: {str(e)}"
                                    if progress_callback: progress_callback(error_message)
                                    translated_lines_chunk.append(line)  # Keep original line on error
                    else:
                        # If there are multiple lines, save leading whitespace, content, and newline characters
                        original_lines_info = []
                        for line_in_chunk in chunk_lines:
                            match = re.match(r"(\s*)(.*?)(\r?\n)?$", line_in_chunk, re.DOTALL)
                            leading_s = match.group(1) if match and match.group(1) else ""
                            content_p = match.group(2) if match and match.group(2) else ""
                            line_e = match.group(3) if match and match.group(3) else ""
                            original_lines_info.append({'leading': leading_s, 'content': content_p, 'ending': line_e})

                        # When joining with LINE_BREAK_TOKEN, use only the content part (without newlines)
                        chunk_text_to_translate = self.LINE_BREAK_TOKEN.join(info['content'] for info in original_lines_info)
                        
                        # Include metadata about the original text structure
                        line_count = len(original_lines_info)
                        
                        modified_chunk_text, keywords = self._extract_keywords_smart(chunk_text_to_translate)
                        
                        # Log the content being sent for translation if there's a callback
                        if progress_callback:
                            progress_callback(f"Processing multi-line content (chunk {i + 1}): {modified_chunk_text[:100]}...")
                        
                        # Simple but specific instructions
                        multi_line_instruction = f"""You are a professional translator. Translate the following text to {output_language} with these STRICT requirements:

PRESERVATION RULES (NEVER translate these):
- Keep technical identifiers like file_name:0, config_key, etc.
- Keep symbols : = exactly as they are
- Keep words like Value, KEY, ID, NAME, TYPE unchanged when they are placeholders
- Keep all formatting, punctuation, and special characters

TRANSLATION RULES:
- Only translate actual content text, especially text in quotes
- For quoted strings: translate the content but keep the quote marks
- For proper nouns without standard translations: use phonetic transliteration in {output_language}
- Maintain natural fluency in {output_language}
- Keep the same meaning and tone as the original
- Preserve the exact structure and line organization

Text to translate:
{modified_chunk_text}

Expected output: Translated text with all technical elements and structure preserved exactly."""

                        # Replace the previous direct translation with improved instruction
                        translated_chunk_text = self.llm_service.translate(multi_line_instruction, output_language, selected_model)
                        
                        # Check for translation errors
                        if "Translation error:" in translated_chunk_text or "Error:" in translated_chunk_text:
                            error_message = f"[CHUNK_ERROR:{i+1}] Error translating chunk: {translated_chunk_text}"
                            if progress_callback: progress_callback(error_message)
                            failed_chunks.append(i+1)
                            translated_lines_chunk.extend(chunk_lines)  # Keep original chunk on error
                            continue  # Skip to the next chunk
                        
                        # Process the translation result
                        try:
                            # Remove instruction part from the response
                            if "Translate the following text to" in translated_chunk_text:
                                instruction_end = translated_chunk_text.find("Text to translate:")
                                if instruction_end > 0:
                                    translated_chunk_text = translated_chunk_text[instruction_end + len("Text to translate:"):].strip()
                            
                            # Restore keywords first
                            restored_chunk_text = self._restore_keywords(translated_chunk_text, keywords)
                            
                            # Split by line break tokens more carefully
                            if self.LINE_BREAK_TOKEN in restored_chunk_text:
                                translated_segments = restored_chunk_text.split(self.LINE_BREAK_TOKEN)
                            else:
                                # Fallback: try to split by actual newlines
                                translated_segments = restored_chunk_text.split('\n')
                            
                            # Process each line with its original formatting
                            num_original_lines = len(original_lines_info)
                            
                            # Ensure we have exactly the right number of segments
                            while len(translated_segments) < num_original_lines:
                                translated_segments.append("")
                            
                            # If we have too many segments, only take what we need
                            if len(translated_segments) > num_original_lines:
                                translated_segments = translated_segments[:num_original_lines]
                            
                            # Process each line with its original formatting preserved
                            for j in range(num_original_lines):
                                leading_space = original_lines_info[j]['leading']
                                line_ending = original_lines_info[j]['ending']
                                
                                # If original line was empty, keep it empty
                                if not original_lines_info[j]['content'].strip():
                                    translated_lines_chunk.append(leading_space + line_ending)
                                else:
                                    # Clean the translated segment and preserve original formatting
                                    translated_content = translated_segments[j].strip() if j < len(translated_segments) else ""
                                    translated_lines_chunk.append(leading_space + translated_content + line_ending)
                        
                        except Exception as e:
                            error_message = f"[CHUNK_ERROR:{i+1}] Error processing translation result: {str(e)}"
                            if progress_callback: progress_callback(error_message)
                            # Keep original in case of error
                            translated_lines_chunk.extend(chunk_lines)

                    translated_lines_all.extend(translated_lines_chunk)
                    
                    # Update translation results in real-time
                    if update_callback:
                        current_translation = "".join(translated_lines_all)
                        update_callback(current_translation)

                    success = True  # If we get here without exceptions, translation was successful
                    
                except Exception as e:
                    last_error = str(e)
                    retries += 1

                    # Check for quota exceeded error
                    if "quota" in last_error.lower() or "rate limit" in last_error.lower():
                        if retries < MAX_RETRIES:
                            api_retry_delay = extract_retry_delay_from_error(last_error)
                            # Use shorter wait times for retranslation to be more responsive
                            base_wait = get_exponential_backoff(retries, api_retry_delay)
                            wait_time = min(base_wait * QUOTA_RETRY_MULTIPLIER, 60)  # Cap at 60 seconds max
                            if progress_callback:
                                progress_callback(f"API quota exceeded for chunk {i + 1}, waiting {wait_time:.1f}s...")
                            time.sleep(wait_time)
                        else:
                            quota_exceeded = True
                            failed_chunks.append(i+1)
                            translated_lines_all.extend(chunk_lines)
                            break
                    else:
                        # Handle other errors
                        if retries < MAX_RETRIES:
                            wait_time = get_exponential_backoff(retries)
                            if progress_callback:
                                progress_callback(f"Translation error for chunk {i + 1}, waiting {wait_time:.1f}s before retry...")
                            time.sleep(wait_time)
                        else:
                            if progress_callback:
                                progress_callback(f"Failed to translate chunk {i + 1} after {MAX_RETRIES} attempts: {str(last_error)}")
                            failed_chunks.append(i+1)
                            translated_lines_all.extend(chunk_lines)  # Keep original on final failure
            
            # Report progress with quality metrics more frequently
            if i % 2 == 0 or i == len(chunks) - 1:  # Update every 2 chunks or at the end
                progress_percent = 10 + ((i + 1) / len(chunks)) * 80  # Fixed base_progress issue
                if progress_callback:
                    progress_callback(f"Progress: {progress_percent:.1f}% | Chunk {i + 1}/{len(chunks)}")
        
        # Final quality report
        if progress_callback:
            progress_callback("Translation completed!")
        
        # Report final status with more detail about quota issues
        if quota_exceeded:
            if progress_callback:
                progress_callback(f"Translation partially completed. {len(failed_chunks)} chunks skipped due to API quota limits.")
                progress_callback("Consider retrying the translation after the API quota resets or reducing chunk size.")
        elif failed_chunks:
            if progress_callback:
                progress_callback(f"Translation completed with {len(failed_chunks)} failed chunks (chunks: {', '.join(map(str, failed_chunks))})")
        else:
            if progress_callback: 
                progress_callback("Translation completed successfully.")
            
        # Combine all translated lines
        full_translated_text = "".join(translated_lines_all)
        return full_translated_text

    def detect_untranslated_sections(self, translated_text, target_language):
        """
        Enhanced detection that identifies any content not in the target language.
        Works dynamically with any target language without hardcoded mappings.
        
        Args:
            translated_text (str): The translated text to check
            target_language (str): The target language name
            
        Returns:
            dict: Contains 'untranslated_lines', 'stats', and 'confidence_scores'
        """
        lines = translated_text.split('\n')
        untranslated_lines = []
        confidence_scores = []
        stats = {
            'total_lines': len(lines),
            'non_empty_lines': 0,
            'keyword_only_lines': 0,
            'untranslated_lines': 0,
            'confidence_avg': 0.0,
            'quoted_content_analyzed': 0,
            'quoted_untranslated': 0,
            'detected_languages': {}  # Track all detected languages
        }
        
        # First, try to determine the target language code from the target language name
        target_lang_code = self._get_target_language_code(target_language)
        
        def extract_quoted_content(text):
            """Extract content from quoted strings, supporting both single and double quotes."""
            quoted_contents = []
            # Pattern to match quoted strings (both single and double quotes)
            quote_patterns = [
                r'"([^"]*)"',  # Double quotes
                r"'([^']*)'"   # Single quotes
            ]
            
            for pattern in quote_patterns:
                matches = re.findall(pattern, text)
                quoted_contents.extend(matches)
            
            return quoted_contents
        
        def is_target_language(text, confidence_threshold=0.3):  # Lowered threshold even more
            """
            Check if text is in the target language using dynamic language detection.
            Returns True only if the detected language matches the target language.
            More strict approach - when in doubt, mark as untranslated.
            """
            if not text.strip() or len(text.strip()) < 1:  # Accept even single characters
                return True, 1.0  # Empty text is considered "correct"
            
            # Don't skip keyword checking - but make it more precise
            if self._is_mostly_keywords(text):
                return True, 1.0
            
            # Detect the actual language of the text with multiple attempts for better accuracy
            detected_languages = []
            
            # Try detection multiple times for consistency, but more aggressively
            for attempt in range(3):  # 3 attempts for stability
                detected_lang, detection_confidence = detect_language_advanced(text, confidence_threshold)
                if detected_lang != 'unknown':
                    detected_languages.append((detected_lang, detection_confidence))
            
            # Choose the most consistent result
            if detected_languages:
                # If we have multiple detections, use the most confident one
                detected_languages.sort(key=lambda x: x[1], reverse=True)
                detected_lang, detection_confidence = detected_languages[0]
            else:
                detected_lang, detection_confidence = 'unknown', 0.0
            
            # Track detected languages for statistics
            if detected_lang != 'unknown':
                if detected_lang in stats['detected_languages']:
                    stats['detected_languages'][detected_lang] += 1
                else:
                    stats['detected_languages'][detected_lang] = 1
            
            # More aggressive detection - assume untranslated unless we're confident it's target language
            if detected_lang == 'unknown':
                # For unknown languages, check if it could be target language by character patterns
                could_be_target = self._could_be_target_language(text, target_lang_code)
                if could_be_target:
                    return True, 0.2  # Low confidence but acceptable
                else:
                    return False, 0.1  # Likely not target language
            elif detection_confidence < confidence_threshold:
                # Low confidence - be more cautious
                # Check if detected language matches target
                is_target = self._is_same_language(detected_lang, target_lang_code, target_language)
                if is_target:
                    return True, detection_confidence
                else:
                    return False, detection_confidence  # Different language detected with low confidence
            else:
                # High confidence detection
                # Check if detected language matches target language
                is_target = self._is_same_language(detected_lang, target_lang_code, target_language)
                
                if is_target:
                    return True, detection_confidence
                else:
                    # Detected a different language with high confidence - definitely untranslated
                    return False, detection_confidence
        
        # Analyze each line
        total_confidence = 0.0
        analyzed_lines = 0
        
        for i, line in enumerate(lines):
            if line.strip():
                stats['non_empty_lines'] += 1
                
                if self._is_mostly_keywords(line):
                    stats['keyword_only_lines'] += 1
                    continue
                
                # Extract quoted content for focused analysis
                quoted_contents = extract_quoted_content(line)
                line_is_untranslated = False
                line_confidence = 1.0
                
                if quoted_contents:
                    # Analyze quoted content specifically
                    stats['quoted_content_analyzed'] += 1
                    quoted_confidences = []
                    
                    for quoted_text in quoted_contents:
                        if quoted_text.strip() and len(quoted_text.strip()) >= 3:  # Skip very short quotes
                            is_correct_lang, confidence = is_target_language(quoted_text)
                            quoted_confidences.append(confidence)
                            
                            if not is_correct_lang:
                                line_is_untranslated = True
                                stats['quoted_untranslated'] += 1
                    
                    # Use average confidence of quoted content
                    if quoted_confidences:
                        line_confidence = sum(quoted_confidences) / len(quoted_confidences)
                    else:
                        line_confidence = 1.0  # No meaningful quoted content to analyze
                else:
                    # No quoted content, analyze the entire line
                    is_correct_lang, line_confidence = is_target_language(line)
                    if not is_correct_lang:
                        line_is_untranslated = True
                
                confidence_scores.append((i, line_confidence))
                total_confidence += line_confidence
                analyzed_lines += 1
                
                if line_is_untranslated:
                    untranslated_lines.append((i, line))
                    stats['untranslated_lines'] += 1
        
        # Calculate average confidence
        if analyzed_lines > 0:
            stats['confidence_avg'] = total_confidence / analyzed_lines
        
        # Return comprehensive results
        return {
            'untranslated_lines': untranslated_lines,
            'stats': stats,
            'confidence_scores': confidence_scores
        }
    
    def _get_target_language_code(self, target_language):
        """
        Dynamically determine the language code for the target language.
        Uses language detection on the target language name itself.
        """
        # Try to detect the language code from common patterns
        target_language_lower = target_language.lower()
        
        # Common language name patterns
        if any(word in target_language_lower for word in ['korean', '한국어', '한국말']):
            return 'ko'
        elif any(word in target_language_lower for word in ['japanese', '일본어', '日本語']):
            return 'ja'
        elif any(word in target_language_lower for word in ['chinese', '중국어', '中文', 'mandarin']):
            return 'zh'
        elif any(word in target_language_lower for word in ['english', '영어']):
            return 'en'
        elif any(word in target_language_lower for word in ['spanish', 'español']):
            return 'es'
        elif any(word in target_language_lower for word in ['french', 'français']):
            return 'fr'
        elif any(word in target_language_lower for word in ['german', 'deutsch']):
            return 'de'
        elif any(word in target_language_lower for word in ['russian', 'русский']):
            return 'ru'
        elif any(word in target_language_lower for word in ['vietnamese', 'tiếng việt']):
            return 'vi'
        elif any(word in target_language_lower for word in ['thai', 'ไทย']):
            return 'th'
        elif any(word in target_language_lower for word in ['indonesian', 'bahasa indonesia']):
            return 'id'
        else:
            # For unknown languages, try to detect from a sample text in that language
            # or use the first two characters as language code
            return target_language_lower[:2]
    
    def _is_same_language(self, detected_lang, target_lang_code, target_language):
        """
        Check if the detected language matches the target language.
        Handles language variants and aliases.
        """
        if not detected_lang or not target_lang_code:
            return False
        
        detected_lang = detected_lang.lower()
        target_lang_code = target_lang_code.lower()
        
        # Direct match
        if detected_lang == target_lang_code:
            return True
        
        # Handle Chinese variants
        if target_lang_code == 'zh' and detected_lang in ['zh', 'zh-cn', 'zh-tw']:
            return True
        if detected_lang == 'zh' and target_lang_code in ['zh-cn', 'zh-tw']:
            return True
        
        # Handle language aliases
        language_aliases = {
            'ko': ['korean'],
            'ja': ['japanese'],
            'zh': ['chinese', 'mandarin'],
            'en': ['english'],
            'es': ['spanish'],
            'fr': ['french'],
            'de': ['german'],
            'ru': ['russian'],
            'vi': ['vietnamese'],
            'th': ['thai'],
            'id': ['indonesian']
        }
        
        # Check if detected language is an alias of target language
        target_aliases = language_aliases.get(target_lang_code, [])
        if detected_lang in target_aliases:
            return True
        
        # Check reverse mapping
        for lang_code, aliases in language_aliases.items():
            if detected_lang == lang_code and target_lang_code in aliases:
                return True
        
        return False
    
    def _is_mostly_keywords(self, text):
        """
        Check if a line consists mostly of keywords that shouldn't be translated.
        More precise detection to avoid skipping translatable content.
        """
        if not text or not text.strip():
            return True
        
        text = text.strip()
        
        # Quick check: if it's purely punctuation or very short, skip detailed analysis
        if len(text) <= 2 or not any(c.isalpha() for c in text):
            return True
        
        # Check for quoted content first - quoted content should usually be translated
        quoted_content = []
        quote_patterns = [r'"([^"]*)"', r"'([^']*)'"]
        for pattern in quote_patterns:
            matches = re.findall(pattern, text)
            quoted_content.extend(matches)
        
        # If there's substantial quoted content with real words, don't skip
        for quote in quoted_content:
            if len(quote.strip()) > 2 and any(c.isalpha() for c in quote):
                # Check if quoted content looks like real language (not just codes)
                alpha_chars = sum(1 for c in quote if c.isalpha())
                non_alpha_chars = len(quote) - alpha_chars
                if alpha_chars > 3 and alpha_chars > non_alpha_chars:
                    return False  # Has substantial translatable quoted content
        
        # Check keywords in the text, but be more precise
        keywords = re.findall(self.keyword_pattern, text)
        
        # Calculate what percentage of meaningful content consists of keywords
        meaningful_chars = sum(1 for c in text if c.isalnum() or c in ' \'"')
        keyword_chars = sum(len(kw) for kw in keywords)
        
        if meaningful_chars == 0:
            return True
        
        keyword_ratio = keyword_chars / meaningful_chars
        
        # More conservative threshold - only skip if it's overwhelmingly keywords
        if keyword_ratio > 0.8:  # Increased from 0.6 to 0.8
            return True
        
        # Additional check: if it contains certain patterns, it's likely technical
        technical_patterns = [
            r'^[A-Z_][A-Z0-9_]*$',  # ALL_CAPS identifiers
            r'^[a-z_][a-z0-9_]*:[0-9]+$',  # key:number patterns
            r'^__[A-Z_]+__$',  # __KEYWORD__ patterns
            r'^[a-zA-Z_][a-zA-Z0-9_]*\s*[:=]\s*[0-9]+$',  # variable assignments
        ]
        
        for pattern in technical_patterns:
            if re.match(pattern, text.strip()):
                return True
        
        return False
    
    def retranslate_untranslated_sections(self, translated_text, untranslated_lines, output_language, 
                                          selected_model, progress_callback=None):
        """
        Retranslate only the untranslated sections of the text with optimized performance.
        
        Args:
            translated_text (str): The original translated text
            untranslated_lines (list): List of (line_index, original_line) tuples that need retranslation
                                    OR detection results dict from detect_untranslated_sections
            output_language (str): The target language
            selected_model (str): The model to use for translation
            progress_callback (function): Callback function to report progress
            
        Returns:
            str: The updated translated text with retranslated sections
        """
        # Handle both old and new format inputs
        if isinstance(untranslated_lines, dict):
            # New format: extract untranslated_lines from detection results
            actual_untranslated_lines = untranslated_lines['untranslated_lines']
            stats = untranslated_lines.get('stats', {})
            if progress_callback:
                progress_callback(f"Processing {len(actual_untranslated_lines)} untranslated sections...")
        else:
            # Old format: direct list
            actual_untranslated_lines = untranslated_lines
            stats = {}
        
        if not actual_untranslated_lines:
            if progress_callback:
                progress_callback("No untranslated sections to process.")
            return translated_text
            
        # Set the selected model
        if selected_model != self.current_model:
            self.current_model = selected_model
            if self.llm_service:
                self.llm_service.set_model(selected_model)
        
        # Split the text into lines for easy replacement
        lines = translated_text.split('\n')
        
        # Store original line formatting (leading whitespace)
        original_line_formats = {}
        for line_idx, line in actual_untranslated_lines:
            if line_idx < len(lines):
                # Extract leading whitespace from original line
                match = re.match(r'(\s*)(.*)', lines[line_idx])
                leading_space = match.group(1) if match else ""
                original_line_formats[line_idx] = leading_space
        
        total_lines = len(actual_untranslated_lines)
        
        # Enhanced chunking strategy for better translation quality and performance
        chunks = []
        current_chunk = []
        current_indices = []
        max_chunk_size = 8  # Increased chunk size to reduce API calls
        max_chars_per_chunk = 800  # Add character limit to respect API limits
        
        # Initial progress update
        if progress_callback:
            progress_callback("Progress: 5% | Organizing content for retranslation...")
        
        for i, (line_idx, line) in enumerate(actual_untranslated_lines):
            current_chunk_chars = sum(len(l) for l in current_chunk)
            
            if not current_chunk:
                current_chunk.append(line)
                current_indices.append(line_idx)
            elif (len(current_chunk) < max_chunk_size and 
                  current_chunk_chars + len(line) < max_chars_per_chunk):
                # Add to current chunk if size and character limits allow
                current_chunk.append(line)
                current_indices.append(line_idx)
            else:
                # Start a new chunk
                chunks.append((current_indices, current_chunk))
                current_chunk = [line]
                current_indices = [line_idx]
                
            # More frequent progress updates during organization
            if i % 20 == 0 and progress_callback:  # Less frequent updates
                org_progress = 5 + (i / total_lines) * 10  # 5-15% for organization
                progress_callback(f"Progress: {org_progress:.1f}% | Organizing content: {i + 1}/{total_lines} lines processed")
        
        # Add the last chunk
        if current_chunk:
            chunks.append((current_indices, current_chunk))
        
        if progress_callback:
            progress_callback(f"Progress: 15% | Created {len(chunks)} translation chunks (avg {total_lines/len(chunks):.1f} lines per chunk). Starting retranslation...")
        
        # Track translation results for quality assessment
        successful_translations = 0
        failed_translations = 0
        quota_exceeded = False
        
        # Now translate each chunk with enhanced context and frequent updates
        for i, (indices, chunk) in enumerate(chunks):
            # Check for quota exceeded
            if quota_exceeded:
                failed_translations += len(chunks) - i
                if progress_callback:
                    progress_callback(f"Skipping remaining {len(chunks) - i} chunks due to API quota limits")
                break
                
            # Calculate current progress (15% to 95% for translation)
            base_progress = 15
            translation_progress = (i / len(chunks)) * 80
            current_progress = base_progress + translation_progress
            
            if progress_callback:
                progress_callback(f"Progress: {current_progress:.1f}% | Translating chunk {i + 1}/{len(chunks)}...")
            
            # Retry logic for retranslation chunks
            retries = 0
            chunk_success = False
            
            while not chunk_success and retries < MAX_RETRIES:
                try:
                    # Provide surrounding context for better translation
                    context_lines = []
                    for idx in indices:
                        # Add a few lines before and after for context
                        start_context = max(0, idx - 2)
                        end_context = min(len(lines), idx + 3)
                        
                        context_chunk = []
                        for ctx_idx in range(start_context, end_context):
                            if ctx_idx == idx:
                                context_chunk.append(f">>> {lines[ctx_idx]} <<<")  # Mark target line
                            else:
                                context_chunk.append(lines[ctx_idx])
                        context_lines.append('\n'.join(context_chunk))
                        break  # Use context from first line only to avoid confusion
                    
                    chunk_text = '\n'.join(chunk)
                    
                    if len(chunk) == 1 and context_lines:
                        # Single line with context
                        prompt = f"""You are a professional translator. The following content was previously poorly translated to {output_language}. Please retranslate it correctly.

Context (the line marked with >>> <<< needs retranslation):
{context_lines[0]}

PRESERVATION RULES (NEVER translate these):
- Keep technical identifiers like file_name:0, config_key, etc.
- Keep symbols : = exactly as they are
- Keep words like Value, KEY, ID, NAME, TYPE unchanged when they are placeholders
- Keep all formatting, punctuation, and special characters

TRANSLATION RULES:
- Only translate actual content text, especially text in quotes
- For quoted strings: translate the content but keep the quote marks
- For proper nouns without standard translations: use phonetic transliteration in {output_language}
- Maintain natural fluency in {output_language}
- Keep the same meaning and tone as the original
- Output exactly {len(chunk)} lines (one translation per input line)
- Maintain the same line structure and numbering
- Do not merge or split lines

Expected output: {len(chunk)} correctly translated lines with all technical elements preserved."""
                    else:
                        # Multiple lines - more efficient batch processing
                        prompt = f"""You are a professional translator. The following content was previously poorly translated to {output_language}. Please retranslate it correctly.

Content to retranslate (each line should be translated separately):
{chunk_text}

PRESERVATION RULES (NEVER translate these):
- Keep technical identifiers like file_name:0, config_key, etc.
- Keep symbols : = exactly as they are
- Keep words like Value, KEY, ID, NAME, TYPE unchanged when they are placeholders
- Keep all formatting, punctuation, and special characters

TRANSLATION RULES:
- Only translate actual content text, especially text in quotes
- For quoted strings: translate the content but keep the quote marks
- For proper nouns without standard translations: use phonetic transliteration in {output_language}
- Maintain natural fluency in {output_language}
- Keep the same meaning and tone as the original
- Output exactly {len(chunk)} lines (one translation per input line)
- Maintain the same line structure and numbering
- Do not merge or split lines

Expected output: {len(chunk)} correctly translated lines with all technical elements preserved."""
                    
                    # Get translation from LLM with enhanced error handling
                    response = self.llm_service.get_completion(prompt)
                    translated_chunk = response.strip()
                    
                    # Clean up the response
                    if ">>>" in translated_chunk or "<<<" in translated_chunk:
                        # Remove context markers if they appear in response
                        translated_chunk = translated_chunk.replace(">>>", "").replace("<<<", "").strip()
                    
                    # Split the translated chunk into lines
                    translated_lines = translated_chunk.split('\n')
                    
                    # Handle line count mismatch
                    if len(translated_lines) != len(indices):
                        if len(translated_lines) == 1 and len(indices) == 1:
                            # Single line translation - this is fine
                            line_idx = indices[0]
                            leading_space = original_line_formats.get(line_idx, "")
                            lines[line_idx] = leading_space + translated_lines[0].strip()
                            successful_translations += 1
                        elif len(translated_lines) > len(indices):
                            # More lines returned than expected - use first N lines
                            for j, idx in enumerate(indices):
                                if j < len(translated_lines):
                                    leading_space = original_line_formats.get(idx, "")
                                    lines[idx] = leading_space + translated_lines[j].strip()
                            successful_translations += 1
                    else:
                        # Perfect match - update each line with preserved formatting
                        for j, idx in enumerate(indices):
                            leading_space = original_line_formats.get(idx, "")
                            lines[idx] = leading_space + translated_lines[j].strip()
                        successful_translations += 1
                    
                    chunk_success = True
                    
                except Exception as translation_error:
                    error_str = str(translation_error)
                    retries += 1
                    
                    # Check for quota exceeded error
                    if "quota" in error_str.lower() or "rate limit" in error_str.lower():
                        if retries < MAX_RETRIES:
                            api_retry_delay = extract_retry_delay_from_error(error_str)
                            # Use shorter wait times for retranslation to be more responsive
                            base_wait = get_exponential_backoff(retries, api_retry_delay)
                            wait_time = min(base_wait * QUOTA_RETRY_MULTIPLIER, 60)  # Cap at 60 seconds max
                            if progress_callback:
                                progress_callback(f"API quota exceeded for chunk {i + 1}, waiting {wait_time:.1f}s...")
                            time.sleep(wait_time)
                        else:
                            quota_exceeded = True
                            break
                    else:
                        # Handle other errors
                        if retries < MAX_RETRIES:
                            wait_time = get_exponential_backoff(retries)
                            if progress_callback:
                                progress_callback(f"Translation error for chunk {i + 1}, waiting {wait_time:.1f}s before retry...")
                            time.sleep(wait_time)
                        else:
                            # Try simpler fallback translation
                            try:
                                simple_prompt = f"""Translate to {output_language}. PRESERVE technical identifiers, symbols, and placeholder words like Value, KEY, ID exactly as they are. Only translate actual content: {chunk_text}"""
                                fallback_response = self.llm_service.get_completion(simple_prompt)
                                
                                if fallback_response and len(fallback_response.strip()) > 0:
                                    line_idx = indices[0]
                                    leading_space = original_line_formats.get(line_idx, "")
                                    lines[line_idx] = leading_space + fallback_response.strip()
                                    successful_translations += 1
                                    chunk_success = True
                                else:
                                    failed_translations += 1
                            except:
                                failed_translations += 1
            
            # Report progress with quality metrics more frequently
            if i % 2 == 0 or i == len(chunks) - 1:  # Update every 2 chunks or at the end
                progress_percent = base_progress + ((i + 1) / len(chunks)) * 80
                if progress_callback:
                    progress_callback(f"Progress: {progress_percent:.1f}% | Successful: {successful_translations} | Failed: {failed_translations}")
        
        # Final quality report
        if progress_callback:
            progress_callback("Progress: 95% | Finalizing retranslated content...")
            total_attempted = successful_translations + failed_translations
            if total_attempted > 0:
                success_rate = (successful_translations / total_attempted) * 100
                if quota_exceeded:
                    progress_callback(f"Progress: 100% | Retranslation stopped due to quota limits: {success_rate:.1f}% success rate ({successful_translations}/{total_attempted})")
                else:
                    progress_callback(f"Progress: 100% | Retranslation complete: {success_rate:.1f}% success rate ({successful_translations}/{total_attempted})")
            else:
                progress_callback("Progress: 100% | Retranslation complete: No chunks processed")
        
        # Combine the lines back into a single text
        return '\n'.join(lines)
        
    def analyze_translation_quality(self, translated_text, target_language, original_text=None):
        """
        Comprehensive translation quality analysis with detailed insights.
        
        Args:
            translated_text (str): The translated text to analyze
            target_language (str): The target language name
            original_text (str, optional): Original text for comparison analysis
            
        Returns:
            dict: Comprehensive analysis results with recommendations
        """
        # Get basic detection results
        detection_results = self.detect_untranslated_sections(translated_text, target_language)
        
        lines = translated_text.split('\n')
        target_language_lower = target_language.lower()
        
        # Initialize analysis results
        analysis = {
            'basic_stats': detection_results['stats'],
            'confidence_scores': detection_results['confidence_scores'],
            'untranslated_lines': detection_results['untranslated_lines'],
            'quality_issues': [],
            'recommendations': [],
            'language_specific_analysis': {},
            'overall_quality_score': 0.0,
            'quality_grade': 'Unknown'
        }
        
        # Analyze line by line for specific issues
        mixed_language_lines = []
        formatting_issues = []
        encoding_issues = []
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
                
            # Check for mixed language content
            if self._has_mixed_languages(line, target_language_lower):
                mixed_language_lines.append((i, line))
            
            # Check for formatting preservation issues
            if self._has_formatting_issues(line):
                formatting_issues.append((i, line))
            
            # Check for encoding issues
            if self._has_encoding_issues(line):
                encoding_issues.append((i, line))
        
        # Language-specific analysis
        if 'korean' in target_language_lower or '한국어' in target_language_lower:
            analysis['language_specific_analysis'] = self._analyze_korean_translation(translated_text)
        elif 'japanese' in target_language_lower or '日本語' in target_language_lower:
            analysis['language_specific_analysis'] = self._analyze_japanese_translation(translated_text)
        elif 'chinese' in target_language_lower or '中文' in target_language_lower:
            analysis['language_specific_analysis'] = self._analyze_chinese_translation(translated_text)
        
        # Compile quality issues
        if mixed_language_lines:
            analysis['quality_issues'].append({
                'type': 'mixed_language',
                'severity': 'medium',
                'count': len(mixed_language_lines),
                'description': 'Lines containing mixed languages detected',
                'lines': mixed_language_lines[:5]  # Show first 5 examples
            })
        
        # Add quoted content specific issues
        if detection_results['stats'].get('quoted_untranslated', 0) > 0:
            analysis['quality_issues'].append({
                'type': 'quoted_content_untranslated',
                'severity': 'high',
                'count': detection_results['stats']['quoted_untranslated'],
                'description': 'Quoted strings found in wrong language using advanced language detection',
                'lines': detection_results['untranslated_lines'][:3]  # Show first 3 examples
            })
        
        if formatting_issues:
            analysis['quality_issues'].append({
                'type': 'formatting',
                'severity': 'low',
                'count': len(formatting_issues),
                'description': 'Potential formatting preservation issues',
                'lines': formatting_issues[:5]
            })
        
        if encoding_issues:
            analysis['quality_issues'].append({
                'type': 'encoding',
                'severity': 'high',
                'count': len(encoding_issues),
                'description': 'Character encoding or display issues',
                'lines': encoding_issues[:5]
            })
        
        # Calculate overall quality score with enhanced metrics
        confidence_avg = analysis['basic_stats']['confidence_avg']
        untranslated_ratio = 0
        if analysis['basic_stats']['non_empty_lines'] > 0:
            untranslated_ratio = analysis['basic_stats']['untranslated_lines'] / analysis['basic_stats']['non_empty_lines']
        
        # Quality score calculation (0-100) with quoted content consideration
        quality_score = confidence_avg * 100
        quality_score -= untranslated_ratio * 50  # Penalty for untranslated content
        quality_score -= len(mixed_language_lines) * 2  # Penalty for mixed language
        quality_score -= len(encoding_issues) * 5  # Penalty for encoding issues
        
        # Additional penalty for quoted content issues
        quoted_analyzed = detection_results['stats'].get('quoted_content_analyzed', 0)
        quoted_untranslated = detection_results['stats'].get('quoted_untranslated', 0)
        if quoted_analyzed > 0:
            quoted_error_ratio = quoted_untranslated / quoted_analyzed
            quality_score -= quoted_error_ratio * 30  # Penalty for quoted content errors
        
        quality_score = max(0, min(100, quality_score))
        
        analysis['overall_quality_score'] = quality_score
        
        # Assign quality grade
        if quality_score >= 90:
            analysis['quality_grade'] = 'Excellent'
        elif quality_score >= 80:
            analysis['quality_grade'] = 'Good'
        elif quality_score >= 70:
            analysis['quality_grade'] = 'Fair'
        elif quality_score >= 60:
            analysis['quality_grade'] = 'Poor'
        else:
            analysis['quality_grade'] = 'Very Poor'
        
        # Generate recommendations
        if untranslated_ratio > 0.1:
            analysis['recommendations'].append("High number of untranslated sections detected. Consider running retranslation or reviewing translation model settings.")
        
        # Add quoted content specific recommendations
        quoted_analyzed = detection_results['stats'].get('quoted_content_analyzed', 0)
        quoted_untranslated = detection_results['stats'].get('quoted_untranslated', 0)
        if quoted_untranslated > 0:
            if quoted_analyzed > 0:
                quoted_error_rate = (quoted_untranslated / quoted_analyzed) * 100
                analysis['recommendations'].append(f"Advanced language detection found {quoted_untranslated} quoted strings in wrong language ({quoted_error_rate:.1f}% of quoted content). These require immediate attention as they contain user-visible text.")
            else:
                analysis['recommendations'].append("Quoted content contains text in unexpected languages. Review translation of string values in key-value pairs.")
        
        if confidence_avg < 0.6:
            analysis['recommendations'].append("Low overall confidence scores. Consider using a more advanced translation model or reviewing target language specification.")
        
        if mixed_language_lines:
            analysis['recommendations'].append("Mixed language content detected. Review translation prompts to ensure consistent target language usage.")
        
        if analysis['basic_stats']['keyword_only_lines'] > analysis['basic_stats']['non_empty_lines'] * 0.5:
            analysis['recommendations'].append("High ratio of keyword-only lines. Consider adjusting keyword detection patterns if some content should be translated.")
        
        # Add language-specific recommendations
        lang_analysis = analysis['language_specific_analysis']
        if lang_analysis.get('issues'):
            for issue in lang_analysis['issues'][:3]:  # Top 3 issues
                analysis['recommendations'].append(f"Language-specific issue: {issue}")
        
        return analysis
    
    def _has_mixed_languages(self, text, target_language_lower):
        """Check if a line contains mixed languages"""
        if not text.strip():
            return False
        
        # Count characters from different language families
        latin_count = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        
        if 'korean' in target_language_lower:
            korean_count = sum(1 for c in text if '\uAC00' <= c <= '\uD7A3')
            return korean_count > 0 and latin_count > korean_count
        elif 'japanese' in target_language_lower:
            japanese_count = sum(1 for c in text if 
                               ('\u3040' <= c <= '\u309F') or 
                               ('\u30A0' <= c <= '\u30FF'))
            return japanese_count > 0 and latin_count > japanese_count
        elif 'chinese' in target_language_lower:
            chinese_count = sum(1 for c in text if '\u4E00' <= c <= '\u9FFF')
            return chinese_count > 0 and latin_count > chinese_count
        
        return False
    
    def _has_formatting_issues(self, text):
        """Check for potential formatting preservation issues"""
        # Look for broken formatting patterns
        issues = [
            len(re.findall(r'\s{3,}', text)) > 2,  # Excessive whitespace
            text.count('  ') > text.count(' ') * 0.1,  # Too many double spaces
            re.search(r'[^\w\s][^\w\s][^\w\s]', text),  # Clustered punctuation
        ]
        return any(issues)
    
    def _has_encoding_issues(self, text):
        """Check for character encoding or display issues"""
        # Look for replacement characters or encoding artifacts
        encoding_issues = [
            '' in text,  # Replacement character
            '???' in text,  # Common encoding error pattern
            re.search(r'[^\x00-\x7F\u0080-\uFFFF]', text),  # Invalid Unicode
        ]
        return any(encoding_issues)
    
    def _analyze_korean_translation(self, text):
        """Korean-specific translation quality analysis"""
        analysis = {'issues': [], 'suggestions': []}
        
        # Check for proper Korean spacing
        lines = text.split('\n')
        spacing_issues = 0
        for line in lines:
            if re.search(r'[가-힣][a-zA-Z]|[a-zA-Z][가-힣]', line):
                spacing_issues += 1
        
        if spacing_issues > 0:
            analysis['issues'].append(f"Korean-English spacing issues found in {spacing_issues} lines")
            analysis['suggestions'].append("Review Korean text spacing rules between Hangul and Latin characters")
        
        # Check for honorific consistency
        formal_endings = len(re.findall(r'습니다|시다|세요', text))
        informal_endings = len(re.findall(r'이야|거야|어|아', text))
        
        if formal_endings > 0 and informal_endings > 0:
            analysis['issues'].append("Mixed formal and informal speech levels detected")
            analysis['suggestions'].append("Consider maintaining consistent politeness level throughout the translation")
        
        return analysis
    
    def _analyze_japanese_translation(self, text):
        """Japanese-specific translation quality analysis"""
        analysis = {'issues': [], 'suggestions': []}
        
        # Check for appropriate particle usage
        particle_density = len(re.findall(r'[는가를에다토]', text)) / max(len(text), 1)
        if particle_density < 0.05:  # Low particle density might indicate poor Japanese
            analysis['issues'].append("Low Japanese particle density - may indicate incomplete translation")
            analysis['suggestions'].append("Review particle usage in Japanese text")
        
        # Check for mixed writing systems balance
        hiragana_count = sum(1 for c in text if '\u3040' <= c <= '\u309F')
        katakana_count = sum(1 for c in text if '\u30A0' <= c <= '\u30FF')
        kanji_count = sum(1 for c in text if '\u4E00' <= c <= '\u9FFF')
        
        total_japanese = hiragana_count + katakana_count + kanji_count
        if total_japanese > 0:
            hiragana_ratio = hiragana_count / total_japanese
            if hiragana_ratio > 0.8:
                analysis['issues'].append("Unusually high hiragana ratio - may indicate limited kanji usage")
                analysis['suggestions'].append("Consider using more appropriate kanji for formal translation")
        
        return analysis
    
    def _analyze_chinese_translation(self, text):
        """Chinese-specific translation quality analysis"""
        analysis = {'issues': [], 'suggestions': []}
        
        # Check for traditional vs simplified consistency
        traditional_chars = 0
        simplified_chars = 0
        
        # Sample traditional vs simplified character pairs
        trad_simp_pairs = [
            ('繁', '繁'), ('體', '体'), ('統', '统'), ('語', '语'), ('國', '国'),
            ('學', '学'), ('長', '长'), ('時', '时'), ('間', '间'), ('現', '现')
        ]
        
        for trad, simp in trad_simp_pairs:
            traditional_chars += text.count(trad)
            simplified_chars += text.count(simp)
        
        if traditional_chars > 0 and simplified_chars > 0:
            analysis['issues'].append("Mixed traditional and simplified Chinese characters detected")
            analysis['suggestions'].append("Consider maintaining consistency in Chinese character set (traditional vs simplified)")
        
        return analysis

    def _could_be_target_language(self, text, target_lang_code):
        """
        Check if text could be in the target language based on character patterns.
        Used when language detection returns 'unknown'.
        More strict approach to reduce false positives.
        """
        if not text or not target_lang_code:
            return False
        
        text = text.strip()
        if len(text) < 2:
            return True  # Very short text, give benefit of doubt
        
        # Count different character types
        korean_chars = sum(1 for c in text if '\uAC00' <= c <= '\uD7A3')
        japanese_chars = sum(1 for c in text if 
                           ('\u3040' <= c <= '\u309F') or  # Hiragana
                           ('\u30A0' <= c <= '\u30FF'))    # Katakana
        chinese_chars = sum(1 for c in text if '\u4E00' <= c <= '\u9FFF')
        latin_chars = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        extended_latin_chars = sum(1 for c in text if c.isalpha() and 128 <= ord(c) < 256)
        
        total_chars = len([c for c in text if c.isalpha()])
        if total_chars == 0:
            return True  # No alphabetic characters, assume correct
        
        # Calculate character ratios
        target_lang_code = target_lang_code.lower()
        
        if target_lang_code == 'ko':
            # For Korean, expect significant Korean characters
            korean_ratio = korean_chars / total_chars
            # Be more strict - require at least 50% Korean characters for Korean target
            return korean_ratio > 0.5
        elif target_lang_code == 'ja':
            # For Japanese, expect Japanese characters or mixed with Chinese
            japanese_ratio = (japanese_chars + chinese_chars) / total_chars
            # Be more strict - require at least 50% Japanese/Chinese characters
            return japanese_ratio > 0.5
        elif target_lang_code == 'zh':
            # For Chinese, expect Chinese characters
            chinese_ratio = chinese_chars / total_chars
            # Be more strict - require at least 60% Chinese characters
            return chinese_ratio > 0.6
        elif target_lang_code == 'en':
            # For English, expect mostly basic Latin characters
            latin_ratio = latin_chars / total_chars
            # Be more strict - require at least 80% basic Latin for English
            return latin_ratio > 0.8 and extended_latin_chars == 0
        else:
            # For other European languages, expect Latin characters but allow extended Latin
            total_latin_ratio = (latin_chars + extended_latin_chars) / total_chars
            # Be more strict - require at least 70% Latin characters for other languages
            return total_latin_ratio > 0.7

# Translation logic will be implemented here