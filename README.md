# Wakey
Wakey transforms confusion into action by helping users understand information, navigate support systems, and complete digital tasks independently and safely.

Dependencies-
pip install google-genai pyautogui pywinauto SpeechRecognition gTTS pygame python-dotenv huggingface_hub Pillow pyttsx3

**Please ensure you have downloaded the .env file in the same folder as the python file.**
Gallery-
<img width="584" height="103" alt="Screenshot 2026-06-19 225838" src="https://github.com/user-attachments/assets/7c2cf525-c65c-48a6-83c3-dd10e3a1cf2a" />

Flowchart;
<img width="800" height="1035" alt="Document (6)PDF_260614_094505" src="https://github.com/user-attachments/assets/d068d011-f55c-44b7-888f-b12417b61de2" />
Features-
1. Hybrid Cognitive & Vision Routing Core
   Dynamic Dual-Model Pipeline: Intelligently switches between a high-capacity primary model (gemma-4-31b-a4b-it) and a high-speed fallback model (gemini-3.1-flash-lite).
   Cloud Failover System with Auto-Cooldown: Monitors API health in real-time. If the primary cloud model encounters an error or network drop, Wakey instantly fails over to the lighter engine and triggers a strict 10-minute cooldown timer before attempting to restore the primary model.
   Persistent Pure-Text Conversational Memory: Maintains a continuous text-based conversation buffer (chat_history) restricted to the last 6 messages to provide lightweight context preservation without inducing payload bloat or API latency.
   Multi-Modal Spatial Analysis Core: Enables the cloud AI to interpret live user interfaces via on-demand context-bound screenshots (pyautogui), matching structural descriptions to interface objects.
   DPI-Aware Native Display Mapping: Implements OS-level display awareness hooks via ctypes to ensure that spatial coordinates derived on the 0–1000 scale translate flawlessly to active screen resolutions, regardless of Windows desktop display scaling (e.g., 125% or 150%).
2. Deep Native Security Firewalls (The Defense Architecture)
   Dual-Tier Proactive & Passive Security Network: Operates a real-time behavioral guardrail system that acts simultaneously before command execution and after script completion.
   Automated EDR Code Auditor: Connects asynchronously to a secondary cyber firewall model (Qwen/Qwen2.5-7B-Instruct) hosted via Hugging Face to inspect background processes for hidden code execution, malicious registry injections, bypass behaviors, or sneaky console flags (e.g., -ExecutionPolicy Bypass, -WindowStyle Hidden).
   Absolute Command Blocklist: Hardcodes a permanent barrier against catastrophic system directives (e.g., format, diskpart), immediately neutralizing the AI loop if triggered.
   Interactive Secondary Word-Based Intercept Firewall: Dynamically traps risky terminal verbs (e.g., del, rd, rmdir, reg delete, shutdown, regedit) and pauses operation before any filesystem damage occurs.
   Interactive UI Safety Layer: Monitors target action descriptions, automatically halting local or vision-based click pipelines if they attempt to engage with high-stakes targets containing risk words like "delete", "submit", "pay", "checkout", or "sign".
   Multi-Modal Dialog Confirmation Threading: Pauses risky command loops and triggers an orange, top-most Tkinter ACTION REQUIRED pop-up window while spinning up a temporary background voice listener allowing you to click a physical button or say "Confirm" / "Proceed" to authenticate the script.
3. Accessible Assistive UI & Persona Matrix
    Top-Most Streamlined Pill Dashboard: Implements an overlay design using Tkinter shapes configured to override native window decorations (overrideredirect), ensuring it stays locked above active applications without taking up massive desktop real estate.
   Dynamic Chroma Status Indicators: Shifts the color of the pill dashboard on-demand to signal operational states to users with cognitive or visual tracking preferences:
   WHITE - System Ready Idle
   BLUE - Microphone Active / Actively Listening
   GREEN - Background Processing / Executing Automated Tasks
   RED - Environment Errors, Crash Warnings
   Real-Time Operational Analytics: Features an on-dashboard metrics monitor tracking the currently engaged engine along with a continuous API transaction success rate calculator.
System Privacy Mode: Toggles a metadata-masking switch via physical UI checkbox or voice macro ("mode privacy"), fully blinding file log engines from caching text blocks during highly sensitive tasks.
Dynamic Accessibility Persona Engine: Alters the baseline system instructions of the AI agent on the fly to support diverse cognitive, sensory, and motor needs:
Vision Persona Mode: Shifts system logic to emphasize detailed spoken audio descriptions of layouts, reading values out loud instead of relying on the user scanning the display.
Motor Persona Mode: Instructs the AI model to aggressively construct script templates, maximize typing automation, and handle execution to bypass the need for physical mouse and keyboard inputs.
Cognitive Persona Mode: Forces the engine to re-map text output to brief, single, bite-sized tasks, filtering out technical jargon and paragraphs to prevent sensory overload.
4. Hybrid Automation Engines (Offline Edge vs. Cloud Vision)
Strict Local Command Interceptor: Detects specific, direct user commands matching the pattern "in this window click [Target]" and handles them entirely offline without pinging cloud networks.
Offline UI Element-Tree Scraper: Restores an native scraping framework via pywinauto to interact directly with internal UI components across desktop structures entirely at the edge.
Multi-Format UI Interaction Driver: Translates target components into physical inputs, invoking deep element procedures or executing manual layout positioning (pyautogui.click(), pyautogui.write()) as a fallback method.
On-Demand Visual Analyzer (analyze_screen_visually): Feeds temporary desktop images into the fast vision model, enabling the AI to extract layout summaries, discover form elements, and visually track interfaces.
5. Multi-Lingual Speech & Audio Pipelines
Continuous Ambient Mic Adaptation: Tunes audio streams via SpeechRecognition's background noise floor threshold tracking to filter out surrounding distortions before a user engages with the hotword.
Multi-Language Speech-To-Text (STT): Integrates regional configurations to decode live audio arrays seamlessly across multiple primary structural maps:
English (en-US)
Hindi (hi-IN)
Arabic (ar-AE)
French (fr-FR)
Dynamic Localization Voice Engine: Switches active input/output audio targets on the fly via specialized voice macros (e.g., "language set to arabic"), updating system drops and text indicators simultaneously.
Dual-Layer Fail-Safe Text-To-Speech (TTS): Processes vocalized strings through Google's cloud text synthesis (gTTS), while keeping a localized, fully offline fallback model (pyttsx3) ready to execute if web connections fail.
6. System Utility Macros (Rapid Local Short-Circuits)
Instant Media Controls: Completely short-circuits the AI processor block to directly trigger core desktop keys (playpause), controlling visual or background audio elements instantly.
Real-Time Clock Engine: Returns accurate system metadata formatting ("It is HH:MM PM") purely at the device level without utilizing tokens.
Desktop Workspace Toggles: Triggers core Windows macro shortcuts via script (Win + D) to minimize layout confusion and instantly show the desktop view.
Dynamic Hardware Manipulation: Translates continuous numerical phrases to alter native device variables, leveraging custom terminal wrappers to inject level changes to sound cards or monitor brightness configurations.
Rapid Application Launch/Kill Maps: Houses pre-configured process dictionaries to immediately initialize tool pathways (e.g., Paint, Notepad, Calc, Chrome, Edge) or terminate hanging tasks violently via taskkill protocols.
API Key Rotation Pool: Configures standard environment files to read and loop sequentially through an array of three separate API keys, protecting system performance against sudden throughput throttling.


   
   
   
   
