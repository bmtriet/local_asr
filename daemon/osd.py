import tkinter as tk
import sys

def main():
    root = tk.Tk()
    root.overrideredirect(True) # Frameless
    root.attributes("-topmost", True)
    
    # Try to make it slightly transparent if supported
    try:
        root.attributes("-alpha", 0.95)
    except:
        pass
    
    # Calculate position based on mouse pointer to ensure it shows on the active monitor
    x = root.winfo_pointerx()
    y = root.winfo_pointery()
    
    width = 300
    height = 145
    root.geometry(f"{width}x{height}+{x - width//2}+{y - height//2 - 50}")
    
    # Appearance
    root.configure(bg="#1e1e1e")
    
    # Add a border
    frame = tk.Frame(root, bg="#1e1e1e", highlightbackground="#3b82f6", highlightthickness=2)
    frame.pack(expand=True, fill="both", padx=2, pady=2)
    
    title = tk.Label(frame, text="🎙️ Chế độ Dịch thuật", font=("sans-serif", 12, "bold"), fg="#ffffff", bg="#1e1e1e")
    title.pack(pady=(10, 5))
    
    info = tk.Label(frame, text="[E] : 🇬🇧 Tiếng Anh\n[Z] : 🇨🇳 Tiếng Trung (Phồn thể)\n[Phím khác] : 🇻🇳 Mặc định\n[ESC] : ❌ Hủy bỏ", font=("sans-serif", 11), fg="#d1d5db", bg="#1e1e1e", justify="left")
    info.pack()

    # The script will run infinitely until killed by parent process.
    root.mainloop()

if __name__ == "__main__":
    main()
