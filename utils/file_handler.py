# File reading/writing utilities will be implemented here
import chardet
import os

def detect_encoding(file_path):
    """Detect the encoding of a file using chardet"""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            return result['encoding'] or 'utf-8'
    except Exception:
        return 'utf-8'  # Default to UTF-8 if detection fails

def read_file(file_path):
    """Read file content with automatic encoding detection"""
    try:
        # First try UTF-8
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # If UTF-8 fails, detect encoding and try again
            encoding = detect_encoding(file_path)
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
    except Exception as e:
        print(f"File reading error ({file_path}): {e}")
        return None

def write_file(file_path, content):
    """Write content to file, preserving the original encoding if possible"""
    try:
        # If file exists, try to detect its encoding
        encoding = 'utf-8'
        if os.path.exists(file_path):
            encoding = detect_encoding(file_path)
        
        # Write with detected or default encoding
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"File writing error ({file_path}): {e}")
        return False 