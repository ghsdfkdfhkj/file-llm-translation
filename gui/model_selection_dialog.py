import tkinter as tk
from tkinter import ttk, messagebox

class ModelSelectionDialog:
    def __init__(self, parent, models, current_model=None, all_models=None):
        self.top = tk.Toplevel(parent)
        self.top.title("Model Selection")
        self.top.geometry("400x400")
        self.top.resizable(False, False)
        
        # Set as modal dialog
        self.top.transient(parent)
        self.top.grab_set()
        
        # Center alignment
        self.top.update_idletasks()
        width = self.top.winfo_width()
        height = self.top.winfo_height()
        x = (self.top.winfo_screenwidth() // 2) - (width // 2)
        y = (self.top.winfo_screenheight() // 2) - (height // 2)
        self.top.geometry(f'+{x}+{y}')
        
        self.result = None
        self.latest_models = models
        self.all_models = all_models if all_models else models
        self.current_models = self.latest_models
        self.parent = parent
        
        # Main frame
        main_frame = ttk.Frame(self.top, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        
        # Top frame (description label and checkbox)
        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        top_frame.columnconfigure(1, weight=1)  # Push checkbox to the right
        
        # Description label
        description = ttk.Label(top_frame, text="Select a model to use:")
        description.grid(row=0, column=0, sticky=tk.W)
        
        # Show all models checkbox
        self.show_all_var = tk.BooleanVar(value=False)
        self.show_all_checkbox = ttk.Checkbutton(
            top_frame,
            text="Show All Models",
            variable=self.show_all_var,
            command=self._toggle_model_view
        )
        self.show_all_checkbox.grid(row=0, column=1, sticky=tk.E)
        
        # Create scrollable frame
        self.canvas = tk.Canvas(main_frame, width=380, height=280)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=360)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        scrollbar.grid(row=1, column=1, sticky="ns")
        
        # Radio button variable
        self.selected_model = tk.StringVar(value=current_model if current_model else "")
        
        # List to store radio buttons
        self.radio_buttons = []
        
        # Initial radio button creation
        self._create_radio_buttons()
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=tk.E, pady=(20, 0), padx=(0, 20))
        
        # Cancel/OK/Apply buttons
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text="Apply", command=self._on_apply).pack(side=tk.LEFT, padx=3)
        
        # Mouse wheel scroll binding
        self._bind_mouse_wheel()
        
        # Handle dialog close
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Keyboard shortcuts
        self.top.bind('<Return>', lambda e: self._on_ok())
        self.top.bind('<Escape>', lambda e: self._on_cancel())

    def _create_radio_buttons(self):
        """Create radio buttons"""
        # Remove existing radio buttons
        for rb in self.radio_buttons:
            rb.destroy()
        self.radio_buttons.clear()
        
        # Select models list to display
        models_to_show = self.all_models if self.show_all_var.get() else self.latest_models
        
        # Create new radio buttons
        style = ttk.Style()
        style.configure('Model.TRadiobutton', padding=5)  # Adjust radio button spacing
        
        for i, model in enumerate(models_to_show):
            rb = ttk.Radiobutton(
                self.scrollable_frame,
                text=model,
                value=model,
                variable=self.selected_model,
                style='Model.TRadiobutton'
            )
            rb.grid(row=i, column=0, sticky=tk.W, pady=2, padx=5)
            self.radio_buttons.append(rb)

    def _toggle_model_view(self):
        self._create_radio_buttons()

    def _bind_mouse_wheel(self):
        """Bind mouse wheel scroll event"""
        def _on_mousewheel(event):
            if self.canvas.winfo_exists():
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Remove previous binding
        self.top.unbind_all("<MouseWheel>")
        # Add new binding
        self.top.bind_all("<MouseWheel>", _on_mousewheel)

    def _unbind_mouse_wheel(self):
        """Unbind mouse wheel scroll event"""
        self.top.unbind_all("<MouseWheel>")

    def _on_apply(self):
        selected = self.selected_model.get()
        if not selected:
            messagebox.showwarning("Warning", "Please select a model.")
            return
        
        self.result = selected
        # Call parent window's callback function
        if hasattr(self.parent, '_on_model_selected'):
            self.parent._on_model_selected(selected)
            # Keep dialog open

    def _on_ok(self):
        selected = self.selected_model.get()
        if not selected:
            messagebox.showwarning("Warning", "Please select a model.")
            return
        
        self.result = selected
        self._unbind_mouse_wheel()
        self.top.destroy()

    def _on_cancel(self):
        self._unbind_mouse_wheel()
        self.result = None
        self.top.destroy()

    def show(self):
        # Disable parent window input and wait until dialog closes
        self.top.wait_window()
        return self.result 