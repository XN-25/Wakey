import os
import subprocess
import speech_recognition as sr
import pyautogui
import tkinter as tk
from tkinter import ttk 
import threading
import time
import tempfile
from datetime import datetime
import re 
from dotenv import load_dotenv

# --- EDR ADDITION: Hugging Face Import ---
from huggingface_hub import InferenceClient

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
from gtts import gTTS

from pywinauto import Desktop
from google import genai
from google.genai import types

# ==========================================
# 1. CONFIGURATION & ENVIRONMENT
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
SESSION_LOG_FILE = os.path.join(SCRIPT_DIR, f"wakey_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
AUDIT_LOG_FILE = os.path.join(SCRIPT_DIR, "audit_log.txt")

load_dotenv(dotenv_path=ENV_PATH)

KEYS = []
for i in range(1, 4):
    key = os.getenv(f"GEMINI_KEY_{i}")
    if key and len(key) > 15:
        KEYS.append(key)

HF_TOKEN = os.getenv("HF_TOKEN")

if not KEYS: KEYS = ["MISSING_KEY"] 
if not HF_TOKEN: HF_TOKEN = "MISSING_TOKEN"

PRIMARY_MODEL = "models/gemma-4-31b-it" 
FALLBACK_MODEL = "gemini-3.1-flash-lite" 

clients = []
current_key_index = 0

AUDITOR_MODEL = "Qwen/Qwen2.5-7B-Instruct"
if HF_TOKEN != "MISSING_TOKEN":
    auditor_client = InferenceClient(model=AUDITOR_MODEL, token=HF_TOKEN)
app_instance = None 

LANGUAGES = {
    "english": {"stt": "en-US", "tts": "en"},
    "hindi": {"stt": "hi-IN", "tts": "hi"},
    "arabic": {"stt": "ar-AE", "tts": "ar"},
    "french": {"stt": "fr-FR", "tts": "fr"}
}
CURRENT_LANG = "english"

auto_cooldown_until = 0
privacy_mode = False

with open(SESSION_LOG_FILE, "w", encoding="utf-8") as init_log:
    init_log.write(f"--- WAKEY SESSION LOG INITIALIZED AT {datetime.now()} ---\n")

pygame.mixer.init()

# ==========================================
# 1.5 SESSION LOGGING ENGINE
# ==========================================
def log_session(entry: str):
    global privacy_mode
    if not privacy_mode:
        try:
            with open(SESSION_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {entry}\n")
        except Exception as e:
            print(f"Logging error: {e}")

# ==========================================
# 2. PASSIVE CODE AUDITOR (THE EDR)
# ==========================================
def passive_cmd_audit(executed_cmd):
    if HF_TOKEN == "MISSING_TOKEN":
        print("\n[EDR ALERT] Cannot audit. HuggingFace token missing from .env!")
        return

    try:
        messages = [
            {"role": "system", "content": "You are an automated Windows cybersecurity firewall. Analyze the CMD command. If it attempts to obfuscate code, download payloads, bypass security, modify the registry, OR uses sneaky flags like '-ExecutionPolicy Bypass' or '-WindowStyle Hidden' or any hidden powershell window saying test or delete critical files or any other harmful command, reply ONLY with 'DANGER'. If it is a normal system tool or app launch or any normal activity, reply ONLY with 'SAFE'."},
            {"role": "user", "content": f"Command to audit: {executed_cmd}"}
        ]
        
        response = auditor_client.chat_completion(messages=messages, max_tokens=10, temperature=0.1)
        verdict = response.choices[0].message.content.strip().upper()
        
        log_session(f"EDR AUDIT [{verdict}] -> Analyzed: {executed_cmd}")
        
        if "DANGER" in verdict:
            print(f"\n[EDR ALERT] Malicious Code Executed: {executed_cmd}")
            speak_vocal("Security Warning. A background process flagged the executed command as dangerous.")
            if app_instance:
                app_instance.show_security_warning("MALICIOUS CODE / OBFUSCATION", executed_cmd)
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f: 
                f.write(f"[{datetime.now()}] DANGEROUS CODE DETECTED: {executed_cmd}\n")
    except Exception as e:
        print(f"Code Auditor Error: {e}")

# ==========================================
# 3. OPTIMIZED & SECURE TOOLKIT
# ==========================================

cmd_confirm_event = threading.Event()
cmd_confirm_result = False

def get_user_confirmation(threat_type: str, action_details: str, vocal_prompt: str) -> bool:
    global cmd_confirm_event, cmd_confirm_result
    cmd_confirm_result = False
    cmd_confirm_event.clear()
    
    if app_instance:
        app_instance.show_interactive_warning(threat_type, action_details)
    
    speak_vocal(vocal_prompt)
    
    def voice_listener():
        global cmd_confirm_result, cmd_confirm_event
        try:
            r_temp = sr.Recognizer()
            with sr.Microphone() as source_temp:
                r_temp.adjust_for_ambient_noise(source_temp, duration=0.5)
                audio = r_temp.listen(source_temp, timeout=12, phrase_time_limit=3)
                text = r_temp.recognize_google(audio).lower()
                if "confirm" in text or "yes" in text or "do it" in text or "proceed" in text:
                    cmd_confirm_result = True
                    cmd_confirm_event.set()
                elif "deny" in text or "no" in text or "cancel" in text or "stop" in text:
                    cmd_confirm_result = False
                    cmd_confirm_event.set()
        except Exception:
            pass 
            
    threading.Thread(target=voice_listener, daemon=True).start()
    
    cmd_confirm_event.wait(timeout=15)
    
    if app_instance and hasattr(app_instance, 'interactive_warn_win'):
        try: app_instance.interactive_warn_win.destroy()
        except: pass
        
    return cmd_confirm_result


def run_system_cmd(command: str) -> str:
    global cmd_confirm_event, cmd_confirm_result
    
    BLACKLIST = ["format ", "diskpart"]
    RISKY_LIST = ["del ", "rd ", "rmdir ", "reg delete", "shutdown", "regedit"]
    
    command_lower = command.lower()
    
    if "taskkill" in command_lower:
        CRITICAL_APPS = ["explorer", "svchost", "csrss", "winlogon", "lsass", "system", "taskmgr"]
        if any(app in command_lower for app in CRITICAL_APPS):
            print(f"\n[SECURITY BLOCK] Prevented AI from killing critical process: {command}")
            return "SYSTEM ERROR: Cannot close critical Windows system processes."
            
    elif any(bad_word in command_lower for bad_word in BLACKLIST):
        print(f"\n[SECURITY BLOCK] Prevented AI from running absolutely blocked command: {command}")
        return "SYSTEM ERROR: Command absolutely blocked by security firewall."

    elif any(risky_word in command_lower for risky_word in RISKY_LIST):
        print(f"\n[SECURITY INTERCEPT] Risky command requires confirmation: {command}")
        
        confirmed = get_user_confirmation(
            "POTENTIALLY DESTRUCTIVE COMMAND", 
            command, 
            "This action modifies or deletes files. Please click confirm, or say confirm to proceed."
        )
        
        if not confirmed:
            print(f"\n[SECURITY BLOCK] User denied risky command: {command}")
            speak_vocal("Action cancelled.")
            return "SYSTEM ERROR: User denied the action."
        else:
            print(f"\n[SECURITY OVERRIDE] User confirmed risky command: {command}")
            speak_vocal("Action confirmed. Executing.")

    try:
        log_session(f"SYSTEM EXECUTION -> Command: {command}")
        subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        threading.Thread(target=passive_cmd_audit, args=(command,), daemon=True).start()
        return f"Executed: {command}"
    except Exception as e: return f"Error: {e}"

def set_system_brightness(level: int) -> str:
    try:
        level = max(0, min(100, int(level)))
        cmd = f"powershell (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
        subprocess.Popen(cmd, shell=True)
        log_session(f"SYSTEM OVERRIDE -> Brightness set to {level}%")
        return f"Brightness set to {level}%"
    except Exception as e: return f"Error: {e}"

def set_system_volume(level: int) -> str:
    try:
        level = max(0, min(100, int(level)))
        pyautogui.press('volumedown', presses=50, interval=0.01) 
        pyautogui.press('volumeup', presses=level // 2, interval=0.01) 
        log_session(f"SYSTEM OVERRIDE -> Volume set to {level}%")
        return f"Volume set to {level}%"
    except Exception as e: return f"Error: {e}"

# --- OFFLINE PYWINAUTO TOOLS (FOR LOCAL COMMANDS) ---
def _find_smart_window(window_name: str):
    desktop = Desktop(backend="uia")
    name_lower = window_name.lower().strip()
    if name_lower in ["current", "active", "this", "current window", "it", "here"]:
        windows = desktop.windows()
        if windows: return windows[0] 
    for win in desktop.windows():
        title = win.window_text()
        if title and name_lower in title.lower():
            return win
    return desktop.window(best_match=window_name)

def get_ui_object_tree(window_name: str) -> str:
    try:
        win = _find_smart_window(window_name)
        tree = f"Elements in '{win.window_text()}':\n"
        for child in win.descendants()[:50]: 
            if child.control_type() in ["Button", "MenuItem", "ListItem"] and child.window_text():
                tree += f"- {child.window_text()}\n"
        return tree
    except Exception as e: return f"Window not found: {e}"

def local_ui_interaction(window_name: str, action: str, target_name: str, text: str = None):
    target_lower = target_name.lower()
    if any(risky in target_lower for risky in ["delete", "submit", "pay", "checkout", "sign"]):
        print(f"\n[SECURITY INTERCEPT] Risky UI action requires confirmation: {target_name}")
        confirmed = get_user_confirmation(
            "CRITICAL UI ACTION PENDING",
            f"Action: {action.upper()} | Target: '{target_name}'",
            f"You are about to click {target_name}. Please confirm or cancel."
        )
        if not confirmed:
            print(f"\n[SECURITY BLOCK] User denied UI action: {target_name}")
            speak_vocal("Action cancelled.")
            return "SYSTEM ERROR: User denied the action."
        else:
            print(f"\n[SECURITY OVERRIDE] User confirmed UI action: {target_name}")
            speak_vocal("Action confirmed.")

    try:
        desktop = Desktop(backend="uia")
        name_lower = window_name.lower().strip()
        
        if name_lower in ["current", "active", "this", "current window", "it", "here"]:
            target_title = pyautogui.getActiveWindowTitle()
        else:
            target_title = window_name
            for win in desktop.windows():
                if win.window_text() and name_lower in win.window_text().lower():
                    target_title = win.window_text()
                    break
                    
        app_win = desktop.window(title=target_title)
        app_win.set_focus()
        target = app_win.child_window(best_match=target_name)
        
        if action == "click":
            try: target.invoke()
            except: target.click_input()
            log_session(f"LOCAL UI INTERACTION -> Clicked '{target_name}' in '{target_title}'")
            return f"Clicked {target_name}"
        elif action == "type":
            target.set_focus()
            pyautogui.write(text, interval=0.02)
            pyautogui.press('enter')
            log_session(f"LOCAL UI INTERACTION -> Typed into '{target_title}'")
            return "Done."
            
    except Exception as e: 
        return f"Failed: {e}"

# --- NEW: DEDICATED SCREEN ANALYZER TOOL (STABLE) ---
def analyze_screen_visually(query: str) -> str:
    """
    Takes a live screenshot to answer questions about the screen. Use this FIRST if you need to read a form or find what's visible.
    query: What you need to know (e.g., 'List all form fields', 'Read the text on screen').
    """
    try:
        screenshot = pyautogui.screenshot()
        client = clients[current_key_index]
        response = client.models.generate_content(
            model=FALLBACK_MODEL, 
            contents=[screenshot, f"Look at this screenshot and answer: {query}"]
        )
        log_session(f"VISION ANALYSIS -> Looked at screen for: '{query}'")
        return response.text
    except Exception as e: 
        return f"Vision Analysis Failed: {e}"

# --- CLOUD VISION UI INTERACTION ENGINE ---
def cloud_vision_ui_interaction(target_description: str, action: str, text: str = None) -> str:
    target_lower = target_description.lower()
    if any(risky in target_lower for risky in ["delete", "submit", "pay", "checkout", "sign"]):
        print(f"\n[SECURITY INTERCEPT] Risky UI action requires confirmation: {target_description}")
        confirmed = get_user_confirmation(
            "CRITICAL UI ACTION PENDING",
            f"Action: {action.upper()} | Target: '{target_description}'",
            f"You are about to interact with {target_description}. Please confirm or cancel."
        )
        if not confirmed:
            print(f"\n[SECURITY BLOCK] User denied Vision UI action: {target_description}")
            speak_vocal("Action cancelled.")
            return "SYSTEM ERROR: User denied the action."
        else:
            print(f"\n[SECURITY OVERRIDE] User confirmed Vision UI action: {target_description}")
            speak_vocal("Action confirmed.")

    try:
        screenshot = pyautogui.screenshot()
        width, height = screenshot.size
        
        client = clients[current_key_index]
        
        prompt = f"Find the UI element visually matching '{target_description}'. Output ONLY its bounding box in exactly this format: [ymin, xmin, ymax, xmax] where values are scaled from 0 to 1000."
        
        response = client.models.generate_content(
            model=FALLBACK_MODEL, 
            contents=[screenshot, prompt]
        )
        
        match = re.search(r'\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]', response.text)
        if match:
            ymin, xmin, ymax, xmax = map(int, match.groups())
            
            center_x = int(((xmin + xmax) / 2000) * width)
            center_y = int(((ymin + ymax) / 2000) * height)
            
            if action == "click":
                pyautogui.click(center_x, center_y)
                log_session(f"CLOUD VISION INTERACTION -> Clicked '{target_description}' at ({center_x}, {center_y})")
                return f"Successfully clicked {target_description}"
            elif action == "type":
                pyautogui.click(center_x, center_y)
                pyautogui.write(text, interval=0.02)
                pyautogui.press('enter')
                log_session(f"CLOUD VISION INTERACTION -> Typed '{text}' into '{target_description}'")
                return f"Successfully typed into {target_description}"
                
        return f"Failed to locate '{target_description}' visually. AI returned: {response.text}"
        
    except Exception as e: 
        return f"Vision Interaction Failed: {e}"

# ==========================================
# 4. UNBREAKABLE VOCAL ENGINE (THREADED)
# ==========================================
def speak_vocal(text):
    def _speak_thread():
        print(f"\nWakey: {text}")
        try:
            tts_lang = LANGUAGES[CURRENT_LANG]["tts"]
            tts = gTTS(text=text, lang=tts_lang)
            fd, temp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            tts.save(temp_path)
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
            try: os.remove(temp_path) 
            except: pass
        except Exception:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except: pass
    threading.Thread(target=_speak_thread, daemon=True).start()

# ==========================================
# 5. ENHANCED UI & HYBRID BRAIN
# ==========================================
class WakeyUI:
    def __init__(self):
        global app_instance
        app_instance = self 
        
        self.total_calls = 0
        self.successful_calls = 0
        self.chat_history = [] 

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True, "-transparentcolor", "#f0f0f0")
        self.root.config(bg="#f0f0f0")
        
        self.COLOR_WHITE = "#FFFFFF"   
        self.COLOR_BLUE  = "#007BFF"   
        self.COLOR_GREEN = "#28A745"   
        self.COLOR_RED   = "#DC3545"   

        self.canvas = tk.Canvas(self.root, width=600, height=125, bg="#f0f0f0", highlightthickness=0)
        self.canvas.pack()
        self.pill = self.canvas.create_polygon(0,0,0,0, fill=self.COLOR_WHITE, outline="#ddd", smooth=True)
        self.draw_pill()
        
        self.title_text = self.canvas.create_text(115, 35, text="WAKEY", font=("Segoe UI", 16, "bold"), fill="black")
        self.status_text = self.canvas.create_text(520, 35, text="READY", font=("Segoe UI", 10, "bold"), fill="#777")
        
        self.dashboard_text = self.canvas.create_text(300, 95, text="Model: Standby | Success Rate: N/A", font=("Segoe UI", 9, "bold"), fill="#555")

        self.privacy_var = tk.BooleanVar(value=False)
        self.privacy_cb = tk.Checkbutton(self.root, text="Privacy", variable=self.privacy_var, command=self.ui_change, bg=self.COLOR_WHITE, activebackground=self.COLOR_WHITE, bd=0, font=("Segoe UI", 8))
        self.privacy_cb.place(x=105, y=55)

        self.persona_var = tk.StringVar(value="Normal")
        self.persona_combo = ttk.Combobox(self.root, textvariable=self.persona_var, values=["Normal", "Vision", "Motor", "Cognitive"], state="readonly", width=9)
        self.persona_combo.place(x=185, y=55)
        self.persona_combo.bind("<<ComboboxSelected>>", self.ui_change)

        self.model_var = tk.StringVar(value="Auto")
        self.model_combo = ttk.Combobox(self.root, textvariable=self.model_var, values=["Auto", "Gemini 3.1", "Gemma 4", "Local"], state="readonly", width=11)
        self.model_combo.place(x=275, y=55)
        self.model_combo.bind("<<ComboboxSelected>>", self.ui_change)

        self.lang_var = tk.StringVar(value=CURRENT_LANG)
        self.lang_combo = ttk.Combobox(self.root, textvariable=self.lang_var, values=list(LANGUAGES.keys()), state="readonly", width=10)
        self.lang_combo.place(x=390, y=55)
        self.lang_combo.bind("<<ComboboxSelected>>", self.ui_lang_change)
        
        tk.Button(self.root, text="×", command=lambda: os._exit(0), font=("Arial", 18), bg="#eee", bd=0).place(x=25, y=18, width=40, height=40)
        
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"600x125+{(sw-600)//2}+40")
        
        threading.Thread(target=self.initialize_ai_and_run, daemon=True).start()
        self.root.mainloop()

    def draw_pill(self):
        x1, y1, x2, y2, r = 5, 5, 595, 120, 35
        p = [x1+r,y1, x1+r,y1, x2-r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y1+r, x2,y2-r, x2,y2-r, x2,y2, x2-r,y2, x2-r,y2, x1+r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y2-r, x1,y1+r, x1,y1+r, x1,y1]
        self.canvas.coords(self.pill, *p)

    def ui_change(self, event=None):
        global privacy_mode
        privacy_mode = self.privacy_var.get()
        self.update_view("SETTINGS UPDATED", self.COLOR_GREEN)
        self.root.after(1000, lambda: self.update_view("READY", self.COLOR_WHITE))

    def ui_lang_change(self, event=None):
        global CURRENT_LANG
        CURRENT_LANG = self.lang_var.get()
        self.update_view(f"LANG: {CURRENT_LANG.upper()}", self.COLOR_GREEN)
        self.root.after(1000, lambda: self.update_view("READY", self.COLOR_WHITE))

    def voice_lang_change(self, lang):
        global CURRENT_LANG
        CURRENT_LANG = lang
        self.lang_var.set(lang) 
        speak_vocal(f"Language set to {lang}")
        self.update_view(f"LANG: {CURRENT_LANG.upper()}", self.COLOR_GREEN)
        self.root.after(1000, lambda: self.update_view("READY", self.COLOR_WHITE))

    def update_view(self, status, color):
        def _u():
            self.canvas.itemconfig(self.status_text, text=status)
            self.canvas.itemconfig(self.pill, fill=color)
            if color == self.COLOR_WHITE:
                self.canvas.itemconfig(self.title_text, fill="black")
                self.canvas.itemconfig(self.status_text, fill="#777")
                self.canvas.itemconfig(self.dashboard_text, fill="#555")
                self.privacy_cb.config(bg=self.COLOR_WHITE, activebackground=self.COLOR_WHITE)
            else:
                self.canvas.itemconfig(self.title_text, fill="white")
                self.canvas.itemconfig(self.status_text, fill="white")
                self.canvas.itemconfig(self.dashboard_text, fill="white")
                self.privacy_cb.config(bg=color, activebackground=color)
        self.root.after(0, _u)

    def update_dashboard(self, current_model, success: bool):
        self.total_calls += 1
        if success: self.successful_calls += 1
        rate = int((self.successful_calls / self.total_calls) * 100)
        def _dash():
            self.canvas.itemconfig(self.dashboard_text, text=f"Model: {current_model} | Success Rate: {rate}%")
        self.root.after(0, _dash)

    def show_security_warning(self, threat_type, command):
        def _create_popup():
            warn_win = tk.Toplevel(self.root)
            warn_win.title("SECURITY ALERT")
            warn_win.geometry("400x180")
            warn_win.attributes("-topmost", True)
            warn_win.config(bg="white", highlightbackground=self.COLOR_RED, highlightthickness=4)
            tk.Label(warn_win, text="⚠️ EDR ALERT", font=("Segoe UI", 14, "bold"), fg=self.COLOR_RED, bg="white").pack(pady=10)
            tk.Label(warn_win, text=f"{threat_type}", font=("Segoe UI", 10, "bold"), bg="white").pack()
            cmd_box = tk.Text(warn_win, height=3, width=40, font=("Consolas", 9), bg="#f8f8f8")
            cmd_box.insert(tk.END, command)
            cmd_box.config(state="disabled")
            cmd_box.pack(pady=10)
            tk.Label(warn_win, text="Dismissing automatically in 30 seconds...", font=("Segoe UI", 8, "italic"), fg="#888", bg="white").pack(pady=2)
            warn_win.after(30000, warn_win.destroy)
        self.root.after(0, _create_popup)

    def show_interactive_warning(self, threat_type, command):
        def _create_popup():
            self.interactive_warn_win = tk.Toplevel(self.root)
            self.interactive_warn_win.title("ACTION REQUIRED")
            self.interactive_warn_win.geometry("450x220")
            self.interactive_warn_win.attributes("-topmost", True)
            self.interactive_warn_win.config(bg="white", highlightbackground="#FFA500", highlightthickness=4)
            
            tk.Label(self.interactive_warn_win, text="⚠️ RISKY ACTION PENDING", font=("Segoe UI", 14, "bold"), fg="#FF8C00", bg="white").pack(pady=10)
            tk.Label(self.interactive_warn_win, text=f"Type: {threat_type}", font=("Segoe UI", 10, "bold"), bg="white").pack()
            
            cmd_box = tk.Text(self.interactive_warn_win, height=3, width=45, font=("Consolas", 9), bg="#f8f8f8")
            cmd_box.insert(tk.END, command)
            cmd_box.config(state="disabled")
            cmd_box.pack(pady=10)
            
            def on_confirm():
                global cmd_confirm_result, cmd_confirm_event
                cmd_confirm_result = True
                cmd_confirm_event.set()
                
            def on_cancel():
                global cmd_confirm_result, cmd_confirm_event
                cmd_confirm_result = False
                cmd_confirm_event.set()

            btn_frame = tk.Frame(self.interactive_warn_win, bg="white")
            btn_frame.pack(pady=5)
            
            tk.Button(btn_frame, text="CONFIRM (or say 'confirm')", bg=self.COLOR_GREEN, fg="white", font=("Segoe UI", 9, "bold"), command=on_confirm).pack(side=tk.LEFT, padx=10)
            tk.Button(btn_frame, text="CANCEL (or say 'cancel')", bg=self.COLOR_RED, fg="white", font=("Segoe UI", 9, "bold"), command=on_cancel).pack(side=tk.RIGHT, padx=10)
            
        self.root.after(0, _create_popup)

    def initialize_ai_and_run(self):
        global clients
        try:
            if "MISSING_KEY" in KEYS:
                self.update_view(".ENV ERROR", self.COLOR_RED)
                speak_vocal("Environment file missing or invalid API keys.")
                return 
                
            clients = [genai.Client(api_key=key) for key in KEYS]
            self.run_brain()
        except Exception: self.update_view("API ERROR", self.COLOR_RED)

    def run_brain(self):
        r = sr.Recognizer()
        r.pause_threshold = 0.8
        
        with sr.Microphone() as source: 
            r.adjust_for_ambient_noise(source, duration=1.5)
        r.dynamic_energy_threshold = False
        
        while True:
            try:
                with sr.Microphone() as source:
                    self.update_view("READY", self.COLOR_WHITE)
                    audio = r.listen(source, timeout=None, phrase_time_limit=4)
                    
                    try:
                        text = r.recognize_google(audio, language="en-US").lower()
                    except sr.UnknownValueError:
                        continue 
                    
                    if "computer" in text:
                        self.update_view("LISTENING", self.COLOR_BLUE)
                        try:
                            cmd_audio = r.listen(source, timeout=6, phrase_time_limit=8)
                            stt_lang = LANGUAGES[CURRENT_LANG]["stt"]
                            command = r.recognize_google(cmd_audio, language=stt_lang).lower().strip()
                            
                            log_session(f"VOICE COMMAND -> '{command}'")
                            
                            if "language" in command and "set" in command:
                                for lang in LANGUAGES:
                                    if lang in command:
                                        self.voice_lang_change(lang)
                                        break
                                continue 
                            
                            if "mode privacy" in command or "privacy mode" in command:
                                self.privacy_var.set(True)
                                self.ui_change()
                                speak_vocal("Privacy mode activated.")
                                continue

                            if "mode normal" in command or "normal mode" in command:
                                self.privacy_var.set(False)
                                self.ui_change()
                                speak_vocal("Normal mode activated.")
                                continue

                            if "model local" in command or "local model" in command:
                                self.model_var.set("Local")
                                self.ui_change()
                                speak_vocal("Local execution engaged.")
                                continue

                            if "model normal" in command or "normal model" in command or "model auto" in command:
                                self.model_var.set("Auto")
                                self.ui_change()
                                speak_vocal("Cloud pipeline restored.")
                                continue

                            if "terminate" in command: 
                                speak_vocal("Shutting down.")
                                os._exit(0)

                            nums = re.findall(r'\d+', command)
                            if "brightness" in command and nums:
                                set_system_brightness(int(nums[0]))
                                speak_vocal(f"Brightness set to {nums[0]} percent")
                                continue
                            if "volume" in command and nums:
                                set_system_volume(int(nums[0]))
                                speak_vocal(f"Volume set to {nums[0]} percent")
                                continue
                                
                            if command in ["pause", "play media", "play"]:
                                pyautogui.press('playpause')
                                speak_vocal("Media controlled.")
                                continue
                                
                            if "time" in command and ("what" in command or "is" in command):
                                speak_vocal(f"It is {datetime.now().strftime('%I:%M %p')}")
                                continue
                            if command in ["show desktop", "minimize all"]:
                                pyautogui.hotkey('win', 'd')
                                speak_vocal("Desktop shown")
                                continue
                            if "screenshot" in command:
                                pyautogui.press('printscreen')
                                speak_vocal("Screenshot taken")
                                continue
                            if "close this app" in command or "close current app" in command:
                                pyautogui.hotkey('alt', 'f4')
                                speak_vocal("Application closed")
                                continue

                            if command.startswith("in this window click ") or command.startswith("in current window click ") or command.startswith("in the current window click "):
                                target_name = command.split("click ")[1].strip()
                                self.update_view("PROCESSING", self.COLOR_GREEN)
                                result = local_ui_interaction("current", "click", target_name)
                                
                                if result != "Done." and not result.startswith("Clicked"):
                                    print(f"Local click failed: {result}. Handing to AI.")
                                else:
                                    speak_vocal(f"Clicked {target_name}")
                                    continue

                            open_map = {
                                "calculator": "calc", "paint": "mspaint", "notepad": "notepad",
                                "google chrome": "chrome", "chrome": "chrome",
                                "microsoft edge": "msedge", "edge": "msedge",
                                "command prompt": "cmd", "word": "winword",
                                "microsoft word": "winword", "excel": "excel",
                                "file explorer": "explorer", "settings": "ms-settings:"
                            }
                            kill_map = {
                                "calculator": "CalculatorApp", "calc": "CalculatorApp",
                                "paint": "mspaint", "notepad": "notepad",
                                "google chrome": "chrome", "chrome": "chrome",
                                "microsoft edge": "msedge", "edge": "msedge",
                                "command prompt": "cmd", "word": "winword",
                                "microsoft word": "winword", "excel": "excel",
                                "settings": "SystemSettings"
                            }

                            if command.startswith("open ") or command.startswith("launch "):
                                app_name = command.replace("open ", "").replace("launch ", "").strip()
                                if app_name in open_map:
                                    target_exe = open_map[app_name]
                                    self.update_view("PROCESSING", self.COLOR_GREEN)
                                    run_system_cmd(f"start {target_exe}")
                                    speak_vocal(f"Opening {app_name}")
                                    continue 

                            if command.startswith("close ") or command.startswith("kill "):
                                app_name = command.replace("close ", "").replace("kill ", "").strip()
                                if app_name in kill_map:
                                    target_exe = kill_map[app_name]
                                    self.update_view("PROCESSING", self.COLOR_GREEN)
                                    run_system_cmd(f"taskkill /F /IM {target_exe}.exe") 
                                    speak_vocal(f"Closing {app_name}")
                                    continue 

                            self.update_view("PROCESSING", self.COLOR_GREEN)
                            self.call_ai(command)
                        except sr.UnknownValueError:
                            pass 
                        except Exception: 
                            pass
            except Exception: time.sleep(0.5)

    def call_ai(self, user_cmd):
        global current_key_index, auto_cooldown_until
        
        selected_mode = self.model_var.get()
        persona = self.persona_var.get()
        
        if selected_mode == "Local":
            speak_vocal("Local execution active. Cloud disabled.")
            self.update_dashboard("Local Only", True)
            self.update_view("READY", self.COLOR_WHITE)
            return

        persona_context = ""
        if persona == "Vision":
            persona_context = "CRITICAL PERSONA: The user has a severe vision impairment. Rely heavily on spoken descriptions. Clearly articulate what is on the screen instead of expecting them to read."
        elif persona == "Motor":
            persona_context = "CRITICAL PERSONA: The user has a motor impairment. Prioritize generating automation scripts, executing clicks, and typing for them. Minimize any physical keyboard/mouse requirements."
        elif persona == "Cognitive":
            persona_context = "CRITICAL PERSONA: The user has a cognitive or learning impairment. You MUST use extremely simple, clear, and direct language. Break complex tasks down into single, bite-sized steps. Avoid jargon and long paragraphs."
        else:
            persona_context = "Standard operational mode."

        try:
            client = clients[current_key_index]
            current_key_index = (current_key_index + 1) % len(KEYS)
            
            # --- FIX: ADDED SCREEN ANALYZER TOOL TO THE DIRECTIVES ---
            gen_config = types.GenerateContentConfig(
                system_instruction=f"""You are Wakey, an ai agent for windows. Respond in {CURRENT_LANG}. Rule: Max 10 words.
                {persona_context}
                - If the user asks you to interact with a form or something on the screen, FIRST use the `analyze_screen_visually` tool to look at the screen and see what fields/buttons exist.
                - Then, use the `cloud_vision_ui_interaction` tool to click/type by providing a clear visual description of the target.
                - Volume/Brightness: Use the necessary tools.
                - URLs: 'run_system_cmd' with 'start https://url'.
                -Do not complete any medical or legal related forms or docs.
                -If an user asks to breakdown something look at the screen analyze the content open notepad break it down into bullet points and marrk the important points then type in any deadlines seperately and excplicitly type the links seprately one below the other then open https://to-do.office.com/tasks/today website and create tasks for each thing the user needs to complete, then open the notepad window back using `cloud_vision_ui_interaction` tool.
                -When user asks to purchase something, find a amazon link for a simmilar product and open that url.""",
                tools=[run_system_cmd, analyze_screen_visually, cloud_vision_ui_interaction, set_system_volume, set_system_brightness],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
            )

            active_dashboard_model = ""

            # --- FIX: FULLY REVERTED TO ORIGINAL PURE TEXT HISTORY TO PREVENT PYDANTIC CRASHES ---
            self.chat_history.append({"role": "user", "parts": [{"text": user_cmd}]})
            if len(self.chat_history) > 6:
                self.chat_history = self.chat_history[-6:]

            if selected_mode == "Auto":
                if time.time() < auto_cooldown_until:
                    active_dashboard_model = "Auto -> Gemini 3.1 (Breaker)"
                    response = client.models.generate_content(
                        model=FALLBACK_MODEL, contents=self.chat_history, config=gen_config
                    )
                else:
                    try:
                        active_dashboard_model = "Auto -> Gemma 4"
                        response = client.models.generate_content(
                            model=PRIMARY_MODEL, contents=self.chat_history, config=gen_config
                        )
                    except Exception as primary_error:
                        print(f"\n[NETWORK ALARM] Primary failed ({primary_error}). Starting 10-Minute Cooldown. Engaging Fallback Engine...")
                        active_dashboard_model = "Auto -> Gemini 3.1 (Failover)"
                        auto_cooldown_until = time.time() + 600
                        response = client.models.generate_content(
                            model=FALLBACK_MODEL, contents=self.chat_history, config=gen_config
                        )
            
            elif selected_mode == "Gemini 3.1":
                active_dashboard_model = "Forced -> Gemini 3.1"
                response = client.models.generate_content(
                    model=FALLBACK_MODEL, contents=self.chat_history, config=gen_config
                )
            elif selected_mode == "Gemma 4":
                active_dashboard_model = "Forced -> Gemma 4"
                response = client.models.generate_content(
                    model=PRIMARY_MODEL, contents=self.chat_history, config=gen_config
                )

            if response.text: 
                speak_vocal(response.text)
                self.chat_history.append({"role": "model", "parts": [{"text": response.text}]})
            
            self.update_dashboard(active_dashboard_model, success=True)
            self.update_view("READY", self.COLOR_WHITE)
            
        except Exception as e: 
            print(f"\n[AI CRASH REPORT]: {e}")
            self.chat_history = [] 
            self.update_dashboard("API CRASH", success=False)
            self.update_view("ERROR", self.COLOR_RED)
            time.sleep(1.5)

if __name__ == "__main__":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    WakeyUI()