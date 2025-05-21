from utils.file_handler import read_file # write_file is used directly in GUI or can be added to Translator if needed
from llm_services.openai_service import OpenAIService
from llm_services.anthropic_service import AnthropicService
from llm_services.google_gemini_service import GoogleGeminiService
import re

# Mapping of supported LLM services
SUPPORTED_LLM_SERVICES = {
    "OpenAI": OpenAIService,
    "Anthropic": AnthropicService,
    "Google Gemini": GoogleGeminiService
}

CHUNK_SIZE = 2000 # Characters per chunk (considering LLM API limits and performance)

# Patterns to recognize as keywords
KEYWORD_PATTERNS = [
    r'`[^`]+`',  # Code surrounded by backticks
    r'\{[^}]+\}',  # Text surrounded by curly braces
    r'<[^>]+>',  # HTML/XML tags
    r'\$[^$]+\$',  # Math expressions surrounded by dollar signs
    r'#\w+',  # Hashtags
    r'@\w+',  # Mentions
    r'https?://\S+',  # URLs
    r'\b[A-Z][A-Z0-9_]*\b',  # Constants in all caps
    r'\b[A-Za-z]+\.[A-Za-z]+(?:\.[A-Za-z]+)*\b',  # Dot-separated identifiers (e.g., module.class.method)
    r'\b(?:[a-zA-Z]+_){2,}[a-zA-Z]+\b',  # Underscore-separated identifiers
    r'\b[a-z]+_[a-z_]+_[a-z_]+(?::[0-9]+)?\b',  # Words with multiple underscores including optional :0 suffix
    r'\b[a-z]+_[a-z_]+(?::[0-9]+)?\b',  # Words with underscores including optional :0 suffix
    r'\$[a-z_]+\$',  # Text between dollar signs
    r'\b[a-z][a-z0-9_]*_[a-z0-9_]+\b',  # Any word containing underscore
]

