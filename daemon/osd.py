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
    height = 165
    root.geometry(f"{width}x{height}+{x - width//2}+{y - height//2 - 50}")
    
    # Appearance
    root.configure(bg="#1e1e1e")
    
    # Add a border
    frame = tk.Frame(root, bg="#1e1e1e", highlightbackground="#3b82f6", highlightthickness=2)
    frame.pack(expand=True, fill="both", padx=2, pady=2)
    
    title = tk.Label(frame, text="🎙️ Recording...", font=("sans-serif", 12, "bold"), fg="#10b981", bg="#1e1e1e")
    title.pack(pady=(8, 4))
    
    info = tk.Label(frame, text="[E] : 🇬🇧 Translate to English\n[Z] : 🇨🇳 Translate to Chinese\n[ESC] : ❌ Cancel", font=("sans-serif", 10), fg="#d1d5db", bg="#1e1e1e", justify="left")
    info.pack()

    hint = tk.Label(frame, text="⏳ Auto closes in 2s (default: speech-to-text)", font=("sans-serif", 9, "italic"), fg="#9ca3af", bg="#1e1e1e")
    hint.pack(pady=(4, 4))

    # Auto close after 2.1s as safety fallback
    root.after(2100, root.destroy)
    root.mainloop()

if __name__ == "__main__":
    main()
