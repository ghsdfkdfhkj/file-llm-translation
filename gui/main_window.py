import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from translation_core.translator import Translator # Translator 임포트
from utils.config_manager import save_api_key, load_api_key # API 키 저장/로드를 위해 추가
from .model_selection_dialog import ModelSelectionDialog

class MainWindow:
    def __init__(self, master):
        self.master = master
        master.title("게임 번역 프로그램")
        master.geometry("1200x700")  # 더 넓은 초기 크기로 설정

        self.translator = None # Translator 인스턴스
        self.translated_content_for_export = None # 내보낼 컨텐츠
        self.current_model = None

        # Main frame
        main_frame = ttk.Frame(master, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)

        # 좌우 분할을 위한 프레임들
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))

        # === 왼쪽 프레임 내용 ===
        # LLM 선택
        llm_label = ttk.Label(left_frame, text="LLM 선택:")
        llm_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.llm_var = tk.StringVar()
        self.llm_combo_box = ttk.Combobox(left_frame, textvariable=self.llm_var, state="readonly")
        self.llm_combo_box['values'] = ("OpenAI", "Anthropic", "Google Gemini")
        self.llm_combo_box.current(0)
        self.llm_combo_box.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        self.llm_combo_box.bind("<<ComboboxSelected>>", self._on_llm_provider_changed)

        # API 키 입력
        api_key_label = ttk.Label(left_frame, text="API 키:")
        api_key_label.grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(left_frame, show="*", textvariable=self.api_key_var)
        self.api_key_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        self.api_key_entry.bind("<FocusOut>", self._on_api_key_focus_out)

        # 모델 선택 버튼
        self.model_button = ttk.Button(left_frame, text="모델 선택...", command=self._show_model_selection)
        self.model_button.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        self.model_button.config(state=tk.DISABLED)

        # 선택된 모델 표시 레이블
        self.selected_model_var = tk.StringVar(value="선택된 모델: 없음")
        selected_model_label = ttk.Label(left_frame, textvariable=self.selected_model_var)
        selected_model_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        # 파일 입력 프레임
        file_input_frame = ttk.Frame(left_frame)
        file_input_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        file_input_frame.columnconfigure(1, weight=1)

        self.file_input_button = ttk.Button(file_input_frame, text="번역할 파일 선택", command=self.open_file_dialog)
        self.file_input_button.grid(row=0, column=0, sticky=tk.W)
        self.selected_file_label = ttk.Label(file_input_frame, text="선택된 파일: 없음")
        self.selected_file_label.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.input_file_path = None

        # 번역 설정
        settings_frame = ttk.LabelFrame(left_frame, text="번역 설정", padding="5")
        settings_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        settings_frame.columnconfigure(1, weight=1)
        
        output_lang_label = ttk.Label(settings_frame, text="출력 언어:")
        output_lang_label.grid(row=0, column=0, sticky=tk.W)
        
        self.output_lang_var = tk.StringVar(value="한국어")
        self.output_lang_combo = ttk.Combobox(settings_frame, textvariable=self.output_lang_var, state="readonly")
        self.output_lang_combo['values'] = (
            "한국어",
            "영어 (English)",
            "일본어 (日本語)",
            "중국어 간체 (简体中文)",
            "중국어 번체 (繁體中文)",
            "프랑스어 (Français)",
            "독일어 (Deutsch)",
            "스페인어 (Español)",
            "러시아어 (Русский)",
            "베트남어 (Tiếng Việt)",
            "태국어 (ไทย)",
            "인도네시아어 (Bahasa Indonesia)"
        )
        self.output_lang_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # 언어 직접 입력을 위한 Entry 추가
        self.custom_lang_var = tk.StringVar()
        self.custom_lang_entry = ttk.Entry(settings_frame, textvariable=self.custom_lang_var)
        self.custom_lang_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=(5, 0))
        custom_lang_label = ttk.Label(settings_frame, text="직접 입력:")
        custom_lang_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))

        # 콤보박스 선택 이벤트 처리
        def on_lang_selected(event):
            if self.output_lang_combo.get() != "":
                self.custom_lang_var.set("")  # 콤보박스에서 선택하면 직접 입력 필드 초기화
        
        # 직접 입력 이벤트 처리
        def on_custom_lang_changed(*args):
            if self.custom_lang_var.get() != "":
                self.output_lang_var.set("")  # 직접 입력하면 콤보박스 선택 초기화
        
        self.output_lang_combo.bind('<<ComboboxSelected>>', on_lang_selected)
        self.custom_lang_var.trace_add('write', on_custom_lang_changed)

        # 번역 버튼과 내보내기 버튼을 위한 프레임
        button_frame = ttk.Frame(left_frame)
        button_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        # 번역 버튼
        self.translate_button = ttk.Button(button_frame, text="번역 시작", command=self.start_translation)
        self.translate_button.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.translate_button.config(state=tk.DISABLED)

        # 파일 내보내기 버튼
        self.export_button = ttk.Button(button_frame, text="번역 결과 내보내기", command=self.export_file_dialog, state=tk.DISABLED)
        self.export_button.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))

        # 로그 영역
        log_label = ttk.Label(left_frame, text="로그")
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

        # === 오른쪽 프레임 내용 ===
        # 번역 결과 영역
        result_label = ttk.Label(right_frame, text="번역 결과")
        result_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        
        result_frame = ttk.Frame(right_frame)
        result_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        
        self.result_text = tk.Text(result_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        result_scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_text.yview)
        result_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.result_text['yscrollcommand'] = result_scrollbar.set

        # 프레임 설정
        main_frame.columnconfigure(0, weight=0)  # 왼쪽은 고정 크기
        main_frame.columnconfigure(1, weight=1)  # 오른쪽이 확장됨
        main_frame.rowconfigure(0, weight=1)
        
        left_frame.columnconfigure(1, weight=1)
        left_frame.rowconfigure(8, weight=1)  # 로그 영역이 확장됨
        
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)  # 결과 영역이 확장됨

        self._on_llm_provider_changed() # Initial call to load saved key for default provider and update service

    def _show_model_selection(self):
        if not self.translator or not self.translator.llm_service:
            messagebox.showerror("오류", "LLM 서비스가 초기화되지 않았습니다.")
            return

        # 최신 모델과 모든 모델 목록 가져오기
        latest_models = self.translator.get_available_models()
        all_models = self.translator.get_all_models()  # 새로운 메서드 호출
        
        if not latest_models:
            messagebox.showerror("오류", "사용 가능한 모델이 없습니다.")
            return

        # 모델 선택 대화상자 생성 및 표시
        model_dialog = ModelSelectionDialog(
            self.master,
            latest_models,
            self.current_model,
            all_models
        )

        # 대화상자가 닫힐 때 처리
        def on_dialog_closed():
            selected_model = model_dialog.result
            if selected_model:
                self.current_model = selected_model
                self.selected_model_var.set(f"선택된 모델: {selected_model}")
                self._update_translate_button_state()
                self._log_message(f"모델이 선택되었습니다: {selected_model}")
            
        # 적용 버튼 콜백 설정
        model_dialog.top.protocol("WM_DELETE_WINDOW", lambda: [model_dialog._on_cancel(), on_dialog_closed()])
        model_dialog.top.bind('<Escape>', lambda e: [model_dialog._on_cancel(), on_dialog_closed()])
        
        # 대화상자에 콜백 함수 설정
        model_dialog.parent = self  # 부모 창 참조 설정
        
        # 대화상자 표시
        result = model_dialog.show()
        if result:  # 확인 버튼으로 닫힌 경우에만 처리
            on_dialog_closed()

    def _on_model_selected(self, selected_model):
        """모델 선택 대화상자에서 '적용' 버튼을 눌렀을 때 호출되는 콜백"""
        self.current_model = selected_model
        self.selected_model_var.set(f"선택된 모델: {selected_model}")
        self._update_translate_button_state()
        self._log_message(f"모델이 선택되었습니다: {selected_model}")

    def _update_translate_button_state(self):
        """번역 버튼의 활성화 상태를 업데이트"""
        if self.translator and self.translator.llm_service and self.input_file_path and self.current_model:
            self.translate_button.config(state=tk.NORMAL)
        else:
            self.translate_button.config(state=tk.DISABLED)

    def _log_message(self, message):
        """로그 메시지를 로그 영역에 추가"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _show_translation_result(self, result):
        """번역 결과를 결과 영역에 표시"""
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert(tk.END, result if result else "번역 결과 없음")
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
                return
            
            self.model_button.config(state=tk.NORMAL)
            self._update_translate_button_state()
            self._log_message(f"{llm_provider} 서비스가 초기화되었습니다.")

        except Exception as e:
            self._log_message(f"LLM 서비스 업데이트 중 예상치 못한 오류: {e}")
            self.model_button.config(state=tk.DISABLED)
            self.translator = None
            self.translate_button.config(state=tk.DISABLED)

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
        api_key = self.api_key_var.get()
        output_language = self.get_target_language()

        if not self.input_file_path:
            messagebox.showerror("오류", "먼저 번역할 파일을 선택해주세요.")
            return

        if not api_key:
            messagebox.showerror("오류", "API 키를 입력해주세요.")
            return
        
        if not self.current_model:
            messagebox.showerror("오류", "번역 모델을 선택해주세요.")
            return
        
        if not output_language:
            messagebox.showerror("오류", "출력 언어를 선택하거나 입력해주세요.")
            return

        self._log_message(f"번역 시작: LLM={llm_provider}, 모델={self.current_model}, 출력언어={output_language}")
        self._log_message(f"입력 파일: {self.input_file_path}")
        self.translate_button.config(state=tk.DISABLED) # 번역 중 버튼 비활성화
        self.export_button.config(state=tk.DISABLED)
        self.translated_content_for_export = None

        # 백그라운드 스레드에서 번역 실행 (GUI 블로킹 방지)
        import threading
        thread = threading.Thread(target=self._execute_translation, 
                                args=(self.input_file_path, output_language, self.current_model))
        thread.start()

    def _execute_translation(self, input_file, output_language, model):
        try:
            # self.translator는 이미 _perform_service_update에서 설정됨
            translated_content = self.translator.translate_file(
                input_file, 
                output_language, 
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
        else:
            self._log_message("번역이 성공적으로 완료되었습니다.")
        
        # 번역 결과 표시
        self._show_translation_result(translated_content)
        
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

    def get_target_language(self):
        """선택된 출력 언어를 반환합니다. 직접 입력이 있으면 직접 입력을 우선합니다."""
        custom_lang = self.custom_lang_var.get().strip()
        if custom_lang:
            return custom_lang
        selected_lang = self.output_lang_var.get().strip()
        if not selected_lang:
            return ""
        return selected_lang.split(' ')[0]  # 괄호 안의 원어 제거

# # 아래 _dummy_translation_progress 와 after_id 는 실제 번역 로직으로 대체되어 제거
# # self.after_id = self.master.after(1000, self._dummy_translation_progress)

# # def _dummy_translation_progress(self):
# # ... (이하 더미 함수 내용 제거)


# if __name__ == '__main__':
#     # 이 파일 단독 실행시 테스트용 (main.py에서 실행하므로 주석 처리)
#     root = tk.Tk()
#     app = MainWindow(root)
#     root.mainloop() 