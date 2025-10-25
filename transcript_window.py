import tkinter as tk
from tkinter import scrolledtext, font
import queue
import threading

class TranscriptWindow:
    def __init__(self, ai_callback=None):
        self.root = tk.Tk()
        self.root.title("🎤 Live Transcription")
        self.root.geometry("900x900")
        # Slight transparency for glassmorphism effect
        try:
            # Overall window alpha (0.0 - fully transparent, 1.0 - opaque)
            self.root.attributes('-alpha', 0.95)
        except Exception:
            pass
        self.ai_callback = ai_callback  # Callback for AI processing
        
        # Make window always on top
        self.root.attributes('-topmost', True)

        # Configure pastel/glass colors
        # Soft, desaturated palette to emulate glassmorphism
        self.bg_color = "#f3f7fb"         # very light blue/gray
        self.text_color = "#22303a"       # dark slate for text
        self.accent_color = "#7be4c7"     # pastel mint accent
        self.status_bg = "#ffffff"        # light frosted panel color

        # Set window background
        self.root.configure(bg=self.bg_color)

        # Create header frame
        header_frame = tk.Frame(self.root, bg=self.status_bg, bd=0, relief=tk.FLAT)
        header_frame.pack(fill=tk.X, padx=0, pady=0)

        # Title label
        title_label = tk.Label(
            header_frame,
            text="🎤 Live Transcription",
            font=("Arial", 16, "bold"),
            bg=self.status_bg,
            fg=self.accent_color,
            pady=10
        )
        title_label.pack()

        # Status frame
        status_frame = tk.Frame(self.root, bg=self.status_bg, bd=0, relief=tk.FLAT)
        status_frame.pack(fill=tk.X, padx=0, pady=0)

        # Status label
        self.status_label = tk.Label(
            status_frame,
            text="⏸️ Status: Waiting for audio...",
            font=("Arial", 11),
            bg=self.status_bg,
            fg=self.accent_color,
            anchor="w",
            padx=15,
            pady=8
        )
        self.status_label.pack(fill=tk.X)

        # Latency label
        self.latency_label = tk.Label(
            status_frame,
            text="⚡ Latency: --",
            font=("Arial", 10),
            bg=self.status_bg,
            fg="#f59eaa",  # soft coral for contrast
            anchor="w",
            padx=15,
            pady=5
        )
        self.latency_label.pack(fill=tk.X)

        # Create button frame - AT THE TOP
        button_frame = tk.Frame(self.root, bg=self.status_bg, height=60)
        button_frame.pack(fill=tk.X, padx=0, pady=0)
        button_frame.pack_propagate(False)

        # AI Process button (arrow) - BIG AND PROMINENT AT TOP
        ai_btn = tk.Button(
            button_frame,
            text="➤ ASK AI",
            command=self.process_with_ai,
            font=("Arial", 14, "bold"),
            bg="#9beccf",   # pastel mint
            fg=self.text_color,
            activebackground="#7be4c7",
            activeforeground=self.text_color,
            padx=50,
            pady=15,
            borderwidth=0,
            cursor="hand2",
            relief=tk.RAISED
        )
        ai_btn.pack(side=tk.LEFT, padx=15, pady=10)

        # Clear All button
        clear_btn = tk.Button(
            button_frame,
            text="🗑️ Clear All",
            command=self.clear_all,
            font=("Arial", 10, "bold"),
            bg="#ffd6db",   # pastel coral
            fg=self.text_color,
            activebackground="#f7a8b3",
            activeforeground=self.text_color,
            padx=20,
            pady=12,
            borderwidth=0,
            cursor="hand2",
            relief=tk.RAISED
        )
        clear_btn.pack(side=tk.LEFT, padx=5, pady=10)

        # Save button
        save_btn = tk.Button(
            button_frame,
            text="💾 Save",
            command=self.save_transcript,
            font=("Arial", 10, "bold"),
            bg="#c6d8ff",   # pastel periwinkle
            fg=self.text_color,
            activebackground="#a7c0ff",
            activeforeground=self.text_color,
            padx=20,
            pady=12,
            borderwidth=0,
            cursor="hand2",
            relief=tk.RAISED
        )
        save_btn.pack(side=tk.LEFT, padx=5, pady=10)

        # Create main conversation frame (single area for everything)
        conversation_frame = tk.Frame(self.root, bg=self.bg_color)
        conversation_frame.pack(padx=15, pady=(10, 15), fill=tk.BOTH, expand=True)

        # Label for conversation section
        conversation_label = tk.Label(
            conversation_frame,
            text="� Conversation",
            font=("Arial", 11, "bold"),
            bg=self.bg_color,
            fg=self.accent_color,
            anchor="w"
        )
        conversation_label.pack(fill=tk.X, pady=(0, 5))

        # Create single conversation text widget (messenger style)
        self.conversation_area = scrolledtext.ScrolledText(
            conversation_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 12),
            bg="#f8fbff",
            fg=self.text_color,
            insertbackground=self.text_color,
            borderwidth=0,
            relief=tk.FLAT,
            padx=15,
            pady=15,
            spacing3=8
        )
        self.conversation_area.pack(fill=tk.BOTH, expand=True)

        # Make text read-only
        self.conversation_area.config(state=tk.DISABLED)

        # Configure text tags for messenger-style formatting
        self.conversation_area.tag_config("transcript_tag", foreground="#6b7b88", font=("Segoe UI", 11, "bold"))
        self.conversation_area.tag_config("transcript_text", foreground=self.text_color, font=("Segoe UI", 11))
        self.conversation_area.tag_config("human_tag", foreground="#5fb8a6", font=("Segoe UI", 11, "bold"))
        self.conversation_area.tag_config("human_text", foreground=self.text_color, font=("Segoe UI", 10))
        self.conversation_area.tag_config("ai_tag", foreground="#6f9fe6", font=("Segoe UI", 11, "bold"))
        self.conversation_area.tag_config("ai_text", foreground="#3b5566", font=("Segoe UI", 10))

        # Markdown formatting tags
        self.conversation_area.tag_config("md_header", foreground="#6f9fe6", font=("Segoe UI", 12, "bold"))
        self.conversation_area.tag_config("md_bold", foreground=self.text_color, font=("Segoe UI", 10, "bold"))
        self.conversation_area.tag_config("md_code", foreground="#8a6b9b", font=("Courier New", 9), background="#f2edf7")
        self.conversation_area.tag_config("md_bullet", foreground="#7be4c7", font=("Segoe UI", 10))
        self.conversation_area.tag_config("md_numbered", foreground="#7be4c7", font=("Segoe UI", 10))
        self.conversation_area.tag_config("md_quote", foreground="#9ab8d8", font=("Segoe UI", 10, "italic"), lmargin1=20)
        
        # Queue for thread-safe updates
        self.update_queue = queue.Queue()
        
        # Track conversation history
        self.conversation_history = []
        
        # Temporary buffer for accumulating transcript before sending to AI
        self.current_transcript = ""
        
        # Track if window is running
        self.is_running = True
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start checking for updates
        self.check_updates()
    
    def on_closing(self):
        """Handle window close event"""
        self.is_running = False
        self.root.destroy()
    
    def check_updates(self):
        """Check queue for updates and apply them (runs in GUI thread)"""
        if not self.is_running:
            return
        
        try:
            while True:
                update_type, data = self.update_queue.get_nowait()
                
                if update_type == "append":
                    # Append to temporary accumulation buffer and show preview
                    self.current_transcript += data + " "
                    self._rebuild_conversation()
                
                elif update_type == "status":
                    # Update status
                    self.status_label.config(text=f"🎙️ {data}")
                
                elif update_type == "latency":
                    # Update latency
                    self.latency_label.config(text=f"⚡ Latency: {data}")
                
                elif update_type == "clear":
                    # Clear the temporary transcript buffer
                    self.current_transcript = ""
                    self._rebuild_conversation()
                
                elif update_type == "ai_message":
                    # Add message to conversation area
                    role, message = data
                    self.conversation_history.append((role, message))
                    self._rebuild_conversation()
                
                elif update_type == "ai_response":
                    # Append to conversation history
                    role, message = data
                    self.conversation_history.append((role, message))
                    self._rebuild_conversation()
                
                elif update_type == "clear_conversation":
                    # Clear conversation history
                    self.conversation_history.clear()
                    self._rebuild_conversation()
        
        except queue.Empty:
            pass
        
        # Schedule next check
        if self.is_running:
            self.root.after(50, self.check_updates)
    
    def append_text(self, text):
        """Add text to window (thread-safe)"""
        self.update_queue.put(("append", text))
    
    def update_status(self, status):
        """Update status label (thread-safe)"""
        self.update_queue.put(("status", status))
    
    def update_latency(self, latency_text):
        """Update latency label (thread-safe)"""
        self.update_queue.put(("latency", latency_text))
    
    def clear_all(self):
        """Clear entire conversation and current transcript (thread-safe)"""
        self.conversation_history.clear()
        self.current_transcript = ""
        self._rebuild_conversation()
        self.update_status("Cleared - Waiting for audio...")
        self.update_latency("--")
    
    def _render_markdown(self, text):
        """Simple markdown rendering using text tags"""
        import re
        
        lines = text.split('\n')
        for line_num, line in enumerate(lines):
            if line_num > 0:
                self.conversation_area.insert(tk.END, "\n")
            
            # Headers (### Header)
            if re.match(r'^###\s+(.+)$', line):
                header_text = re.sub(r'^###\s+', '', line)
                self.conversation_area.insert(tk.END, header_text, "md_header")
            # Bullet lists (- item or * item)
            elif re.match(r'^[\*\-]\s+(.+)$', line):
                item_text = re.sub(r'^[\*\-]\s+', '• ', line)
                self.conversation_area.insert(tk.END, item_text, "md_bullet")
            # Numbered lists (1. item)
            elif re.match(r'^\d+\.\s+(.+)$', line):
                self.conversation_area.insert(tk.END, line, "md_numbered")
            # Blockquote (> text)
            elif line.startswith('> '):
                quote_text = line[2:]
                self.conversation_area.insert(tk.END, "  " + quote_text, "md_quote")
            # Regular text with inline formatting
            else:
                self._render_inline_markdown(line)
    
    def _render_inline_markdown(self, text):
        """Render inline markdown (bold, code, etc)"""
        import re
        
        # Split by **bold**, `code`
        pattern = r'(\*\*[^*]+\*\*|`[^`]+`)'
        parts = re.split(pattern, text)
        
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                # Bold text
                self.conversation_area.insert(tk.END, part[2:-2], "md_bold")
            elif part.startswith('`') and part.endswith('`'):
                # Code text
                self.conversation_area.insert(tk.END, part[1:-1], "md_code")
            else:
                # Regular text
                self.conversation_area.insert(tk.END, part, "ai_text")
    
    def _rebuild_conversation(self):
        """Rebuild the conversation view (Human/AI + visible accumulating text)"""
        # Save current scroll position
        scroll_position = self.conversation_area.yview()
        
        self.conversation_area.config(state=tk.NORMAL)
        self.conversation_area.delete(1.0, tk.END)
        
        for i, (role, message) in enumerate(self.conversation_history):
            if i > 0:
                self.conversation_area.insert(tk.END, "\n\n")
            
            # Format based on role
            if role == "Human":
                self.conversation_area.insert(tk.END, "Human:\n", "human_tag")
                self.conversation_area.insert(tk.END, message, "human_text")
            else:  # AI - render as markdown
                self.conversation_area.insert(tk.END, "AI:\n", "ai_tag")
                self._render_markdown(message)
        
        # Show current accumulating text (VISIBLE, ready to send)
        if self.current_transcript.strip():
            if len(self.conversation_history) > 0:
                self.conversation_area.insert(tk.END, "\n\n")
            # Show as regular text (will become Human: when Ask AI is clicked)
            self.conversation_area.insert(tk.END, self.current_transcript.strip(), "transcript_text")
        
        self.conversation_area.config(state=tk.DISABLED)
        
        # Restore scroll position - keep user's view where they left it
        self.conversation_area.yview_moveto(scroll_position[0])
    
    def get_transcript_text(self):
        """Get current accumulated transcript text"""
        return self.current_transcript.strip()
    
    def add_conversation_message(self, role, message):
        """Add a message to the conversation area (thread-safe)"""
        self.update_queue.put(("ai_message", (role, message)))
    
    def clear_conversation(self):
        """Clear conversation history (thread-safe)"""
        self.update_queue.put(("clear_conversation", None))
    
    def process_with_ai(self):
        """Process transcript with AI (called by button click)"""
        transcript = self.get_transcript_text()
        
        if not transcript:
            self.add_conversation_message("AI", "⚠️ No transcription available to process!")
            return
        
        # Add human message to conversation
        self.add_conversation_message("Human", transcript)
        
        # Auto-clear the accumulation buffer immediately
        self.current_transcript = ""
        self._rebuild_conversation()
        
        # Show processing status
        self.update_status("Sending to AI...")
        
        # Call the callback if provided
        if self.ai_callback:
            # Run in separate thread to avoid blocking GUI
            threading.Thread(
                target=self.ai_callback,
                args=(transcript,),
                daemon=True
            ).start()
        else:
            self.add_conversation_message("AI", "⚠️ AI callback not configured!")
    
    def save_transcript(self):
        """Save entire conversation to file"""
        from tkinter import filedialog
        import datetime
        
        # Get all conversation text
        text_content = self.conversation_area.get(1.0, tk.END).strip()
        
        if not text_content:
            self.update_status("Nothing to save!")
            return
        
        # Default filename with timestamp
        default_name = f"transcript_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # Ask user for save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                self.update_status(f"Saved to {filename}")
            except Exception as e:
                self.update_status(f"Error saving: {e}")
    
    def run(self):
        """Start the GUI (call from main thread)"""
        self.root.mainloop()
    
    def start_in_thread(self):
        """Start GUI in a separate thread"""
        gui_thread = threading.Thread(target=self.run, daemon=False)
        gui_thread.start()
        return gui_thread
