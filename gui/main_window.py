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
        
        # Create a frame for the file path
        file_path_frame = ttk.Frame(file_input_frame)
        file_path_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        file_path_frame.columnconfigure(0, weight=1)
        
        # Create text widget for file path
        self.file_path_text = tk.Text(file_path_frame, height=1, wrap=tk.NONE)
        self.file_path_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Bind Return key to update file path
        def update_file_path(event=None):
            # Handle only one of the Return key or FocusOut events
            if event and event.keysym == 'Return' and hasattr(self, '_processing_event'):
                return 'break'
            if not event and hasattr(self, '_processing_event'):
                return
                
            setattr(self, '_processing_event', True)
            
            try:
                file_path = self.file_path_text.get('1.0', 'end-1c').strip()
                if os.path.exists(file_path):
                    self.input_file_path = file_path
                    self._log_message(f"File path updated: {file_path}")
                    if self.translator and self.translator.llm_service and self.current_model:
                        self.translate_button.config(state=tk.NORMAL)
                else:
                    self._log_message(f"Invalid file path: {file_path}")
                    self.translate_button.config(state=tk.DISABLED)
                    self.input_file_path = None
                    if file_path and event and event.keysym == 'Return':  # Only show warning on Enter key press
                        messagebox.showwarning("Invalid File Path", 
                            "The specified file path does not exist.\nPlease check the path and try again.")
            finally:
                delattr(self, '_processing_event')
            
            # Prevent default Enter key behavior
            if event and event.keysym == 'Return':
                return 'break'
        
        # Bind events
        self.file_path_text.bind('<Return>', update_file_path)
        self.file_path_text.bind('<FocusOut>', lambda e: update_file_path(None))
        
        # Prevent multiple lines
        def prevent_multiple_lines(event=None):
            content = self.file_path_text.get('1.0', 'end-1c')
            if '\n' in content:
                self.file_path_text.delete('1.0', tk.END)
                self.file_path_text.insert('1.0', content.replace('\n', ''))
                return 'break'
            
        self.file_path_text.bind('<KeyPress>', prevent_multiple_lines)
        
        self.input_file_path = None

        # Translation settings
        settings_frame = ttk.LabelFrame(left_frame, text="Translation Settings", padding="5")
        settings_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        settings_frame.columnconfigure(1, weight=1)
        
        # Chunk size input with tooltip
        chunk_size_label = ttk.Label(settings_frame, text="Chunk Size:")
        chunk_size_label.grid(row=0, column=0, sticky=tk.W)
        
        # Create a frame for chunk size input
        chunk_size_frame = ttk.Frame(settings_frame)
        chunk_size_frame.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        self.chunk_size_var = tk.StringVar(value="1000")  # Default chunk size
        self.chunk_size_entry = ttk.Entry(chunk_size_frame, textvariable=self.chunk_size_var, width=10)
        self.chunk_size_entry.pack(side=tk.LEFT)
        
        # Create tooltip window
        self.tooltip_window = None
        
        def create_tooltip():
            if self.tooltip_window:
                return
                
            # Create tooltip window
            self.tooltip_window = tk.Toplevel(self.master)
            self.tooltip_window.withdraw()  # Hide initially
            self.tooltip_window.overrideredirect(True)  # Remove window decorations
            
            # Create frame with border
            frame = ttk.Frame(self.tooltip_window, relief="solid", borderwidth=1)
            frame.pack(padx=1, pady=1)
            
            # Create tooltip content with multiple lines
            tooltip_text = [
                "Minimum chunk size: 100",
                "Maximum chunk size: 5000"
            ]
            
            # Style for tooltip labels
            style = ttk.Style()
            style.configure("Tooltip.TLabel", background='lightyellow', padding=(5, 2))
            
            for text in tooltip_text:
                label = ttk.Label(frame, text=text, style="Tooltip.TLabel")
                label.pack(fill=tk.X, padx=2, pady=1)
            
            # Configure tooltip background
            frame.configure(style="Tooltip.TFrame")
            style.configure("Tooltip.TFrame", background='lightyellow')
            
        def show_tooltip(event=None):
            create_tooltip()
            if self.tooltip_window:
                # Get the screen position of the entry widget
                x = self.chunk_size_entry.winfo_rootx()
                y = self.chunk_size_entry.winfo_rooty()
                
                # Position tooltip above the entry
                self.tooltip_window.deiconify()  # Show before calculating size
                tooltip_height = self.tooltip_window.winfo_height()
                self.tooltip_window.geometry(f"+{x}+{y-tooltip_height-5}")
                
                # Ensure tooltip stays on top
                self.tooltip_window.lift()
                
        def hide_tooltip(event=None):
            if self.tooltip_window:
                self.tooltip_window.withdraw()
        
        # Bind to focus events
        self.chunk_size_entry.bind("<FocusIn>", show_tooltip)
        self.chunk_size_entry.bind("<FocusOut>", hide_tooltip)
        
        # Also bind to hover events for better UX
        self.chunk_size_entry.bind("<Enter>", show_tooltip)
        self.chunk_size_entry.bind("<Leave>", hide_tooltip)
        
        # Output language selection
        output_lang_label = ttk.Label(settings_frame, text="Output Language:")
        output_lang_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
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
        self.output_lang_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=(5, 0))
        
        # Entry for custom input
        self.custom_lang_var = tk.StringVar()
        self.custom_lang_entry = ttk.Entry(settings_frame, textvariable=self.custom_lang_var)
        self.custom_lang_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5, pady=(5, 0))
        custom_lang_label = ttk.Label(settings_frame, text="Custom Output:")
        custom_lang_label.grid(row=2, column=0, sticky=tk.W, pady=(5, 0))

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

        # Button frame for translation and export - expanded for more buttons
        button_frame = ttk.Frame(left_frame)
        button_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        # First row of buttons
        first_row = ttk.Frame(button_frame)
        first_row.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        first_row.columnconfigure(0, weight=1)
        first_row.columnconfigure(1, weight=1)

        # Translation button
        self.translate_button = ttk.Button(first_row, text="Start Translation", command=self.start_translation)
        self.translate_button.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.translate_button.config(state=tk.DISABLED)

        # Export button
        self.export_button = ttk.Button(first_row, text="Export Translated File", command=self.export_file_dialog, state=tk.DISABLED)
        self.export_button.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))

        # Second row of buttons
        second_row = ttk.Frame(button_frame)
        second_row.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        second_row.columnconfigure(0, weight=1)
        second_row.columnconfigure(1, weight=1)
        second_row.columnconfigure(2, weight=1)
        
        # Find untranslated parts button
        self.find_untranslated_button = ttk.Button(
            second_row, 
            text="Find Untranslated",
            command=self.find_untranslated_parts,
            state=tk.DISABLED
        )
        self.find_untranslated_button.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 3))
        
        # Detailed analysis button - NEW
        self.detailed_analysis_button = ttk.Button(
            second_row,
            text="Detailed Analysis",
            command=self.show_detailed_analysis,
            state=tk.DISABLED
        )
        self.detailed_analysis_button.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(3, 3))
        
        # Retranslate selected parts button
        self.retranslate_button = ttk.Button(
            second_row, 
            text="Retranslate", 
            command=self.retranslate_untranslated_parts,
            state=tk.DISABLED
        )
        self.retranslate_button.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=(3, 0))

        # Log area
        log_label = ttk.Label(left_frame, text="Log")
        log_label.grid(row=8, column=0, sticky=tk.W, pady=(0, 2))
        
        log_frame = ttk.Frame(left_frame)
        log_frame.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = log_scrollbar.set

        # === Right frame content ===
        # Result text area with scrollbar
        result_frame = ttk.Frame(right_frame)
        result_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)

        self.result_text = tk.Text(result_frame, wrap=tk.WORD, width=60, height=30)
        self.result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.result_text.config(state=tk.NORMAL)  # Make editable initially
        
        # Configure tags for highlighting with enhanced styles
        self.result_text.tag_configure("untranslated", background="#ffcccc", foreground="#cc0000", font=("TkDefaultFont", "10", "bold"))  # Light red background, red text
        self.result_text.tag_configure("low_confidence", background="#fff3cd", foreground="#856404", font=("TkDefaultFont", "10", "italic"))  # Light yellow background, dark yellow text
        self.result_text.tag_configure("modified", background="#d4edda", foreground="#155724", font=("TkDefaultFont", "10", "bold"))  # Light green background, green text
        self.result_text.tag_configure("high_confidence", background="#d1ecf1", foreground="#0c5460")  # Light blue background for high confidence areas
        
        result_scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_text.yview)
        result_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.result_text['yscrollcommand'] = result_scrollbar.set
        
        # Add events for text modifications
        self.result_text.bind("<<Modified>>", self._on_text_modified)
        self.result_text.bind("<KeyRelease>", self._on_text_modified)  # Add key release event
        self.result_text.bind("<ButtonRelease-1>", self._on_text_modified)  # Mouse button release
        self.result_text.bind("<ButtonRelease-2>", self._on_text_modified)  # Middle button release
        self.result_text.bind("<ButtonRelease-3>", self._on_text_modified)  # Right button release
        
        # Initial state of translate button based on text content
        if self.result_text.get("1.0", tk.END).strip():
            self.translate_button.config(state=tk.NORMAL)
        else:
            self.translate_button.config(state=tk.DISABLED)

        # Add progress bar (moved from left_frame)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            right_frame, 
            orient=tk.HORIZONTAL, 
            length=200, 
            mode='determinate', 
            variable=self.progress_var
        )
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        self.progress_bar.grid_remove()  # Hide initially

        # Frame settings
        main_frame.columnconfigure(0, weight=0)  # Left is fixed size
        main_frame.columnconfigure(1, weight=1)  # Right is expandable
        main_frame.rowconfigure(0, weight=1)
        
        left_frame.columnconfigure(1, weight=1)
        left_frame.rowconfigure(9, weight=1)  # Log area is expandable
        
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)  # Result area is expandable

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

        # Load chunk size
        last_chunk_size = settings.get("last_chunk_size", "1000")
        try:
            chunk_size = int(last_chunk_size)
            if 100 <= chunk_size <= 5000:
                self.chunk_size_var.set(last_chunk_size)
        except ValueError:
            self.chunk_size_var.set("1000")  # Default if invalid

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
            "last_output_language_custom": self.custom_lang_var.get(),
            "last_chunk_size": self.chunk_size_var.get()  # Save chunk size
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
            self.file_path_text.delete('1.0', tk.END)
            self.file_path_text.insert('1.0', filepath)
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
        """Handle model selection from dialog"""
        self.current_model = selected_model
        self.selected_model_var.set(f"Selected Model: {selected_model}")
        
        # Set the current model in the translator
        if self.translator:
            self.translator.current_model = selected_model
            
        self._update_translate_button_state()

    def _update_translate_button_state(self):
        """Update translation button state"""
        if self.translator and self.translator.llm_service and self.input_file_path and self.current_model:
            self.translate_button.config(state=tk.NORMAL)
        else:
            self.translate_button.config(state=tk.DISABLED)

    def _log_message(self, message):
        """Log a message to the log area with timestamp"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # Enable log text for editing
        self.log_text.config(state=tk.NORMAL)
        
        # Insert log message at the end
        self.log_text.insert(tk.END, log_entry)
        
        # Autoscroll to the end
        self.log_text.see(tk.END)
        
        # Disable editing again
        self.log_text.config(state=tk.DISABLED)
        
        # Also print to console for debugging
        print(log_entry, end='')

    def _show_translation_result(self, result):
        """Display the translation result in the text area"""
        self.result_text.config(state=tk.NORMAL)  # Enable editing
        self.result_text.delete("1.0", tk.END)    # Clear existing content
        self.result_text.insert("1.0", result)    # Insert new content
        self.translated_content_for_export = result

    def _on_text_modified(self, event=None):
        """Handle text modification events"""
        # Update all buttons state based on text content
        current_text = self.result_text.get("1.0", tk.END).strip()
        
        # Set button states based on text content
        if current_text:
            # Initialize translator if not already initialized
            if not self.translator:
                llm_provider = self.llm_var.get()
                api_key = self.api_key_var.get()
                
                if llm_provider and api_key:
                    try:
                        self.translator = Translator(llm_provider_name=llm_provider, api_key=api_key)
                        self._log_message(f"{llm_provider} service has been initialized.")
                    except Exception as e:
                        self._log_message(f"Error initializing translator: {e}")
            
            # Enable translation button if translator service is ready
            if self.translator and self.translator.llm_service and self.current_model:
                self.translate_button.config(state=tk.NORMAL)
            
            # Store text content for translation
            self.translated_content_for_export = current_text
            
            # Enable other buttons
            self.export_button.config(state=tk.NORMAL)
            self.find_untranslated_button.config(state=tk.NORMAL)
            self.detailed_analysis_button.config(state=tk.NORMAL)
            
            # Enable retranslate button only if there's a translator
            if self.translator and self.translator.llm_service:
                self.retranslate_button.config(state=tk.NORMAL)
        else:
            # Disable all buttons if no text content
            self.translate_button.config(state=tk.DISABLED)
            self.export_button.config(state=tk.DISABLED)
            self.find_untranslated_button.config(state=tk.DISABLED)
            self.detailed_analysis_button.config(state=tk.DISABLED)
            self.retranslate_button.config(state=tk.DISABLED)
            self.translated_content_for_export = None

        if not self.original_translation:
            return
        
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
            self.file_path_text.delete('1.0', tk.END)
            self.file_path_text.insert('1.0', filepath)
            self._log_message(f"Input file selected: {filepath}")
            # Enable translation button if LLM service is ready
            if self.translator and self.translator.llm_service and self.current_model:
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
        
        # Disable translation button and make text area read-only during translation
        self.translate_button.config(state=tk.DISABLED)
        self.export_button.config(state=tk.DISABLED)
        self.result_text.config(state=tk.DISABLED)  # Make text area read-only
        self.translated_content_for_export = None

        # Run translation in background thread (prevent GUI blocking)
        import threading
        thread = threading.Thread(target=self._execute_translation, 
                                args=(self.input_file_path, output_language, self.current_model))
        thread.start()

    def _execute_translation(self, input_file, output_language, model):
        try:
            # Get chunk size from input field
            try:
                chunk_size = int(self.chunk_size_var.get())
                if chunk_size < 100:  # Minimum chunk size
                    chunk_size = 100
                    self.chunk_size_var.set("100")
                elif chunk_size > 5000:  # Maximum chunk size
                    chunk_size = 5000
                    self.chunk_size_var.set("5000")
            except ValueError:
                chunk_size = 1000  # Default if invalid input
                self.chunk_size_var.set("1000")
                self._log_message("Invalid chunk size input. Using default size: 1000")

            def update_translation_result(current_translation):
                # Update the result text in the main thread
                self.master.after(0, lambda: self._update_translation_result(current_translation))

            # self.translator is already set in _perform_service_update
            translated_content = self.translator.translate_file(
                input_file, 
                output_language, 
                model,
                chunk_size=chunk_size,  # Pass chunk size to translator
                progress_callback=self._log_message,  # Pass callback function
                update_callback=update_translation_result  # Pass update callback
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
            # Handle final GUI updates in main thread using master.after
            self.master.after(0, self._on_translation_complete, translated_content)

        except Exception as e:
            error_message = f"Critical error during translation: {e}"
            self._log_message(error_message)
            self.master.after(0, self._on_translation_failed)

    def _update_translation_result(self, current_translation):
        """Update translation results in real-time"""
        # Temporarily enable editing to update content
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert(tk.END, current_translation if current_translation else "")
        self.result_text.see(tk.END)  # Scroll to the latest content
        # Make read-only again during translation
        self.result_text.config(state=tk.DISABLED)

    def _on_translation_complete(self, translated_content):
        """Handle translation completion"""
        if not translated_content.strip():
            self._log_message("Translation failed: No content was translated.")
            self._show_translation_result("Translation failed. Please check the log for details.")
            self.translate_button.config(state=tk.NORMAL)
            self.export_button.config(state=tk.DISABLED)
            self.find_untranslated_button.config(state=tk.DISABLED)
            self.detailed_analysis_button.config(state=tk.DISABLED)
            self.retranslate_button.config(state=tk.DISABLED)
            self.result_text.config(state=tk.NORMAL)  # Re-enable text editing
            return
            
        self._log_message("Translation completed successfully.")
        self._show_translation_result(translated_content)
        
        self.translated_content_for_export = translated_content
        self.original_translation = translated_content  # Store original for comparison
        
        self.translate_button.config(state=tk.NORMAL)  # Re-enable translation button
        self.export_button.config(state=tk.NORMAL)  # Enable export button
        self.find_untranslated_button.config(state=tk.NORMAL)  # Enable find untranslated button
        self.detailed_analysis_button.config(state=tk.NORMAL)  # Enable detailed analysis button
        self.retranslate_button.config(state=tk.DISABLED)  # Disable retranslate button until untranslated parts are found
        self.result_text.config(state=tk.NORMAL)  # Re-enable text editing

    def _on_translation_failed(self):
        messagebox.showerror("Translation Failed", "Translation process encountered an error. Please check the log.")
        self.translate_button.config(state=tk.NORMAL)
        self.export_button.config(state=tk.DISABLED)
        self.find_untranslated_button.config(state=tk.DISABLED)
        self.detailed_analysis_button.config(state=tk.DISABLED)
        self.retranslate_button.config(state=tk.DISABLED)
        self.result_text.config(state=tk.NORMAL)  # Re-enable text editing

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
                ("All files", "*.*"),
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

    def find_untranslated_parts(self):
        """Enhanced find and highlight parts that were not translated properly with detailed analysis."""
        if not self.translator or not self.translated_content_for_export:
            messagebox.showwarning("Warning", "No translation available to check.")
            return
            
        target_language = self.get_target_language()
        if not target_language:
            messagebox.showwarning("Warning", "Please select a target language first.")
            return
            
        # Get the current content from the text widget
        current_content = self.result_text.get("1.0", tk.END)
        
        # ----- Async untranslated detection start -----
        self.result_text.tag_remove("untranslated", "1.0", tk.END)
        self.result_text.tag_remove("low_confidence", "1.0", tk.END)

        # Show an indeterminate progress bar while detection runs in background
        self.progress_var.set(0)
        self.progress_bar.config(mode='indeterminate')
        self.progress_bar.grid()
        self.progress_bar.start(10)

        # Launch background thread to perform detection without blocking GUI
        import threading
        threading.Thread(
            target=self._execute_untranslated_detection,
            args=(current_content, target_language),
            daemon=True
        ).start()
        return  # The original synchronous implementation below is kept but no longer executed
        # ----- Async untranslated detection end -----

    def retranslate_untranslated_parts(self):
        """Retranslate the untranslated parts of the text."""
        if not hasattr(self, 'untranslated_lines') or not self.untranslated_lines:
            messagebox.showwarning("Warning", "No untranslated parts to retranslate.")
            return
            
        if not self.translator or not self.translator.llm_service:
            messagebox.showwarning("Warning", "Translator service is not available.")
            return
            
        target_language = self.get_target_language()
        if not target_language:
            messagebox.showwarning("Warning", "Please select a target language first.")
            return
        
        # Disable buttons during retranslation and make text area read-only
        self.retranslate_button.config(state=tk.DISABLED)
        self.translate_button.config(state=tk.DISABLED)
        self.find_untranslated_button.config(state=tk.DISABLED)
        self.detailed_analysis_button.config(state=tk.DISABLED)
        self.result_text.config(state=tk.DISABLED)  # Make text area read-only
        
        # Get the current content from the text widget
        current_content = self.result_text.get("1.0", tk.END)
        
        # Store current untranslated lines for the background thread
        untranslated_lines_copy = self.untranslated_lines.copy()
        
        # Clear the UI untranslated lines immediately
        self.untranslated_lines = []
        
        self._log_message(f"Starting retranslation of {len(untranslated_lines_copy)} untranslated sections...")
        
        # Run retranslation in background thread
        import threading
        thread = threading.Thread(
            target=self._execute_retranslation, 
            args=(current_content, untranslated_lines_copy, target_language, self.current_model)
        )
        thread.start()
    
    def _execute_retranslation(self, current_content, untranslated_lines, target_language, model):
        """Execute retranslation in background thread with progress updates."""
        try:
            def progress_callback(message):
                # Update progress in main thread
                self.master.after(0, lambda: self._log_message(message))
                
                # Extract progress percentage if available
                if "Progress:" in message:
                    try:
                        progress_str = message.split("Progress:")[1].split("%")[0].strip()
                        progress_val = float(progress_str)
                        self.master.after(0, lambda: self._update_retranslation_progress(progress_val))
                    except:
                        pass
            
            # Show progress bar
            self.master.after(0, lambda: self.progress_bar.grid())
            self.master.after(0, lambda: self.progress_var.set(0))
            
            # Perform retranslation
            updated_content = self.translator.retranslate_untranslated_sections(
                current_content,
                untranslated_lines,
                target_language,
                model,
                progress_callback
            )
            
            # Update UI in main thread
            self.master.after(0, lambda: self._on_retranslation_complete(updated_content, untranslated_lines))
            
        except Exception as e:
            error_message = f"Error during retranslation: {e}"
            self.master.after(0, lambda: self._log_message(error_message))
            self.master.after(0, lambda: self._on_retranslation_failed())
    
    def _update_retranslation_progress(self, progress_value):
        """Update progress bar during retranslation."""
        self.progress_var.set(progress_value)
        self.master.update_idletasks()
    
    def _on_retranslation_complete(self, updated_content, retranslated_lines):
        """Handle retranslation completion in main thread."""
        try:
            # Enable text area for editing before updating content
            self.result_text.config(state=tk.NORMAL)
            
            # Update the result text
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert("1.0", updated_content)
            
            # Clear untranslated highlights and add modified highlights
            self.result_text.tag_remove("untranslated", "1.0", tk.END)
            self.result_text.tag_remove("low_confidence", "1.0", tk.END)
            
            for line_idx, _ in retranslated_lines:
                # Calculate the text positions
                line_start = f"{line_idx + 1}.0"
                line_end = f"{line_idx + 1}.end"
                
                # Apply the modified tag
                self.result_text.tag_add("modified", line_start, line_end)
                
            # Update the content for export
            self.translated_content_for_export = updated_content
            
            self._log_message(f"Retranslation completed successfully. {len(retranslated_lines)} sections updated.")
            
            # Show success message
            messagebox.showinfo("Retranslation Complete", 
                              f"Successfully retranslated {len(retranslated_lines)} sections.\n"
                              f"Modified lines are highlighted in green.")
            
        except Exception as e:
            self._log_message(f"Error updating UI after retranslation: {e}")
        finally:
            self._reset_retranslation_ui()
    
    def _on_retranslation_failed(self):
        """Handle retranslation failure in main thread."""
        # Re-enable text area editing
        self.result_text.config(state=tk.NORMAL)
        
        messagebox.showerror("Retranslation Failed", 
                           "Retranslation process encountered an error. Please check the log for details.")
        self._reset_retranslation_ui()
    
    def _reset_retranslation_ui(self):
        """Reset UI elements after retranslation completion or failure."""
        # Hide progress bar
        self.progress_bar.grid_remove()
        
        # Re-enable buttons
        self.translate_button.config(state=tk.NORMAL)
        self.find_untranslated_button.config(state=tk.NORMAL)
        self.detailed_analysis_button.config(state=tk.NORMAL)
        self.retranslate_button.config(state=tk.DISABLED)  # Will be enabled again when untranslated parts are found

    def show_detailed_analysis(self):
        """Show comprehensive translation quality analysis with detailed insights."""
        if not self.translator or not self.translated_content_for_export:
            messagebox.showwarning("Warning", "No translation available to analyze.")
            return
            
        target_language = self.get_target_language()
        if not target_language:
            messagebox.showwarning("Warning", "Please select a target language first.")
            return
            
        # Get the current content from the text widget
        current_content = self.result_text.get("1.0", tk.END)
        
        # Show progress while analyzing
        self.progress_var.set(0)
        self.progress_bar.grid()
        self.master.update_idletasks()
        
        try:
            # Perform comprehensive analysis
            self.progress_var.set(25)
            self.master.update_idletasks()
            
            analysis_results = self.translator.analyze_translation_quality(
                current_content, 
                target_language
            )
            
            self.progress_var.set(75)
            self.master.update_idletasks()
            
            # Create detailed analysis window
            self._show_analysis_results_window(analysis_results, target_language)
            
            self.progress_var.set(100)
            self.master.update_idletasks()
            
            # Log summary
            self._log_message("=== Detailed Translation Analysis Complete ===")
            self._log_message(f"Overall Quality Score: {analysis_results['overall_quality_score']:.1f}/100")
            self._log_message(f"Quality Grade: {analysis_results['quality_grade']}")
            self._log_message(f"Issues Found: {len(analysis_results['quality_issues'])}")
            self._log_message(f"Recommendations: {len(analysis_results['recommendations'])}")
            
        except Exception as e:
            self._log_message(f"Error during detailed analysis: {e}")
            messagebox.showerror("Analysis Error", f"Error during detailed analysis:\n{e}")
        finally:
            # Hide progress bar
            self.progress_bar.grid_remove()
    
    def _show_analysis_results_window(self, analysis_results, target_language):
        """Display detailed analysis results in a new window."""
        # Create new window
        analysis_window = tk.Toplevel(self.master)
        analysis_window.title(f"Translation Quality Analysis - {target_language}")
        analysis_window.geometry("800x600")
        analysis_window.resizable(True, True)
        
        # Create notebook for different analysis tabs
        notebook = ttk.Notebook(analysis_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # === Overview Tab ===
        overview_frame = ttk.Frame(notebook)
        notebook.add(overview_frame, text="Overview")
        
        # Quality score display
        score_frame = ttk.LabelFrame(overview_frame, text="Quality Assessment")
        score_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Quality score with color coding
        score = analysis_results['overall_quality_score']
        grade = analysis_results['quality_grade']
        
        if score >= 80:
            score_color = "#28a745"  # Green
        elif score >= 60:
            score_color = "#ffc107"  # Yellow
        else:
            score_color = "#dc3545"  # Red
        
        score_label = tk.Label(
            score_frame, 
            text=f"Overall Quality Score: {score:.1f}/100 ({grade})",
            font=("TkDefaultFont", 14, "bold"),
            fg=score_color
        )
        score_label.pack(pady=10)
        
        # Basic statistics
        stats_frame = ttk.LabelFrame(overview_frame, text="Translation Statistics")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        stats = analysis_results['basic_stats']
        stats_text = tk.Text(stats_frame, height=8, wrap=tk.WORD)
        stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        stats_content = f"""Total Lines: {stats['total_lines']}