class Translator:
    def __init__(self, llm_provider_name, api_key):
        self.llm_service = None
        self.llm_provider_name = llm_provider_name
        self.api_key = api_key
        self._initialize_llm_service()
        self.keyword_pattern = '|'.join(KEYWORD_PATTERNS)
        
        # Define special token
        self.LINE_BREAK_TOKEN = "__LINE_BREAK_TOKEN_7f8a31c2__"

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

    def _split_text_into_chunks(self, lines, chunk_size=CHUNK_SIZE):
        """Split lines into chunks, preserving line integrity."""
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line)
            
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
            
        return chunks

    def _extract_keywords_smart(self, text):
        """
        Extract ALL keywords from text based on KEYWORD_PATTERNS and replace with placeholders.
        This applies to the entire text, regardless of quotes.
        """
        keywords = {}
        placeholder_counter = 0
        
        def replace_match(match):
            nonlocal placeholder_counter
            keyword_val = match.group(0)
            # Avoid replacing already identified placeholders if text is reprocessed (e.g., in error retries)
            if re.fullmatch(r"__KEYWORD_\d+__", keyword_val):
                return keyword_val
            
            placeholder = f"__KEYWORD_{placeholder_counter}__"
            # Check if this exact keyword_val was already assigned to a different placeholder
            # This can happen if the same keyword appears multiple times.
            # We want each occurrence to have a unique placeholder if they are different instances,
            # but if it's the *exact same string*, using the same placeholder might be okay,
            # though simpler to just give a new one each time.
            # For now, always create a new placeholder for simplicity and to handle all cases.
            keywords[placeholder] = keyword_val
            placeholder_counter += 1
            return placeholder
        
        # Apply all keyword patterns to the text
        modified_text = re.sub(self.keyword_pattern, replace_match, text)
        return modified_text, keywords

    def _restore_keywords(self, translated_text, keywords):
        """Restore original keywords in translated text"""
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
            return "" # Return empty content for empty file

        # Split file into lines
        lines = content.splitlines(True)  # Keep newline characters
        
        # Create chunks split by lines
        chunks = self._split_text_into_chunks(lines)
        translated_lines_all = []
        total_chunks = len(chunks)

        if progress_callback: progress_callback(f"Starting translation of {total_chunks} chunk(s) using {self.llm_provider_name} ({selected_model})...")

        for i, chunk_lines in enumerate(chunks):
            if progress_callback:
                progress_callback(f"Translating chunk {i + 1}/{total_chunks}...")
                
            try:
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
                        content_to_translate = match.group(2) if match else line # Fallback to full line

                        if not content_to_translate.strip(): # If there is no content after removing leading whitespace
                            translated_lines_chunk.append(line)
                        else:
                            # Extract keywords (excluding those inside quotes) and replace with placeholders
                            modified_content, keywords = self._extract_keywords_smart(content_to_translate)
                            
                            # Translate (only the content excluding leading whitespace)
                            # Specify in the prompt to translate content within quotes
                            single_line_instruction = f"Translate the following text to {output_language}. Content within double quotes (e.g., \"example text\") MUST be translated. Specific tokens like __KEYWORD_0__, __KEYWORD_1__, etc., are placeholders for non-translatable text and MUST be preserved EXACTLY as they appear in the output. Do NOT translate these placeholders. Do NOT alter them in any way (e.g., by adding spaces or changing case). Other text should be translated normally.:\n\n"
                            
                            # Only add instruction if modified_content is not just placeholders or empty
                            # This check might be too simple, consider if LLM needs instruction anyway for context
                            text_for_llm = modified_content
                            if any(c.isalnum() for c in modified_content.replace("_", "")): # Check if there is actual text beyond keywords
                                text_for_llm = single_line_instruction + modified_content


                            translated_content = self.llm_service.translate(text_for_llm, output_language, selected_model)
                            
                            # Remove instruction from translated text if it was included
                            translated_content = translated_content.replace(single_line_instruction, "").strip()

                            # Restore keywords
                            if "Translation error:" in translated_content or "Error:" in translated_content:
                                error_message = f"Error translating line: {translated_content}"
                                if progress_callback: progress_callback(error_message)
                                translated_lines_chunk.append(line)  # Keep original line on error
                            else:
                                restored_content = self._restore_keywords(translated_content, keywords)
                                translated_lines_chunk.append(leading_space + restored_content) # Prepend leading whitespace to restored and translated content
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
                    modified_chunk_text, keywords = self._extract_keywords_smart(chunk_text_to_translate)
                    
                    # Specify in the translation instruction to maintain line breaks, translate content in quotes, and preserve placeholders
                    instruction = f"Translate the following text to {output_language}. Content within double quotes (e.g., \"example text\") MUST be translated. Preserve all special markers EXACTLY as they appear. This includes line break markers '{self.LINE_BREAK_TOKEN}' and placeholder tokens like __KEYWORD_0__, __KEYWORD_1__, etc. These placeholder tokens represent non-translatable text and MUST be preserved EXACTLY as they appear in the output. Do NOT translate these placeholders. Do NOT alter them in any way (e.g., by adding spaces or changing case). Ensure the count of '{self.LINE_BREAK_TOKEN}' markers in the output matches the input. Other text should be translated normally.:\n\n"
                    modified_chunk_with_instruction = instruction + modified_chunk_text
                    
                    # Translate
                    translated_chunk_text = self.llm_service.translate(modified_chunk_with_instruction, output_language, selected_model)
                    
                    if "Translation error:" in translated_chunk_text or "Error:" in translated_chunk_text:
                        error_message = f"Error translating chunk {i+1}: {translated_chunk_text}"
                        if progress_callback: progress_callback(error_message)
                        translated_lines_chunk.extend(chunk_lines)  # Keep original chunk on error
                    else:
                        # Remove instruction from translated text if it was included
                        translated_chunk_text = translated_chunk_text.replace(instruction, "").strip()
                        
                        # Restore keywords
                        restored_chunk_text = self._restore_keywords(translated_chunk_text, keywords)
                        
                        # Split lines and restore newline characters and leading whitespace
                        translated_segments = restored_chunk_text.split(self.LINE_BREAK_TOKEN)
                        
                        num_original_lines = len(original_lines_info)
                        num_translated_segments = len(translated_segments)

                        for j in range(max(num_original_lines, num_translated_segments)):
                            leading_space = original_lines_info[j]['leading'] if j < num_original_lines else ""
                            # Use original newline, otherwise based on LLM result (or default).
                            # Since only content was used for join, original newlines must be appended now.
                            original_ending = original_lines_info[j]['ending'] if j < num_original_lines else "\n"
                            
                            translated_content_part = translated_segments[j] if j < num_translated_segments else ""

                            # If LLM returned fewer segments than original and original had empty lines, try to keep those empty lines
                            if j < num_original_lines and not original_lines_info[j]['content'].strip() and j >= num_translated_segments:
                                translated_lines_chunk.append(original_lines_info[j]['leading'] + original_lines_info[j]['ending'])
                            elif j < num_original_lines and not original_lines_info[j]['content'].strip() and not translated_content_part.strip():
                                # If both original and translated are empty, use original (leading space + original ending)
                                translated_lines_chunk.append(original_lines_info[j]['leading'] + translated_content_part + original_lines_info[j]['ending'])
                            else:
                                # Adjust so that if the last line in original had no newline, and it's also the last translated segment, no newline is added
                                if j == num_original_lines - 1 and not original_lines_info[j]['ending'] and j == num_translated_segments - 1:
                                     final_ending = ""
                                else:
                                     final_ending = original_ending if j < num_original_lines else "\n" # Default newline if LLM added lines

                                translated_lines_chunk.append(leading_space + translated_content_part + final_ending)
                
                translated_lines_all.extend(translated_lines_chunk)

            except Exception as e:
                error_message = f"Exception during translation of chunk {i + 1}/{total_chunks}: {e}"
                if progress_callback: progress_callback(error_message)
                # Keep original chunk on error
                translated_lines_all.extend(chunk_lines)

        # Combine all translated lines
        full_translated_text = "".join(translated_lines_all)
        
        if progress_callback: progress_callback("Translation complete.")
        return full_translated_text

# Translation logic will be implemented here