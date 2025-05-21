import json
import os

CONFIG_FILE = "config.json"

# API key and settings management will be implemented here

def save_api_key(provider, api_key):
    # API 키를 안전하게 저장하는 로직 (예: 암호화)
    # 여기서는 간단히 JSON 파일에 저장
    config = load_config()
    if 'api_keys' not in config:
        config['api_keys'] = {}
    config['api_keys'][provider] = api_key # 주의: 실제 사용시 암호화 고려
    _save_config_to_file(config)

def load_api_key(provider):
    config = load_config()
    return config.get('api_keys', {}).get(provider)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {} # 파일 손상시 빈 설정 반환
    return {}

def _save_config_to_file(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4) 