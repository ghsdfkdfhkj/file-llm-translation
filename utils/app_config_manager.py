import json
import os

CONFIG_FILE_NAME = "app_config.json"

def get_config_path():
    # For simplicity, save in the same directory as the executable or script
    # More robust solutions might use platform-specific config directories
    return CONFIG_FILE_NAME

def save_app_settings(settings):
    """Saves application settings to a JSON file."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        print(f"Application settings saved to {config_path}")
        return True
    except IOError as e:
        print(f"Error saving application settings to {config_path}: {e}")
        return False

def load_app_settings():
    """Loads application settings from a JSON file."""
    config_path = get_config_path()
    if not os.path.exists(config_path):
        print(f"Application settings file not found: {config_path}. Returning default settings.")
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        print(f"Application settings loaded from {config_path}")
        return settings
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading application settings from {config_path}: {e}. Returning default settings.")
        return {}

if __name__ == '__main__':
    # Example Usage
    mock_settings_to_save = {
        "last_llm_provider": "Google Gemini",
        "last_selected_model": "gemini-1.5-pro-latest",
        "last_output_language_combo": "Korean (한국어)",
        "last_output_language_custom": ""
    }
    save_app_settings(mock_settings_to_save)
    
    loaded = load_app_settings()
    print("\nLoaded settings:")
    print(loaded)

    # Clean up the test file
    # if os.path.exists(CONFIG_FILE_NAME):
    #     os.remove(CONFIG_FILE_NAME)
    #     print(f"Cleaned up {CONFIG_FILE_NAME}") 