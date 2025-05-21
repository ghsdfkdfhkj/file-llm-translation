# File reading/writing utilities will be implemented here

def read_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f: # 다양한 인코딩 고려 필요
            return f.read()
    except Exception as e:
        print(f"파일 읽기 오류 ({file_path}): {e}")
        return None

def write_file(file_path, content):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"파일 쓰기 오류 ({file_path}): {e}")
        return False 