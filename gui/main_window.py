import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from translation_core.translator import Translator # Translator 임포트
from utils.config_manager import save_api_key, load_api_key # API 키 저장/로드를 위해 추가

class MainWindow:
    def __init__(self, master):
        self.master = master
        master.title("게임 번역 프로그램")
        master.geometry("800x650") # 높이 약간 늘림

        self.translator = None # Translator 인스턴스
        self.translated_content_for_export = None # 내보낼 컨텐츠

        # Main frame
        main_frame = ttk.Frame(master, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)

        # LLM 선택
        llm_label = ttk.Label(main_frame, text="LLM 선택:")
        llm_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.llm_var = tk.StringVar()
        self.llm_combo_box = ttk.Combobox(main_frame, textvariable=self.llm_var, state="readonly")
        self.llm_combo_box['values'] = ("OpenAI", "Anthropic", "Google Gemini") # Translator와 일치해야 함
        self.llm_combo_box.current(0)
        self.llm_combo_box.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        self.llm_combo_box.bind("<<ComboboxSelected>>", self._on_llm_provider_changed)

        # API 키 입력
        api_key_label = ttk.Label(main_frame, text="API 키:")
        api_key_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(main_frame, show="*", textvariable=self.api_key_var)
        self.api_key_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        self.api_key_entry.bind("<FocusOut>", self._on_api_key_focus_out) # 포커스 아웃 시 저장

        # 모델 선택
        self.model_frame = ttk.LabelFrame(main_frame, text="모델 선택") # 초기에는 비어있음
        self.model_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5, padx=2)
        self.model_var = tk.StringVar()
        self.model_status_label = ttk.Label(self.model_frame, text="LLM을 선택하고 API 키를 입력하세요.")
        self.model_status_label.pack(anchor=tk.W, padx=5, pady=5)

        # 출력 언어 선택
        output_lang_label = ttk.Label(main_frame, text="출력 언어 선택:")
        output_lang_label.grid(row=3, column=0, sticky=tk.W, pady=5)
        self.output_lang_var = tk.StringVar()
        self.output_lang_combo_box = ttk.Combobox(main_frame, textvariable=self.output_lang_var, state="readonly")
        self.output_lang_combo_box['values'] = [
            "Korean", "English", "Japanese", "Chinese (Simplified)",
            "Chinese (Traditional)", "Spanish", "French",
            "German", "Russian", "Vietnamese", "Thai"
        ]
        self.output_lang_combo_box.current(0)
        self.output_lang_combo_box.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)

        # 파일 입력 프레임
        file_input_frame = ttk.Frame(main_frame)
        file_input_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        file_input_frame.columnconfigure(1, weight=1)

        self.file_input_button = ttk.Button(file_input_frame, text="번역할 파일 선택", command=self.open_file_dialog)
        self.file_input_button.grid(row=0, column=0, sticky=tk.W)
        self.selected_file_label = ttk.Label(file_input_frame, text="선택된 파일: 없음")
        self.selected_file_label.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.input_file_path = None

        # 번역 실행 버튼
        self.translate_button = ttk.Button(main_frame, text="번역 실행", command=self.start_translation, state=tk.DISABLED)
        self.translate_button.grid(row=5, column=0, columnspan=2, pady=10)

        # 결과 표시 (또는 진행 상황)
        result_frame = ttk.LabelFrame(main_frame, text="번역 결과 및 로그")
        result_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)

        self.result_text = tk.Text(result_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.result_text['yscrollcommand'] = scrollbar.set

        # 파일 내보내기 버튼
        self.export_button = ttk.Button(main_frame, text="번역 파일 내보내기", command=self.export_file_dialog, state=tk.DISABLED)
        self.export_button.grid(row=7, column=0, columnspan=2, pady=(5,0))
        
        main_frame.columnconfigure(1, weight=1)

        self._on_llm_provider_changed() # Initial call to load saved key for default provider and update service

    def _log_message(self, message):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, message + "\n")
        self.result_text.see(tk.END)
        self.result_text.config(state=tk.DISABLED)

    def _on_llm_provider_changed(self, event=None):
        llm_provider = self.llm_var.get()
        if llm_provider:
            loaded_key = load_api_key(llm_provider)
            if loaded_key:
                self.api_key_var.set(loaded_key)
                self._log_message(f"{llm_provider}의 저장된 API 키를 로드했습니다.")
            else:
                self.api_key_var.set("") # No saved key for this provider, clear the field
                self._log_message(f"{llm_provider}에 대해 저장된 API 키가 없습니다. 새로 입력해주세요.")
        self._perform_service_update() # Update service after provider change and key loading

    def _save_current_api_key(self):
        llm_provider = self.llm_var.get()
        api_key = self.api_key_var.get()
        if llm_provider and api_key: # Only save if provider and key are present
            save_api_key(llm_provider, api_key)
            self._log_message(f"{llm_provider}의 API 키가 저장되었습니다.")
        elif llm_provider and not api_key:
             self._log_message(f"{llm_provider}의 API 키가 비어있어 저장하지 않았습니다.")

    def _on_api_key_focus_out(self, event=None):
        self._save_current_api_key() # Save the key first
        self._perform_service_update() # Then update the service

    def _perform_service_update(self):
        llm_provider = self.llm_var.get()
        api_key = self.api_key_var.get()

        if not llm_provider:
            self._update_model_selection_ui([], "LLM 공급자를 선택하세요.")
            self.translate_button.config(state=tk.DISABLED)
            self.translator = None
            return

        if not api_key:
            self._update_model_selection_ui([], f"{llm_provider} API 키를 입력하세요.")
            self.translator = None
            self.translate_button.config(state=tk.DISABLED)
            return

        self._log_message(f"Attempting to initialize {llm_provider} service...")
        try:
            self.translator = Translator(llm_provider_name=llm_provider, api_key=api_key)
            if self.translator.llm_service is None:
                self._update_model_selection_ui([], f"{llm_provider} 서비스 초기화 실패. API 키 또는 설정을 확인하세요.")
                self.translate_button.config(state=tk.DISABLED)
                return
            
            self._log_message(f"Fetching models for {llm_provider}...")
            models = self.translator.get_available_models()
            if models:
                self._update_model_selection_ui(models)
                self._log_message(f"Available models for {llm_provider}: {models}")
                self.translate_button.config(state=tk.NORMAL if self.input_file_path else tk.DISABLED)
            else:
                self._update_model_selection_ui([], f"{llm_provider}에서 사용 가능한 모델을 찾을 수 없습니다. API 키, 네트워크 또는 서비스 상태를 확인하세요.")
                self.translate_button.config(state=tk.DISABLED)

        except ConnectionError as e: # Raised by LLM services if API key config fails
            self._log_message(f"오류: {llm_provider} 서비스 연결 실패 - {e}")
            self._update_model_selection_ui([], f"{llm_provider} 연결 오류: {e}")
            self.translator = None
            self.translate_button.config(state=tk.DISABLED)
        except ValueError as e: 
            self._log_message(f"오류: {e}")
            self._update_model_selection_ui([], str(e))
            self.translator = None
            self.translate_button.config(state=tk.DISABLED)
        except Exception as e: 
            self._log_message(f"LLM 서비스 업데이트 중 예상치 못한 오류: {e}")
            self._update_model_selection_ui([], "LLM 서비스 업데이트 중 오류 발생.")
            self.translator = None
            self.translate_button.config(state=tk.DISABLED)

    def _update_model_selection_ui(self, models, status_message=None):
        # 기존 모델 라디오 버튼들 제거
        for widget in self.model_frame.winfo_children():
            widget.destroy()
        
        self.model_var.set("") # 이전 선택 초기화

        if models:
            self.model_status_label = None # 상태 레이블 제거
            for model_name in models:
                rb = ttk.Radiobutton(self.model_frame, text=model_name, variable=self.model_var, value=model_name)
                rb.pack(anchor=tk.W, padx=5, pady=2)
            if models: # 모델이 있으면 첫번째 모델을 기본 선택
                self.model_var.set(models[0])
        elif status_message:
            self.model_status_label = ttk.Label(self.model_frame, text=status_message)
            self.model_status_label.pack(anchor=tk.W, padx=5, pady=5)
        else: # models도 없고 status_message도 없는 경우 (일반적으로 발생하지 않음)
            self.model_status_label = ttk.Label(self.model_frame, text="모델 정보를 로드할 수 없습니다.")
            self.model_status_label.pack(anchor=tk.W, padx=5, pady=5)

    def open_file_dialog(self):
        file_path = filedialog.askopenfilename(
            title="번역할 파일 선택",
            filetypes=(("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")) # JSON 추가
        )
        if file_path:
            self.input_file_path = file_path
            self.selected_file_label.config(text=f"선택된 파일: {file_path}")
            self._log_message(f"입력 파일 선택됨: {file_path}")
            # 파일이 선택되면 번역 버튼 활성화 (LLM 서비스가 준비되었다면)
            if self.translator and self.translator.llm_service:
                self.translate_button.config(state=tk.NORMAL)

    def start_translation(self):
        if not self.translator or not self.translator.llm_service:
            messagebox.showerror("오류", "LLM 서비스가 초기화되지 않았습니다. LLM 종류와 API 키를 확인하세요.")
            return
            
        llm_provider = self.llm_var.get()
        api_key = self.api_key_var.get() # api_key_entry.get() 대신 변수 사용
        selected_model = self.model_var.get()
        output_language = self.output_lang_var.get()

        if not self.input_file_path:
            messagebox.showerror("오류", "먼저 번역할 파일을 선택해주세요.")
            return

        # API 키와 모델 선택은 _perform_service_update에서 주로 처리되므로 여기서는 상태 확인
        if not api_key:
            messagebox.showerror("오류", "API 키를 입력해주세요.")
            return
        
        if not selected_model:
            messagebox.showerror("오류", "번역 모델을 선택해주세요.")
            return

        self._log_message(f"번역 시작: LLM={llm_provider}, 모델={selected_model}, 출력언어={output_language}")
        self._log_message(f"입력 파일: {self.input_file_path}")
        self.translate_button.config(state=tk.DISABLED) # 번역 중 버튼 비활성화
        self.export_button.config(state=tk.DISABLED)
        self.translated_content_for_export = None

        # 백그라운드 스레드에서 번역 실행 (GUI 블로킹 방지) - threading 모듈 필요
        import threading
        thread = threading.Thread(target=self._execute_translation, 
                                 args=(self.input_file_path, output_language, selected_model))
        thread.start()

    def _execute_translation(self, input_file, output_lang, model):
        try:
            # self.translator는 이미 _perform_service_update에서 설정됨
            translated_content = self.translator.translate_file(
                input_file, 
                output_lang, 
                model, 
                self._log_message # 콜백 함수 전달
            )
            self.translated_content_for_export = translated_content
            # GUI 업데이트는 master.after를 통해 메인 스레드에서 처리
            self.master.after(0, self._on_translation_complete, translated_content)

        except Exception as e:
            error_message = f"번역 중 심각한 오류 발생: {e}"
            self._log_message(error_message)
            self.master.after(0, self._on_translation_failed)

    def _on_translation_complete(self, translated_content):
        if "Error:" in translated_content or "[CHUNK_ERROR:" in translated_content or "[CHUNK_EXCEPTION:" in translated_content:
            self._log_message("번역 중 일부 오류가 발생했습니다. 로그를 확인하세요.")
            # 부분 성공 시에도 내보내기 허용 여부 결정
        else:
            self._log_message("번역이 성공적으로 완료되었습니다.")
        
        # 결과 텍스트 영역에 최종 결과 표시 (선택적, 로그에 이미 표시됨)
        # self.result_text.config(state=tk.NORMAL)
        # self.result_text.delete('1.0', tk.END)
        # self.result_text.insert(tk.END, translated_content if translated_content else "번역 결과 없음")
        # self.result_text.config(state=tk.DISABLED)
        
        self.translate_button.config(state=tk.NORMAL) # 번역 버튼 다시 활성화
        if self.translated_content_for_export is not None: # None이 아닐때만 (오류만 있었던게 아니라면)
             self.export_button.config(state=tk.NORMAL) # 내보내기 버튼 활성화

    def _on_translation_failed(self):
        messagebox.showerror("번역 실패", "번역 과정 중 오류가 발생했습니다. 로그를 확인해주세요.")
        self.translate_button.config(state=tk.NORMAL)
        self.export_button.config(state=tk.DISABLED)

    def export_file_dialog(self):
        if self.translated_content_for_export is None: # None이면 아직 번역 안됐거나 실패
            messagebox.showwarning("경고", "내보낼 번역된 내용이 없습니다. 먼저 번역을 실행하세요.")
            return

        file_path = filedialog.asksaveasfilename(
            title="번역 파일 저장",
            defaultextension=".txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if file_path:
            try:
                # utils.file_handler.write_file 사용
                from utils.file_handler import write_file
                if write_file(file_path, self.translated_content_for_export):
                    self._log_message(f"번역된 파일 저장됨: {file_path}")
                    messagebox.showinfo("성공", f"번역된 파일이 '{file_path}'에 저장되었습니다.")
                else:
                    self._log_message(f"파일 저장 실패: {file_path}")
                    messagebox.showerror("오류", f"파일 저장 중 오류가 발생했습니다.")
            except Exception as e:
                self._log_message(f"파일 저장 오류: {e}")
                messagebox.showerror("오류", f"파일 저장 중 오류가 발생했습니다: {e}")

# # 아래 _dummy_translation_progress 와 after_id 는 실제 번역 로직으로 대체되어 제거
# # self.after_id = self.master.after(1000, self._dummy_translation_progress)

# # def _dummy_translation_progress(self):
# # ... (이하 더미 함수 내용 제거)


# if __name__ == '__main__':
#     # 이 파일 단독 실행시 테스트용 (main.py에서 실행하므로 주석 처리)
#     root = tk.Tk()
#     app = MainWindow(root)
#     root.mainloop() 