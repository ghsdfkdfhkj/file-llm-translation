import json
import os

CONFIG_FILE = "config.json"

# API key and settings management will be implemented here

def save_api_key(provider, api_key):
    # Logic to securely save API key (e.g., encryption)
    # Here, simply save to JSON file
    config = load_config()
    if 'api_keys' not in config:
        config['api_keys'] = {}
    config['api_keys'][provider] = api_key # Note: Consider encryption for production use
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
            return {} # Return empty config if file is corrupted
    return {}

def _save_config_to_file(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4) 