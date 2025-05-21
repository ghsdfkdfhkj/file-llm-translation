import tkinter as tk
from tkinter import ttk, messagebox

class ModelSelectionDialog:
    def __init__(self, parent, models, current_model=None, all_models=None):
        self.top = tk.Toplevel(parent)
        self.top.title("모델 선택")
        self.top.geometry("400x400")  # 원래 크기로 복원
        self.top.resizable(False, False)
        
        # 모달 대화상자로 설정
        self.top.transient(parent)
        self.top.grab_set()
        
        # 중앙 정렬
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
        
        # 메인 프레임
        main_frame = ttk.Frame(self.top, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)
        
        # 상단 프레임 (설명 레이블과 체크박스)
        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        top_frame.columnconfigure(1, weight=1)  # 체크박스를 오른쪽으로 밀기 위해
        
        # 설명 레이블
        description = ttk.Label(top_frame, text="사용할 모델을 선택하세요:")
        description.grid(row=0, column=0, sticky=tk.W)
        
        # 모든 모델 보기 체크박스
        self.show_all_var = tk.BooleanVar(value=False)
        self.show_all_checkbox = ttk.Checkbutton(
            top_frame,
            text="모든 모델 보기",
            variable=self.show_all_var,
            command=self._toggle_model_view
        )
        self.show_all_checkbox.grid(row=0, column=1, sticky=tk.E)
        
        # 스크롤 가능한 프레임 생성
        self.canvas = tk.Canvas(main_frame, width=380, height=280)  # 높이 원래대로
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
        
        # 라디오 버튼 변수
        self.selected_model = tk.StringVar(value=current_model if current_model else "")
        
        # 라디오 버튼들을 저장할 리스트
        self.radio_buttons = []
        
        # 초기 라디오 버튼 생성
        self._create_radio_buttons()
        
        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=tk.E, pady=(20, 0), padx=(0, 20))
        
        # 취소/확인/적용 버튼
        ttk.Button(button_frame, text="취소", command=self._on_cancel).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text="확인", command=self._on_ok).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text="적용", command=self._on_apply).pack(side=tk.LEFT, padx=3)
        
        # 마우스 휠 스크롤 바인딩
        self._bind_mouse_wheel()
        
        # 대화상자가 닫힐 때 처리
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # 키보드 단축키
        self.top.bind('<Return>', lambda e: self._on_ok())
        self.top.bind('<Escape>', lambda e: self._on_cancel())

    def _create_radio_buttons(self):
        """라디오 버튼 생성"""
        # 기존 라디오 버튼 제거
        for rb in self.radio_buttons:
            rb.destroy()
        self.radio_buttons.clear()
        
        # 현재 표시할 모델 목록 선택
        models_to_show = self.all_models if self.show_all_var.get() else self.latest_models
        
        # 새 라디오 버튼 생성
        style = ttk.Style()
        style.configure('Model.TRadiobutton', padding=5)  # 라디오 버튼 간격 조정
        
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
        """마우스 휠 스크롤 이벤트 바인딩"""
        def _on_mousewheel(event):
            if self.canvas.winfo_exists():
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # 이전 바인딩 제거
        self.top.unbind_all("<MouseWheel>")
        # 새로운 바인딩 추가
        self.top.bind_all("<MouseWheel>", _on_mousewheel)

    def _unbind_mouse_wheel(self):
        """마우스 휠 스크롤 이벤트 바인딩 해제"""
        self.top.unbind_all("<MouseWheel>")

    def _on_apply(self):
        selected = self.selected_model.get()
        if not selected:
            messagebox.showwarning("경고", "모델을 선택해주세요.")
            return
        
        self.result = selected
        # 부모 창의 콜백 함수 호출
        if hasattr(self.parent, '_on_model_selected'):
            self.parent._on_model_selected(selected)
            # 대화상자는 닫지 않고 유지

    def _on_ok(self):
        selected = self.selected_model.get()
        if not selected:
            messagebox.showwarning("경고", "모델을 선택해주세요.")
            return
        
        self.result = selected
        self._unbind_mouse_wheel()
        self.top.destroy()

    def _on_cancel(self):
        self._unbind_mouse_wheel()
        self.result = None
        self.top.destroy()

    def show(self):
        # 부모 창의 입력을 비활성화하고 대화상자가 닫힐 때까지 대기
        self.top.wait_window()
        return self.result 