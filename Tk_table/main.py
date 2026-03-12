# main.py
from controller import AppController
import tkinter as tk

if __name__ == "__main__":
    root = tk.Tk()
    app = AppController(root)
    root.mainloop()