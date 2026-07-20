import re
from typing import Tuple, Dict


PACKAGE_MAPPING = {
    "com.android.chrome": "Chrome",
    "org.mozilla.firefox": "Firefox",
    "com.google.android.youtube": "YouTube",
    "com.instagram.android": "Instagram",
    "com.facebook.katana": "Facebook",
    "com.twitter.android": "Twitter",
    "com.whatsapp": "WhatsApp",
    "com.spotify.music": "Spotify",
    "com.reddit.frontpage": "Reddit",
    "com.valvesoftware.android.steam.community": "Steam",
    "com.slack": "Slack",
    "com.microsoft.teams": "Teams",
    "com.zhiliaoapp.musically": "TikTok",
    "com.netflix.mediaclient": "Netflix",
}

DISPLAY_NAME_MAPPING = {
    "chrome": "Chrome",
    "firefox": "Firefox",
    "msedge": "Edge",
    "edge": "Edge",
    "code": "VS Code",
    "vscode": "VS Code",
    "cursor": "Cursor",
    "terminal": "Terminal",
    "powershell": "PowerShell",
    "cmd": "Command Prompt",
    "word": "Word",
    "winword": "Word",
    "excel": "Excel",
    "powerpoint": "PowerPoint",
    "slack": "Slack",
    "teams": "Teams",
    "youtube": "YouTube",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "twitter": "Twitter",
    "whatsapp": "WhatsApp",
    "discord": "Discord",
    "spotify": "Spotify",
    "steam": "Steam",
    "reddit": "Reddit",
    "notion": "Notion",
    "explorer": "File Explorer",
}

class AppClassifier:
    def __init__(self):
        # Caching layer to avoid repetitive evaluation
        self.cache: Dict[str, Tuple[str, float]] = {}
        
        # Regex contextual rules for window title or browser URLs
        self.rules = [
            # Productive Contexts
            (re.compile(r"leetcode|hackerrank|codewars|github|gitlab|bitbucket|stackoverflow|notion|jira|confluence|docs\.", re.IGNORECASE), "productive", 0.95),
            (re.compile(r"chatgpt|claude|gemini|copilot|bard|huggingface|prompt", re.IGNORECASE), "productive", 0.85),
            (re.compile(r"vs code|vscode|cursor|pycharm|intellij|eclipse|sublime|webstorm|terminal|powershell|bash|cmd|git", re.IGNORECASE), "productive", 0.95),
            (re.compile(r"excel|sheets|word|powerpoint|pdf|documentation|tutorials|stackexchange", re.IGNORECASE), "productive", 0.8),
            
            # Distracting Contexts
            (re.compile(r"youtube|instagram|facebook|twitter|x\.com|reddit|netflix|spotify|steam|twitch|disney|hulu|prime video", re.IGNORECASE), "distracting", 0.98),
            (re.compile(r"shopping|amazon|ebay|walmart|flipkart|aliexpress|games|gaming|arcade|chess", re.IGNORECASE), "distracting", 0.85)
        ]
        
        # Base Application classification fallbacks
        self.app_rules = {
            "code": "productive",
            "cursor": "productive",
            "cmd": "productive",
            "powershell": "productive",
            "terminal": "productive",
            "slack": "neutral",
            "teams": "neutral",
            "zoom": "neutral",
            "whatsapp": "neutral",
            "discord": "distracting",
            "spotify": "distracting",
            "steam": "distracting",
            "chrome": "neutral",
            "firefox": "neutral",
            "msedge": "neutral",
            "explorer": "neutral"
        }
        
    def classify(self, app_name: str, window_title: str = "", browser_url: str = "") -> Tuple[str, float]:
        """
        Classifies an app usage event based on application name, active window title, and browser URL.
        Returns: Tuple[classification (productive/distracting/neutral), confidence (0.0 to 1.0)]
        """
        app_clean = app_name.lower().strip()
        title_clean = window_title.lower().strip()
        url_clean = browser_url.lower().strip()
        
        cache_key = f"{app_clean}:{title_clean}:{url_clean}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        # 1. Test App Name, Window Title, and URL Context rules (high confidence)
        context_str = f"{app_clean} {title_clean} {url_clean}"
        for regex, classification, confidence in self.rules:
            if regex.search(context_str):
                result = (classification, confidence)
                self.cache[cache_key] = result
                return result

                
        # 2. Test App Name direct match rules
        if app_clean in self.app_rules:
            result = (self.app_rules[app_clean], 0.75)
            self.cache[cache_key] = result
            return result
            
        # 3. Fallback default (low confidence neutral)
        result = ("neutral", 0.3)
        self.cache[cache_key] = result
        return result

# Global singleton instance
classifier = AppClassifier()

def auto_classify(app_name: str, window_title: str = "", browser_url: str = "") -> str:
    """Helper functional wrapper returning just the classification string."""
    classification, _ = classifier.classify(app_name, window_title, browser_url)
    return classification

def normalize_app_name(app_name: str) -> str:
    """Normalizes package names / app names across platforms to their common display names."""
    if not app_name:
        return "Unknown"

    clean = app_name.lower().strip()
    if clean in PACKAGE_MAPPING:
        return PACKAGE_MAPPING[clean]

    short_name = clean.split("/")[-1].split("\\")[-1]
    short_name = short_name.replace(".exe", "").replace("_", " ").replace("-", " ").strip()
    if short_name in DISPLAY_NAME_MAPPING:
        return DISPLAY_NAME_MAPPING[short_name]

    if short_name:
        return " ".join(part.capitalize() for part in short_name.split())

    return app_name
