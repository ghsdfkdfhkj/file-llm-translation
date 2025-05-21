import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from translation_core.translator import Translator # Import Translator
from utils.config_manager import save_api_key, load_api_key # Added for API key save/load
from utils.app_config_manager import save_app_settings, load_app_settings # For app settings
from .model_selection_dialog import ModelSelectionDialog
import os
from tkinterdnd2 import DND_FILES, TkinterDnD # For drag and drop

class MainWindow:
    def __init__(self, master):
        # Ensure master is a TkinterDnD.Tk instance for drag-and-drop
        if not isinstance(master, TkinterDnD.Tk):
            # This case should ideally not happen if main.py is updated correctly.
            # However, if it does, log and potentially raise an error or disable DND.
            print("Warning: master is not a TkinterDnD.Tk instance. Drag and drop might not work.")
            # Consider: master = TkinterDnD.Tk() # Or handle differently
            # For now, we proceed assuming it might be handled by the caller or will gracefully degrade.

        self.master = master
        master.title("File LLM Translation")
        master.geometry("1200x700")  # Set wider initial size

        self.translator = None # Translator instance
        self.translated_content_for_export = None # Content to export
        self.current_model = None
        self.original_translation = None  # Store original translation

        # Configure text tags for highlighting
        self.modified_sections = set()  # Track modified sections

        # Main frame
        main_frame = ttk.Frame(master, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)

        # Frames for left-right split
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))

        # === Left frame content ===
        # LLM selection
        llm_label = ttk.Label(left_frame, text="Select LLM:")
        llm_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.llm_var = tk.StringVar()
        self.llm_combo_box = ttk.Combobox(left_frame, textvariable=self.llm_var, state="readonly")
        self.llm_combo_box['values'] = ("OpenAI", "Anthropic", "Google Gemini")
        self.llm_combo_box.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        self.llm_combo_box.bind("<<ComboboxSelected>>", self._on_llm_provider_changed)

        # API key input
        api_key_label = ttk.Label(left_frame, text="API Key:")
        api_key_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(left_frame, show="*", textvariable=self.api_key_var)
        self.api_key_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        self.api_key_entry.bind("<FocusOut>", self._on_api_key_focus_out)

        # Model selection button
        self.model_button = ttk.Button(left_frame, text="Select Model...", command=self._show_model_selection)
        self.model_button.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        self.model_button.config(state=tk.DISABLED)

        # Selected model display label
        self.selected_model_var = tk.StringVar(value="Selected Model: None")
        selected_model_label = ttk.Label(left_frame, textvariable=self.selected_model_var)
        selected_model_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        # File input frame
        file_input_frame = ttk.Frame(left_frame)
        file_input_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        file_input_frame.columnconfigure(1, weight=1)

        self.file_input_button = ttk.Button(file_input_frame, text="Select File to Translate", command=self.open_file_dialog)
        self.file_input_button.grid(row=0, column=0, sticky=tk.W)
        self.selected_file_label = ttk.Label(file_input_frame, text="Selected File: None")
        self.selected_file_label.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.input_file_path = None

        # Translation settings
        settings_frame = ttk.LabelFrame(left_frame, text="Translation Settings", padding="5")
        settings_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        settings_frame.columnconfigure(1, weight=1)
        
        output_lang_label = ttk.Label(settings_frame, text="Output Language:")
        output_lang_label.grid(row=0, column=0, sticky=tk.W)
        
        self.output_lang_var = tk.StringVar(value="English")
        self.output_lang_combo = ttk.Combobox(settings_frame, textvariable=self.output_lang_var, state="readonly")
        self.output_lang_combo['values'] = (
            "English",
            "Korean (한국어)",
            "Japanese (日本語)",
            "Chinese Simplified (简体中文)",
            "Chinese Traditional (繁體中文)",
            "French (Français)",
            "German (Deutsch)",
            "Spanish (Español)",
            "Russian (Русский)",
            "Vietnamese (Tiếng Việt)",
            "Thai (ไทย)",
            "Indonesian (Bahasa Indonesia)"
        )
        self.output_lang_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Entry for custom input
        self.custom_lang_var = tk.StringVar()
        self.custom_lang_entry = ttk.Entry(settings_frame, textvariable=self.custom_lang_var)
        self.custom_lang_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=(5, 0))
        custom_lang_label = ttk.Label(settings_frame, text="Custom Input:")
        custom_lang_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))

        # Combo box selection event handling
        def on_lang_selected(event):
            if self.output_lang_combo.get() != "":
                self.custom_lang_var.set("")  # Reset custom input field when selected from combo box
        
        # Custom input event handling
        def on_custom_lang_changed(*args):
            if self.custom_lang_var.get() != "":
                self.output_lang_var.set("")  # Reset combo box selection when custom input
        
        self.output_lang_combo.bind('<<ComboboxSelected>>', on_lang_selected)
        self.custom_lang_var.trace_add('write', on_custom_lang_changed)

        # Button frame for translation and export
        button_frame = ttk.Frame(left_frame)
        button_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        # Translation button
        self.translate_button = ttk.Button(button_frame, text="Start Translation", command=self.start_translation)
        self.translate_button.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.translate_button.config(state=tk.DISABLED)

        # Export button
        self.export_button = ttk.Button(button_frame, text="Export Translation Results", command=self.export_file_dialog, state=tk.DISABLED)
        self.export_button.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))

        # Log area
        log_label = ttk.Label(left_frame, text="Log")
        log_label.grid(row=7, column=0, sticky=tk.W, pady=(0, 2))
        
        log_frame = ttk.Frame(left_frame)
        log_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = log_scrollbar.set

        # === Right frame content ===
        # Translation results area
        result_label = ttk.Label(right_frame, text="Translation Results (Editable)")
        result_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        
        result_frame = ttk.Frame(right_frame)
        result_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        
        self.result_text = tk.Text(result_frame, wrap=tk.WORD)
        self.result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.result_text.tag_configure("modified", foreground="blue")  # Configure modified text tag
        self.result_text.bind("<<Modified>>", self._on_text_modified)  # Bind modification event
        result_scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_text.yview)
        result_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.result_text['yscrollcommand'] = result_scrollbar.set

        # Add "Save Changes" button
        self.save_changes_button = ttk.Button(right_frame, text="Save Changes", command=self._save_changes)
        self.save_changes_button.grid(row=2, column=0, sticky=tk.E, pady=5)
        self.save_changes_button.config(state=tk.DISABLED)

        # Frame settings
        main_frame.columnconfigure(0, weight=0)  # Left is fixed size
        main_frame.columnconfigure(1, weight=1)  # Right is expandable
        main_frame.rowconfigure(0, weight=1)
        
        left_frame.columnconfigure(1, weight=1)
        left_frame.rowconfigure(8, weight=1)  # Log area is expandable
        
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)  # Result area is expandable

        # Register drop target (e.g., the entire left frame or a specific widget)
        # Using left_frame as the drop target for now.
        # You might want to make a more specific area (e.g., a Label widget) the drop target.
        try:
            left_frame.drop_target_register(DND_FILES)
            left_frame.dnd_bind('<<Drop>>', self._handle_drop)
            self._log_message("Drag and drop for files is enabled on the left panel.")
        except Exception as e:
            self._log_message(f"Failed to initialize drag and drop: {e}. TkinterDnD might not be set up correctly.")

        # Load general application settings first, which may set the LLM provider
        self._load_application_settings() 
        # If _load_application_settings did not trigger _on_llm_provider_changed (e.g. no saved provider),
        # explicitly call it to initialize with default or ensure UI consistency.
        # This check is to prevent double calls if llm_var.set in _load_application_settings already triggered it.
        if not self.translator: # A proxy to check if service initialization has run
            self._on_llm_provider_changed() 
        
        # Bind window close event to save settings
        master.protocol("WM_DELETE_WINDOW", self._on_window_close)

    def _on_window_close(self):
        """Handles actions to be performed when the window is closed."""
        self._save_application_settings()
        self.master.destroy() # Close the window

    def _load_application_settings(self):
        """Loads general application settings and applies them."""
        settings = load_app_settings()
        if not settings:
            self._log_message("No saved application settings found or error loading them.")
            # Set default LLM provider if no settings, which will trigger API key loading
            self.llm_combo_box.current(0) # Default to OpenAI or first in list
            self._on_llm_provider_changed() # Ensure service is updated for the default
            return

        last_provider = settings.get("last_llm_provider")
        if last_provider and last_provider in self.llm_combo_box['values']:
            self.llm_var.set(last_provider)
            # _on_llm_provider_changed will be called automatically by var set, which loads API key
            # and then calls _perform_service_update.
        else:
            self.llm_combo_box.current(0) # Default if saved one is invalid
            self._on_llm_provider_changed() # Ensure service is updated
        
        # Output language - ComboBox
        last_output_lang_combo = settings.get("last_output_language_combo")
        if last_output_lang_combo and last_output_lang_combo in self.output_lang_combo['values']:
            self.output_lang_var.set(last_output_lang_combo)
        elif not last_output_lang_combo: # if key is missing, set default
             self.output_lang_combo.current(0) # Default to English

        # Output language - Custom input (only if combo was not set from saved value)
        if not self.output_lang_var.get(): # If combo is empty (e.g. custom was used)
            last_output_lang_custom = settings.get("last_output_language_custom", "")
            self.custom_lang_var.set(last_output_lang_custom)
        
        # Note: Last selected model will be loaded within _perform_service_update 
        # after the translator service is confirmed to be initialized.
        self._log_message("Application settings loaded.")

    def _save_application_settings(self):
        """Saves current application settings."""
        current_settings = {
            "last_llm_provider": self.llm_var.get(),
            "last_selected_model": self.current_model if self.current_model else "",
            "last_output_language_combo": self.output_lang_var.get(),
            "last_output_language_custom": self.custom_lang_var.get()
        }
        if save_app_settings(current_settings):
            self._log_message("Application settings saved successfully.")
        else:
            self._log_message("Failed to save application settings.")

    def _handle_drop(self, event):
        """Handle file drop events."""
        # The event.data attribute contains a string with one or more file paths,
        # possibly enclosed in curly braces if multiple files are dropped or if the path contains spaces.
        filepath_str = event.data
        
        # Simple parsing: remove curly braces if present and take the first file if multiple are listed.
        # For more robust parsing, especially with multiple files, you might need a more complex approach.
        if filepath_str.startswith("{") and filepath_str.endswith("}"):
            filepath_str = filepath_str[1:-1]
        
        # If multiple files are dropped (often space-separated if not in braces, or part of the braced list),
        # we'll just take the first one. You could also iterate or show an error if more than one.
        # This simple split might not be robust for all path names (e.g., paths with spaces not in braces).
        # TkinterDND2 often returns a single path even if it has spaces, correctly handled.
        # If it returns a list like string '{path1} {path2}', splitting by '}{' or similar might be needed.
        
        # A common format is a single path, or paths separated by spaces if multiple are dropped.
        # We are interested in the first valid file path.
        potential_paths = filepath_str.split() # Simple split, might need refinement
        filepath = None
        for p_path in potential_paths:
            # A basic check: does it look like a file path?
            # os.path.isfile is the most reliable check.
            if os.path.isfile(p_path):
                filepath = p_path
                break # Take the first valid file found

        if filepath:
            self.input_file_path = filepath
            self.selected_file_label.config(text=f"Selected File: {filepath}")
            self._log_message(f"Input file selected via drag and drop: {filepath}")
            if self.translator and self.translator.llm_service and self.current_model: # Check model too
                self.translate_button.config(state=tk.NORMAL)
        else:
            self._log_message(f"Drag and drop: No valid file path found in '{event.data}'")

    def _show_model_selection(self):
        if not self.translator or not self.translator.llm_service:
            messagebox.showerror("Error", "LLM service is not initialized.")
            return

        # Get latest model and all model list
        latest_models = self.translator.get_available_models()
        all_models = self.translator.get_all_models()  # New method call
        
        if not latest_models:
            messagebox.showerror("Error", "No available models.")
            return

        # Create and display model selection dialog
        model_dialog = ModelSelectionDialog(
            self.master,
            latest_models,
            self.current_model,
            all_models
        )

        # Handle dialog close
        def on_dialog_closed():
            selected_model = model_dialog.result
            if selected_model:
                self.current_model = selected_model
                self.selected_model_var.set(f"Selected Model: {selected_model}")
                self._update_translate_button_state()
                self._log_message(f"Model selected: {selected_model}")
            
        # Set apply button callback
        model_dialog.top.protocol("WM_DELETE_WINDOW", lambda: [model_dialog._on_cancel(), on_dialog_closed()])
        model_dialog.top.bind('<Escape>', lambda e: [model_dialog._on_cancel(), on_dialog_closed()])
        
        # Set callback function for dialog
        model_dialog.parent = self  # Set parent window reference
        
        # Display dialog
        result = model_dialog.show()
        if result:  # Process only if closed with OK button
            on_dialog_closed()

    def _on_model_selected(self, selected_model):
        """Callback called when 'Apply' button is clicked in model selection dialog"""
        self.current_model = selected_model
        self.selected_model_var.set(f"Selected Model: {selected_model}")
        self._update_translate_button_state()
        self._log_message(f"Model selected: {selected_model}")

    def _update_translate_button_state(self):
        """Update translation button state"""
        if self.translator and self.translator.llm_service and self.input_file_path and self.current_model:
            self.translate_button.config(state=tk.NORMAL)
        else:
            self.translate_button.config(state=tk.DISABLED)

    def _log_message(self, message):
        """Add log message to log area"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _show_translation_result(self, result):
        """Display translation results in result area"""
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert(tk.END, result if result else "No translation results")
        self.original_translation = result  # Store original translation
        self.modified_sections.clear()  # Clear modified sections
        self.save_changes_button.config(state=tk.NORMAL)
        self.result_text.edit_modified(False)  # Reset modified flag

    def _on_text_modified(self, event=None):
        """Handle text modification events"""
        if not self.original_translation:
            return
        
        current_text = self.result_text.get("1.0", tk.END).strip()
        if current_text == self.original_translation:
            return

        # Remove all existing tags
        self.result_text.tag_remove("modified", "1.0", tk.END)

        # Compare current text with original translation line by line
        original_lines = self.original_translation.split('\n')
        current_lines = current_text.split('\n')
        
        for i, (orig, curr) in enumerate(zip(original_lines, current_lines + [''] * (len(original_lines) - len(current_lines)))):
            if curr != orig:
                line_start = f"{i+1}.0"
                line_end = f"{i+1}.end"
                self.result_text.tag_add("modified", line_start, line_end)

        # Handle case where new lines were added
        if len(current_lines) > len(original_lines):
            for i in range(len(original_lines), len(current_lines)):
                line_start = f"{i+1}.0"
                line_end = f"{i+1}.end"
                self.result_text.tag_add("modified", line_start, line_end)

        self.result_text.edit_modified(False)  # Reset modified flag

    def _on_llm_provider_changed(self, event=None):
        """Handles LLM provider changes, loads API key, and updates the service."""
        provider = self.llm_var.get()
        api_key = load_api_key(provider) # Load API key for the selected provider
        
        if api_key:
            self.api_key_var.set(api_key) # Set the API key in the entry field
            self._log_message(f"API key for {provider} loaded.")
            self.model_button.config(state=tk.NORMAL) # Enable model selection
        else:
            self.api_key_var.set("") # Clear API key field if not found
            self._log_message(f"API key for {provider} not found. Please enter it.")
            self.model_button.config(state=tk.DISABLED) # Disable model selection until API key is entered
            self.selected_model_var.set("Selected Model: None") # Reset selected model display
            self.translator = None # Reset translator instance

        # Save current API key (if any) when provider changes before updating service
        # This ensures if a user switches, types a key, then switches back, the typed key isn't lost
        # (unless it was for the *new* provider).
        self._save_current_api_key() # This might be slightly redundant if key was just loaded but ensures consistency

        self._perform_service_update() # Update translator service and selected model

    def _save_current_api_key(self):
        llm_provider = self.llm_var.get()
        api_key = self.api_key_var.get()
        if llm_provider and api_key: # Only save if provider and key are present
            save_api_key(llm_provider, api_key)
            self._log_message(f"API key for {llm_provider} has been saved.")
        elif llm_provider and not api_key:
             self._log_message(f"API key for {llm_provider} is empty, not saved.")

    def _on_api_key_focus_out(self, event=None):
        self._save_current_api_key() # Save the key first
        self._perform_service_update() # Then update the service

    def _perform_service_update(self):
        llm_provider = self.llm_var.get()
        api_key = self.api_key_var.get()

        if not llm_provider:
            self.model_button.config(state=tk.DISABLED)
            self.translate_button.config(state=tk.DISABLED)
            self.translator = None
            return

        if not api_key:
            self.model_button.config(state=tk.DISABLED)
            self.translator = None
            self.translate_button.config(state=tk.DISABLED)
            return

        self._log_message(f"Attempting to initialize {llm_provider} service...")
        try:
            self.translator = Translator(llm_provider_name=llm_provider, api_key=api_key)
            if self.translator.llm_service is None:
                self.model_button.config(state=tk.DISABLED)
                self.translate_button.config(state=tk.DISABLED)
                self._log_message(f"{llm_provider} service initialization failed. Check API key.")
                return
            
            self.model_button.config(state=tk.NORMAL)
            self._log_message(f"{llm_provider} service has been initialized.")

            # Now that translator is initialized, try to load the last selected model for this provider
            app_settings = load_app_settings() # Reload to get the model specific to this provider if saved
            last_model_for_provider = app_settings.get("last_selected_model")
            
            # Check if the current provider in settings matches the one just initialized
            # This is important if settings were saved with a different provider active
            saved_provider_for_model = app_settings.get("last_llm_provider")

            if last_model_for_provider and saved_provider_for_model == llm_provider:
                # Validate if this model is available for the current provider
                available_models = self.translator.get_all_models() # Use get_all_models for broader check
                if last_model_for_provider in available_models:
                    self.current_model = last_model_for_provider
                    self.selected_model_var.set(f"Selected Model: {self.current_model}")
                    self._log_message(f"Restored last selected model: {self.current_model} for {llm_provider}")
                else:
                    self._log_message(f"Last selected model '{last_model_for_provider}' not available for {llm_provider}. Please select a model.")
                    self.current_model = None # Reset if not available
                    self.selected_model_var.set("Selected Model: None")
            else:
                 self.current_model = None # Reset if no model saved for this provider or provider mismatch
                 self.selected_model_var.set("Selected Model: None")

            self._update_translate_button_state()

        except Exception as e:
            self._log_message(f"Unexpected error while updating LLM service: {e}")
            self.model_button.config(state=tk.DISABLED)
            self.translator = None
            self.translate_button.config(state=tk.DISABLED)

    def open_file_dialog(self):
        """Open file dialog"""
        filetypes = (
            ("All files", "*.*"),
        )
        filepath = filedialog.askopenfilename(
            title="Select a file to translate",
            filetypes=filetypes
        )
        if filepath:
            self.input_file_path = filepath
            self.selected_file_label.config(text=f"Selected File: {filepath}")
            self._log_message(f"Input file selected: {filepath}")
            # Enable translation button if LLM service is ready
            if self.translator and self.translator.llm_service:
                self.translate_button.config(state=tk.NORMAL)

    def start_translation(self):
        if not self.translator or not self.translator.llm_service:
            messagebox.showerror("Error", "LLM service is not initialized. Please check LLM type and API key.")
            return
            
        llm_provider = self.llm_var.get()
        api_key = self.api_key_var.get()
        output_language = self.get_target_language()

        if not self.input_file_path:
            messagebox.showerror("Error", "Please select a file to translate first.")
            return

        if not api_key:
            messagebox.showerror("Error", "Please enter API key.")
            return
        
        if not self.current_model:
            messagebox.showerror("Error", "Please select a translation model.")
            return
        
        if not output_language:
            messagebox.showerror("Error", "Please select or enter output language.")
            return

        self._log_message(f"Translation started: LLM={llm_provider}, model={self.current_model}, output language={output_language}")
        self._log_message(f"Input file: {self.input_file_path}")
        self.translate_button.config(state=tk.DISABLED) # Disable button during translation
        self.export_button.config(state=tk.DISABLED)
        self.translated_content_for_export = None

        # Run translation in background thread (prevent GUI blocking)
        import threading
        thread = threading.Thread(target=self._execute_translation, 
                                args=(self.input_file_path, output_language, self.current_model))
        thread.start()

    def _execute_translation(self, input_file, output_language, model):
        try:
            # self.translator is already set in _perform_service_update
            translated_content = self.translator.translate_file(
                input_file, 
                output_language, 
                model, 
                self._log_message # Pass callback function
            )
            
            # Check if translation contains error messages
            error_keywords = ["Error:", "[CHUNK_ERROR:", "[CHUNK_EXCEPTION:", "500 Internal error"]
            has_error = any(keyword in translated_content for keyword in error_keywords)
            
            if has_error:
                # Extract actual translation content by removing error messages
                lines = translated_content.split('\n')
                cleaned_lines = [line for line in lines if not any(keyword in line for keyword in error_keywords)]
                translated_content = '\n'.join(cleaned_lines)
                
                # Log the error but don't show in translation result
                self._log_message("Warning: Some parts of the translation had errors. Check the log for details.")
            
            self.translated_content_for_export = translated_content
            # Handle GUI updates in main thread using master.after
            self.master.after(0, self._on_translation_complete, translated_content)

        except Exception as e:
            error_message = f"Critical error during translation: {e}"
            self._log_message(error_message)
            self.master.after(0, self._on_translation_failed)

    def _on_translation_complete(self, translated_content):
        """Handle translation completion"""
        if not translated_content.strip():
            self._log_message("Translation failed: No content was translated.")
            self._show_translation_result("Translation failed. Please check the log for details.")
            self.translate_button.config(state=tk.NORMAL)
            self.export_button.config(state=tk.DISABLED)
            self.save_changes_button.config(state=tk.DISABLED)
            return
            
        self._log_message("Translation completed successfully.")
        self._show_translation_result(translated_content)
        
        self.translate_button.config(state=tk.NORMAL)  # Re-enable translation button
        self.export_button.config(state=tk.NORMAL)  # Enable export button
        self.save_changes_button.config(state=tk.NORMAL)  # Enable save changes button

    def _on_translation_failed(self):
        messagebox.showerror("Translation Failed", "Translation process encountered an error. Please check the log.")
        self.translate_button.config(state=tk.NORMAL)
        self.export_button.config(state=tk.DISABLED)

    def export_file_dialog(self):
        if self.translated_content_for_export is None: # None means not translated yet or failed
            messagebox.showwarning("Warning", "No translated content to export. Please run translation first.")
            return

        # Get the original file extension
        original_ext = os.path.splitext(self.input_file_path)[1] if self.input_file_path else ".txt"
        
        file_path = filedialog.asksaveasfilename(
            title="Save Translated File",
            defaultextension=original_ext,
            filetypes=(
                ("Text files", "*.txt"),
                ("JSON files", "*.json"),
                ("Markdown files", "*.md"),
                ("Python files", "*.py"),
                ("JavaScript files", "*.js"),
                ("TypeScript files", "*.ts"),
                ("HTML files", "*.html;*.htm"),
                ("CSS files", "*.css"),
                ("XML files", "*.xml"),
                ("YAML files", "*.yml;*.yaml"),
                ("INI files", "*.ini"),
                ("Config files", "*.cfg;*.conf"),
                ("CSV files", "*.csv"),
                ("SQL files", "*.sql"),
                ("Log files", "*.log"),
                ("All files", "*.*")
            ),
            initialfile=f"translated{original_ext}"
        )
        if file_path:
            try:
                # Use utils.file_handler.write_file
                from utils.file_handler import write_file
                if write_file(file_path, self.translated_content_for_export):
                    self._log_message(f"Translated file saved: {file_path}")
                    messagebox.showinfo("Success", f"Translated file saved to '{file_path}'")
                else:
                    self._log_message(f"Failed to save file: {file_path}")
                    messagebox.showerror("Error", f"Error occurred while saving file: {file_path}")
            except Exception as e:
                self._log_message(f"File save error: {e}")
                messagebox.showerror("Error", f"Error occurred while saving file: {e}")

    def get_target_language(self):
        """Returns the selected output language. Prioritizes custom input if available."""
        custom_lang = self.custom_lang_var.get().strip()
        if custom_lang:
            return custom_lang
        selected_lang = self.output_lang_var.get().strip()
        if not selected_lang:
            return ""
        return selected_lang.split(' ')[0]  # Remove native language in parentheses

    def _save_changes(self):
        """Save edited translation content"""
        edited_content = self.result_text.get('1.0', tk.END).strip()
        self.translated_content_for_export = edited_content
        self._log_message("Changes saved successfully.")
        messagebox.showinfo("Success", "Changes have been saved.")
        
        # Update original translation to reflect saved changes
        self.original_translation = edited_content
        self.modified_sections.clear()
        self.result_text.tag_remove("modified", "1.0", tk.END)

# # The following _dummy_translation_progress and after_id have been removed and replaced with actual translation logic
# # self.after_id = self.master.after(1000, self._dummy_translation_progress)

# # def _dummy_translation_progress(self):
# # ... (dummy function content removed)


# if __name__ == '__main__':
#     # For testing when run standalone (commented out since run from main.py)
#     root = tk.Tk()
#     app = MainWindow(root)
#     root.mainloop() 