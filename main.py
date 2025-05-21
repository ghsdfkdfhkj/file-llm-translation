import tkinter as tk
from tkinterdnd2 import TkinterDnD
from gui.main_window import MainWindow

def main():
    root = TkinterDnD.Tk()
    app = MainWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main() 