Non-empty Lines: {stats['non_empty_lines']}
Keyword-only Lines: {stats['keyword_only_lines']}
Lines with Quoted Content: {stats.get('quoted_content_analyzed', 0)}
Quoted Content Needing Translation: {stats.get('quoted_untranslated', 0)}
Untranslated Lines: {stats['untranslated_lines']}
Average Confidence: {stats['confidence_avg']:.1%}

Translation Success Rate: {((stats['non_empty_lines'] - stats['untranslated_lines']) / max(stats['non_empty_lines'], 1)) * 100:.1f}%
Lines Requiring Review: {len(analysis_results['untranslated_lines'])}"""
        
        # Add quoted content success rate if applicable
        if stats.get('quoted_content_analyzed', 0) > 0:
            quoted_success = ((stats['quoted_content_analyzed'] - stats.get('quoted_untranslated', 0)) / stats['quoted_content_analyzed']) * 100
            stats_content += f"\nQuoted Content Success Rate: {quoted_success:.1f}%"
        
        stats_text.insert(tk.END, stats_content)
        stats_text.config(state=tk.DISABLED)
        
        # === Issues Tab ===
        issues_frame = ttk.Frame(notebook)
        notebook.add(issues_frame, text="Issues Found")
        
        issues_text = tk.Text(issues_frame, wrap=tk.WORD)
        issues_scrollbar = ttk.Scrollbar(issues_frame, orient=tk.VERTICAL, command=issues_text.yview)
        issues_text.config(yscrollcommand=issues_scrollbar.set)
        
        issues_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        issues_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        
        if analysis_results['quality_issues']:
            for i, issue in enumerate(analysis_results['quality_issues'], 1):
                severity_color = {
                    'high': '🔴',
                    'medium': '🟡', 
                    'low': '🟢'
                }.get(issue['severity'], '⚪')
                
                issues_text.insert(tk.END, f"{severity_color} Issue #{i}: {issue['description']}\n")
                issues_text.insert(tk.END, f"   Severity: {issue['severity'].title()}\n")
                issues_text.insert(tk.END, f"   Count: {issue['count']} lines affected\n")
                
                if issue.get('lines'):
                    issues_text.insert(tk.END, f"   Examples:\n")
                    for line_idx, line_content in issue['lines'][:3]:
                        issues_text.insert(tk.END, f"     Line {line_idx + 1}: {line_content[:100]}...\n")
                
                issues_text.insert(tk.END, "\n")
        else:
            issues_text.insert(tk.END, "🎉 No significant issues detected!\n\nYour translation appears to be of high quality.")
        
        issues_text.config(state=tk.DISABLED)
        
        # === Recommendations Tab ===
        recommendations_frame = ttk.Frame(notebook)
        notebook.add(recommendations_frame, text="Recommendations")
        
        rec_text = tk.Text(recommendations_frame, wrap=tk.WORD)
        rec_scrollbar = ttk.Scrollbar(recommendations_frame, orient=tk.VERTICAL, command=rec_text.yview)
        rec_text.config(yscrollcommand=rec_scrollbar.set)
        
        rec_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        rec_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        
        if analysis_results['recommendations']:
            rec_text.insert(tk.END, "Recommendations to improve translation quality:\n\n")
            for i, recommendation in enumerate(analysis_results['recommendations'], 1):
                rec_text.insert(tk.END, f"{i}. {recommendation}\n\n")
        else:
            rec_text.insert(tk.END, "Excellent work! No specific recommendations at this time.\n\nYour translation meets high quality standards.")
        
        # Add language-specific suggestions if available
        lang_analysis = analysis_results.get('language_specific_analysis', {})
        if lang_analysis.get('suggestions'):
            rec_text.insert(tk.END, f"\n{target_language}-specific suggestions:\n\n")
            for suggestion in lang_analysis['suggestions']:
                rec_text.insert(tk.END, f"• {suggestion}\n")
        
        rec_text.config(state=tk.DISABLED)
        
        # === Confidence Details Tab ===
        confidence_frame = ttk.Frame(notebook)
        notebook.add(confidence_frame, text="Confidence Analysis")
        
        conf_text = tk.Text(confidence_frame, wrap=tk.WORD, font=("Courier", 10))
        conf_scrollbar = ttk.Scrollbar(confidence_frame, orient=tk.VERTICAL, command=conf_text.yview)
        conf_text.config(yscrollcommand=conf_scrollbar.set)
        
        conf_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        conf_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        
        conf_text.insert(tk.END, "Line-by-line Confidence Analysis:\n\n")
        conf_text.insert(tk.END, "Line | Confidence | Status\n")
        conf_text.insert(tk.END, "-" * 40 + "\n")
        
        confidence_scores = analysis_results['confidence_scores']
        untranslated_line_indices = {idx for idx, _ in analysis_results['untranslated_lines']}
        
        for line_idx, confidence in confidence_scores:
            confidence_percent = confidence * 100
            if line_idx in untranslated_line_indices:
                status = "❌ Needs retranslation"
            elif confidence >= 0.8:
                status = "✅ High quality"
            elif confidence >= 0.6:
                status = "⚠️  Review recommended"
            else:
                status = "🔍 Low confidence"
            
            conf_text.insert(tk.END, f"{line_idx + 1:4d} | {confidence_percent:8.1f}% | {status}\n")
        
        conf_text.config(state=tk.DISABLED)
        
        # Add close button
        button_frame = ttk.Frame(analysis_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        close_button = ttk.Button(
            button_frame, 
            text="Close", 
            command=analysis_window.destroy
        )
        close_button.pack(side=tk.RIGHT)
        
        # Make window modal
        analysis_window.transient(self.master)
        analysis_window.grab_set()
        analysis_window.focus_set()

    # === New asynchronous untranslated detection helpers ===
    def _execute_untranslated_detection(self, current_content, target_language):
        """Run untranslated detection in a background thread."""
        try:
            detection_results = self.translator.detect_untranslated_sections(current_content, target_language)
            self.master.after(0, lambda dr=detection_results, tl=target_language: self._on_untranslated_detection_complete(dr, tl))
        except Exception as e:
            self.master.after(0, lambda err=e: self._on_untranslated_detection_failed(err))

    def _on_untranslated_detection_complete(self, detection_results, target_language):
        """Process detection results on the Tkinter main thread."""
        # Stop the indeterminate bar and switch back to determinate mode
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate')
        self.progress_var.set(50)
        self.master.update_idletasks()

        try:
            untranslated_lines = detection_results['untranslated_lines']
            stats = detection_results['stats']
            confidence_scores = detection_results['confidence_scores']

            # Log statistics
            self._log_message(f"=== Enhanced Translation Quality Analysis for {target_language} ===")
            self._log_message(f"Total lines: {stats['total_lines']}")
            self._log_message(f"Non-empty lines: {stats['non_empty_lines']}")
            self._log_message(f"Keyword-only lines (skipped): {stats['keyword_only_lines']}")
            self._log_message(f"Lines with quoted content: {stats['quoted_content_analyzed']}")
            self._log_message(f"Quoted content requiring translation: {stats['quoted_untranslated']}")
            self._log_message(f"Untranslated lines detected: {stats['untranslated_lines']}")
            self._log_message(f"Average confidence score: {stats['confidence_avg']:.2f}")

            if stats['non_empty_lines'] > 0:
                translation_rate = ((stats['non_empty_lines'] - stats['untranslated_lines']) / stats['non_empty_lines']) * 100
                self._log_message(f"Translation success rate: {translation_rate:.1f}%")

            if stats['quoted_content_analyzed'] > 0:
                quoted_success_rate = ((stats['quoted_content_analyzed'] - stats['quoted_untranslated']) / stats['quoted_content_analyzed']) * 100
                self._log_message(f"Quoted content translation rate: {quoted_success_rate:.1f}%")

            # Highlight untranslated parts
            low_confidence_lines = []
            for line_idx, line in untranslated_lines:
                line_start = f"{line_idx + 1}.0"
                line_end = f"{line_idx + 1}.end"
                line_confidence = next((c for idx, c in confidence_scores if idx == line_idx), 0.0)
                if line_confidence < 0.3:
                    self.result_text.tag_add("untranslated", line_start, line_end)
                else:
                    self.result_text.tag_add("low_confidence", line_start, line_end)
                    low_confidence_lines.append((line_idx, line))

            # Final progress update
            self.progress_var.set(100)
            self.master.update_idletasks()

            # Enable retranslation button if needed and store lines
            if untranslated_lines:
                self.retranslate_button.config(state=tk.NORMAL)
            self.untranslated_lines = untranslated_lines

            # Build result message
            result_msg = f"Enhanced Translation Analysis Results:\n\n"
            result_msg += "General Statistics:\n"
            result_msg += f"• Total lines: {stats['total_lines']}\n"
            result_msg += f"• Analyzed lines: {stats['non_empty_lines']}\n"
            result_msg += f"• Untranslated lines: {len(untranslated_lines)}\n"
            result_msg += f"• Low confidence lines: {len(low_confidence_lines)}\n"
            result_msg += f"• Average confidence: {stats['confidence_avg']:.1%}\n\n"

            if stats['quoted_content_analyzed'] > 0:
                result_msg += "Quoted Content Analysis:\n"
                result_msg += f"• Lines with quoted content: {stats['quoted_content_analyzed']}\n"
                result_msg += f"• Quoted content needing translation: {stats['quoted_untranslated']}\n"
                quoted_success = ((stats['quoted_content_analyzed'] - stats['quoted_untranslated']) / stats['quoted_content_analyzed']) * 100
                result_msg += f"• Quoted content success rate: {quoted_success:.1f}%\n\n"

            result_msg += "Highlighting Legend:\n"
            result_msg += "• Red background: Definitely untranslated\n"
            result_msg += "• Yellow background: Low confidence (review recommended)\n\n"

            if stats['quoted_untranslated'] > 0:
                result_msg += f"Focus Areas:\n• {stats['quoted_untranslated']} quoted strings detected in wrong language\n\n"

            if stats['confidence_avg'] < 0.5:
                result_msg += "Low overall confidence detected.\nConsider checking translation model and target language settings."
            elif len(untranslated_lines) > stats['non_empty_lines'] * 0.1:
                result_msg += "Language mismatches found in content.\nYou can use 'Retranslate' to fix the highlighted parts."
            else:
                result_msg += f"Most content appears to be well translated!\nLanguage detection shows good compliance with {target_language}."

            if untranslated_lines:
                first_line = untranslated_lines[0][0] + 1
                self.result_text.see(f"{first_line}.0")
                self._log_message(f"Scrolled to first untranslated line: {first_line}")

            messagebox.showinfo("Translation Analysis Complete", result_msg)

        except Exception as e:
            self._log_message(f"Error during translation analysis: {e}")
            messagebox.showerror("Analysis Error", f"Error during translation analysis:\n{e}")
        finally:
            self.progress_bar.grid_remove()

    def _on_untranslated_detection_failed(self, error):
        """Handle errors from background untranslated detection."""
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate')
        self.progress_bar.grid_remove()
        self._log_message(f"Error during translation analysis: {error}")
        messagebox.showerror("Analysis Error", f"Error during translation analysis:\n{error}")

# # The following _dummy_translation_progress and after_id have been removed and replaced with actual translation logic
# # self.after_id = self.master.after(1000, self._dummy_translation_progress)

# # def _dummy_translation_progress(self):
# # ... (dummy function content removed)


# if __name__ == '__main__':
#     # For testing when run standalone (commented out since run from main.py)
#     root = tk.Tk()
#     app = MainWindow(root)
#     root.mainloop() 