# -*- coding: utf-8 -*-
import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import json
import logging
import signal
import threading
import re
import sys
import atexit
import requests
import random
import hashlib
# --- Flask Keep Alive ---
from flask import Flask
from threading import Thread
app = Flask('')
@app.route('/')
def home():
    return "🤖 EXE CODEX 🦁 is Running!"
@app.route('/health')
def health():
    return {"status": "healthy", "uptime": get_uptime()}
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("✅ Flask Keep-Alive server started.")
# --- End Flask Keep Alive ---
# --- Configuration ---
TOKEN = '8911946857:AAE8fGMCE-ZdJ32y5toAS7aIIZ0bHkx1e04'
OWNER_ID = 8257117768
ADMIN_ID = 8257117768
YOUR_USERNAME = '@Brexxee'
UPDATE_CHANNEL = 'https://t.me/+VWY-7wa_svxjM2Vl'
# Folder setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
# File upload limits
FREE_USER_LIMIT = 10
SUBSCRIBED_USER_LIMIT = 15
ADMIN_LIMIT = 999
OWNER_LIMIT = float('inf')
# Create necessary directories
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
# Initialize bot
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
# --- Data structures ---
bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False
bot_start_time = datetime.now()
# Animation States
user_operations = {}  # Track ongoing operations per user
# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'bot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# --- Animation Classes ---
class ProgressAnimation:
    """Handles progress bar animations"""
    @staticmethod
    def create_progress_bar(current, total, length=4, style='blocks'):
        """Create a progress bar string using 🟩 and ⬜ (fixed 4-length, no % in bar)"""
        progress = int((current / total) * length)
        bar = "🟩" * progress + "⬜" * (length - progress)
        return f"[{bar}]"

class TerminalAnimation:
    """Creates terminal-style animations and outputs"""
    @staticmethod
    def create_terminal_box(title, content, status="running"):
        """Create a terminal-style box"""
        status_icons = {
            "running": "🟢",
            "stopped": "🔴",
            "error": "⚠️",
            "success": "✅",
            "loading": "⏳"
        }
        icon = status_icons.get(status, "📦")
        box = f"""
╔═══════════════════════════════════╗
║ {icon} {title[:30]:<30} ║
╠═══════════════════════════════════╣
║ {content[:32]:<32} ║
╚═══════════════════════════════════╝
"""
        return box

    @staticmethod
    def create_log_entry(action, details, timestamp=None):
        """Create a log-style entry"""
        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M:%S")
        return f"[{timestamp}] {action}: {details}"

    @staticmethod
    def create_ascii_header(text):
        """Create a simple ASCII header"""
        border = "═" * (len(text) + 4)
        return f"╔{border}╗\n║  {text}  ║\n╚{border}╝"

# --- Animated Message Functions ---
def send_animated_message(chat_id, final_text, animation_type="loading", duration=2, steps=4):
    """Send animated message using the new ⚙️ 𝐋ᴏᴀᴅɪɴɢ... style"""
    try:
        # Map animation types to action texts
        action_map = {
            "loading": "Authenticating session",
            "upload": "Uploading file",
            "download": "Downloading file",
            "delete": "Deleting file",
            "run": "Starting script",
            "stop": "Stopping script",
            "install": "Installing dependencies",
            "terminal": "Initializing terminal"
        }
        action_text = action_map.get(animation_type, "Processing")

        msg = None
        for i in range(steps + 1):
            percent = int((i / steps) * 100)
            bar = "🟩" * i + "⬜" * (steps - i)
            display = f"⚙️ 𝐋ᴏᴀᴅɪɴɢ... ({percent}%)\n[{bar}] {action_text}..."
            if i == 0:
                msg = bot.send_message(chat_id, display)
            else:
                try:
                    bot.edit_message_text(display, chat_id, msg.message_id)
                except:
                    pass
            time.sleep(duration / steps)

        # Final message
        try:
            bot.edit_message_text(final_text, chat_id, msg.message_id, parse_mode='HTML')
        except:
            bot.send_message(chat_id, final_text, parse_mode='HTML')
        return msg
    except Exception as e:
        logger.error(f"Animation error: {e}")
        return bot.send_message(chat_id, final_text, parse_mode='HTML')

def send_progress_animation(chat_id, action_text, total_steps=4, callback=None):
    """Send progress using new style: ⚙️ 𝐋ᴏᴀᴅɪɴɢ... + [🟩...]"""
    try:
        msg = None
        for step in range(total_steps + 1):
            percent = int((step / total_steps) * 100)
            bar = "🟩" * step + "⬜" * (total_steps - step)
            display = f"⚙️ 𝐋ᴏᴀᴅɪɴɢ... ({percent}%)\n[{bar}] {action_text}..."
            if step == 0:
                msg = bot.send_message(chat_id, display)
            else:
                try:
                    bot.edit_message_text(display, chat_id, msg.message_id)
                except:
                    pass
            time.sleep(0.4)
            if callback:
                callback(step, total_steps)
        return msg
    except Exception as e:
        logger.error(f"Progress animation error: {e}")
        return None

def send_spinner_animation(chat_id, text, duration=3):
    """Fallback: use loading animation if spinner is called"""
    return send_animated_message(chat_id, text, animation_type="loading", duration=duration)

def send_terminal_animation(chat_id, commands, final_output):
    """Use standard loading animation for terminal too"""
    return send_animated_message(chat_id, final_output, animation_type="terminal", duration=2)

# --- Utility Functions ---
def get_uptime():
    """Get bot uptime as string"""
    uptime = datetime.now() - bot_start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"

def format_size(size_bytes):
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def get_system_stats():
    """Get system statistics"""
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return {
        'cpu': cpu,
        'memory_used': memory.percent,
        'memory_total': format_size(memory.total),
        'disk_used': disk.percent,
        'disk_total': format_size(disk.total),
        'uptime': get_uptime()
    }

def create_system_stats_message():
    """Create formatted system stats message"""
    stats = get_system_stats()
    running_bots = len([k for k, v in bot_scripts.items() if v.get('process') and is_bot_running_check(k)])
    msg = f"""
╔══════════════════════════════════════╗
║       📊 <b>EXE CODEX 𝐒𝐓𝐀𝐓𝐒</b> 📊         ║
╠══════════════════════════════════════╣
║ 🖥️ <b>𝐂𝐏𝐔 𝐔𝐬𝐚𝐠𝐞:</b> {stats['cpu']}%
║ {create_mini_bar(stats['cpu'])}
║
║ 🧠 <b>𝐌𝐞𝐦𝐨𝐫𝐲:</b> {stats['memory_used']}% / {stats['memory_total']}
║ {create_mini_bar(stats['memory_used'])}
║
║ 💾 <b>𝐃𝐢𝐬𝐤:</b> {stats['disk_used']}% / {stats['disk_total']}
║ {create_mini_bar(stats['disk_used'])}
║
║ ⏱️ <b>𝐔𝐩𝐭𝐢𝐦𝐞:</b> {stats['uptime']}
║ 🤖 <b>𝐑𝐮𝐧𝐧𝐢𝐧𝐠 𝐁𝐨𝐭𝐬:</b> {running_bots}
║ 👥 <b>𝐓𝐨𝐭𝐚𝐥 𝐔𝐬𝐞𝐫𝐬:</b> {len(active_users)}
╚══════════════════════════════════════╝
"""
    return msg

def create_mini_bar(percentage, length=20):
    """Create a mini progress bar for stats"""
    filled = int((percentage / 100) * length)
    bar = '█' * filled + '░' * (length - filled)
    return f"║ [{bar}]"

def is_bot_running_check(script_key):
    """Quick check if bot is running"""
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            proc = psutil.Process(script_info['process'].pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except:
            return False
    return False

# --- Database Functions ---
def init_db():
    """Initialize the database with required tables"""
    logger.info(f"Initializing database at: {DATABASE_PATH}")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
(user_id INTEGER PRIMARY KEY, expiry TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
(user_id INTEGER, file_name TEXT, file_type TEXT, upload_time TEXT,
file_size INTEGER, PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users
(user_id INTEGER PRIMARY KEY, username TEXT, first_seen TEXT, last_seen TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins
(user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS bot_logs
(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT,
details TEXT, timestamp TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS running_scripts
(script_key TEXT PRIMARY KEY, user_id INTEGER, file_name TEXT,
start_time TEXT, pid INTEGER)''')
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)

def load_data():
    """Load data from database into memory"""
    logger.info("Loading data from database...")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, expiry FROM subscriptions')
        for user_id, expiry in c.fetchall():
            try:
                user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry)}
            except ValueError:
                logger.warning(f"Invalid expiry format for user {user_id}")
        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for user_id, file_name, file_type in c.fetchall():
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id].append((file_name, file_type))
        c.execute('SELECT user_id FROM active_users')
        active_users.update(user_id for (user_id,) in c.fetchall())
        c.execute('SELECT user_id FROM admins')
        admin_ids.update(user_id for (user_id,) in c.fetchall())
        conn.close()
        logger.info(f"Data loaded: {len(active_users)} users, {len(user_subscriptions)} subs, {len(admin_ids)} admins")
    except Exception as e:
        logger.error(f"❌ Error loading  {e}", exc_info=True)

def save_user_file_db(user_id, file_name, file_type, file_size=0):
    """Save file info to database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO user_files
(user_id, file_name, file_type, upload_time, file_size)
VALUES (?, ?, ?, ?, ?)''',
                  (user_id, file_name, file_type, datetime.now().isoformat(), file_size))
        conn.commit()
        conn.close()
        log_action(user_id, "FILE_UPLOAD", f"Uploaded {file_name}")
    except Exception as e:
        logger.error(f"Error saving file to DB: {e}")

def remove_user_file_db(user_id, file_name):
    """Remove file from database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
        conn.commit()
        conn.close()
        log_action(user_id, "FILE_DELETE", f"Deleted {file_name}")
    except Exception as e:
        logger.error(f"Error removing file from DB: {e}")

def save_active_user(user_id, username=None):
    """Save or update active user"""
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute('''INSERT INTO active_users (user_id, username, first_seen, last_seen)
VALUES (?, ?, ?, ?)
ON CONFLICT(user_id) DO UPDATE SET last_seen = ?, username = ?''',
                  (user_id, username, now, now, now, username))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving active user: {e}")

def log_action(user_id, action, details):
    """Log user action to database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''INSERT INTO bot_logs (user_id, action, details, timestamp)
VALUES (?, ?, ?, ?)''',
                  (user_id, action, details, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error logging action: {e}")

def save_subscription(user_id, expiry):
    """Save subscription to database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)',
                  (user_id, expiry.isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving subscription: {e}")

# Initialize DB and Load Data
init_db()
load_data()

# --- Helper Functions ---
def get_user_folder(user_id):
    """Get or create user's folder"""
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_file_limit(user_id):
    """Get file upload limit for user"""
    if user_id == OWNER_ID:
        return OWNER_LIMIT
    if user_id in admin_ids:
        return ADMIN_LIMIT
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now():
        return SUBSCRIBED_USER_LIMIT
    return FREE_USER_LIMIT

def get_user_file_count(user_id):
    """Get number of files uploaded by user"""
    return len(user_files.get(user_id, []))

def is_bot_running(script_owner_id, file_name):
    """Check if a bot script is running"""
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            proc = psutil.Process(script_info['process'].pid)
            is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            if not is_running:
                cleanup_script(script_key)
            return is_running
        except psutil.NoSuchProcess:
            cleanup_script(script_key)
            return False
        except Exception as e:
            logger.error(f"Error checking process: {e}")
            return False
    return False

def cleanup_script(script_key):
    """Clean up script resources"""
    if script_key in bot_scripts:
        script_info = bot_scripts[script_key]
        if 'log_file' in script_info and hasattr(script_info['log_file'], 'close'):
            try:
                if not script_info['log_file'].closed:
                    script_info['log_file'].close()
            except:
                pass
        del bot_scripts[script_key]
        logger.info(f"Cleaned up script: {script_key}")

def kill_process_tree(process_info):
    """Kill a process and all its children"""
    script_key = process_info.get('script_key', 'N/A')
    pid = None
    try:
        if 'log_file' in process_info and hasattr(process_info['log_file'], 'close'):
            try:
                if not process_info['log_file'].closed:
                    process_info['log_file'].close()
            except:
                pass
        process = process_info.get('process')
        if process and hasattr(process, 'pid'):
            pid = process.pid
            try:
                parent = psutil.Process(pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                gone, alive = psutil.wait_procs(children, timeout=2)
                for p in alive:
                    try:
                        p.kill()
                    except:
                        pass
                try:
                    parent.terminate()
                    parent.wait(timeout=2)
                except psutil.TimeoutExpired:
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass
            except psutil.NoSuchProcess:
                logger.warning(f"Process {pid} already gone")
            except Exception as e:
                logger.error(f"Error killing process: {e}")
    except Exception as e:
        logger.error(f"Error in kill_process_tree: {e}")

# --- Package Installation ---
TELEGRAM_MODULES = {
    'telebot': 'pytelegrambotapi',
    'telegram': 'python-telegram-bot',
    'pyrogram': 'pyrogram',
    'telethon': 'telethon',
    'aiogram': 'aiogram',
    'PIL': 'Pillow',
    'cv2': 'opencv-python',
    'sklearn': 'scikit-learn',
    'bs4': 'beautifulsoup4',
    'dotenv': 'python-dotenv',
    'yaml': 'pyyaml',
    'aiohttp': 'aiohttp',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'requests': 'requests',
    'flask': 'flask',
    'django': 'django',
    'fastapi': 'fastapi',
}

def attempt_install_pip(module_name, message):
    """Attempt to install a Python package with animation"""
    package_name = TELEGRAM_MODULES.get(module_name.lower(), module_name)
    if package_name is None:
        return False
    try:
        msg = send_spinner_animation(message.chat.id, f"Installing {package_name}...", duration=2)
        command = [sys.executable, '-m', 'pip', 'install', package_name]
        result = subprocess.run(command, capture_output=True, text=True, check=False,
                                encoding='utf-8', errors='ignore', timeout=120)
        if result.returncode == 0:
            try:
                bot.edit_message_text(
                    f"✅ <b>Package Installed!</b>\n📦 <code>{package_name}</code> installed successfully!",
                    message.chat.id, msg.message_id, parse_mode='HTML'
                )
            except:
                bot.send_message(message.chat.id, f"✅ Package {package_name} installed!", parse_mode='HTML')
            return True
        else:
            error_msg = result.stderr[:500] if result.stderr else result.stdout[:500]
            try:
                bot.edit_message_text(
                    f"❌ <b>Installation Failed</b>\n<code>{error_msg}</code>",
                    message.chat.id, msg.message_id, parse_mode='HTML'
                )
            except:
                pass
            return False
    except subprocess.TimeoutExpired:
        bot.send_message(message.chat.id, f"⏱️ Installation timed out for {package_name}")
        return False
    except Exception as e:
        logger.error(f"Install error: {e}")
        return False

def attempt_install_npm(module_name, user_folder, message):
    """Attempt to install an npm package with animation"""
    try:
        msg = send_spinner_animation(message.chat.id, f"Installing npm: {module_name}...", duration=2)
        command = ['npm', 'install', module_name]
        result = subprocess.run(command, capture_output=True, text=True, check=False,
                                cwd=user_folder, encoding='utf-8', errors='ignore', timeout=120)
        if result.returncode == 0:
            try:
                bot.edit_message_text(
                    f"✅ <b>NPM Package Installed!</b>\n📦 <code>{module_name}</code>",
                    message.chat.id, msg.message_id, parse_mode='HTML'
                )
            except:
                pass
            return True
        else:
            return False
    except FileNotFoundError:
        bot.send_message(message.chat.id, "❌ NPM not found! Install Node.js first.")
        return False
    except Exception as e:
        logger.error(f"NPM install error: {e}")
        return False

# --- Script Running Functions ---
def run_script(script_path, script_owner_id, user_folder, file_name, message_obj, attempt=1):
    """Run Python script with animation"""
    max_attempts = 3
    if attempt > max_attempts:
        bot.send_message(message_obj.chat.id, f"❌ Failed to run '{file_name}' after {max_attempts} attempts.")
        return
    script_key = f"{script_owner_id}_{file_name}"
    logger.info(f"Running script: {script_path} (Attempt {attempt})")
    try:
        if not os.path.exists(script_path):
            bot.send_message(message_obj.chat.id, f"❌ Script '{file_name}' not found!")
            return
        check_result = subprocess.run(
            [sys.executable, '-c', f'import ast; ast.parse(open("{script_path}").read())'],
            capture_output=True, text=True, timeout=10
        )
        if check_result.returncode != 0:
            bot.send_message(message_obj.chat.id,
                             f"⚠️ <b>Syntax Error in Script</b>\n<code>{check_result.stderr[:500]}</code>",
                             parse_mode='HTML')
            return
        terminal_msg = f"""
╔══════════════════════════════════════╗
║      🚀 <b>EXE CODEX: STARTING SCRIPT</b> 🚀 ║
╠══════════════════════════════════════╣
║ 📄 File: <code>{file_name[:25]}</code>
║ 👤 User: {script_owner_id}
║ 🔄 Attempt: {attempt}/{max_attempts}
╚══════════════════════════════════════╝
"""
        msg = send_animated_message(message_obj.chat.id, terminal_msg, "run", duration=2)
        log_file_path = os.path.join(LOGS_DIR, f"{script_key}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        process = subprocess.Popen(
            [sys.executable, script_path],
            cwd=user_folder,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        bot_scripts[script_key] = {
            'process': process,
            'file_name': file_name,
            'user_id': script_owner_id,
            'start_time': datetime.now(),
            'log_file': log_file,
            'log_path': log_file_path,
            'script_key': script_key,
            'script_path': script_path
        }
        time.sleep(2)
        if process.poll() is None:
            success_msg = f"""
╔══════════════════════════════════════╗
║     ✅ <b>EXE CODEX: SCRIPT RUNNING</b> ✅   ║
╠══════════════════════════════════════╣
║ 📄 <b>File:</b> <code>{file_name[:25]}</code>
║ 🆔 <b>PID:</b> {process.pid}
║ ⏱️ <b>Started:</b> {datetime.now().strftime('%H:%M:%S')}
╚══════════════════════════════════════╝
"""
            try:
                bot.edit_message_text(success_msg, message_obj.chat.id, msg.message_id, parse_mode='HTML')
            except:
                bot.send_message(message_obj.chat.id, success_msg, parse_mode='HTML')
            log_action(script_owner_id, "SCRIPT_START", f"Started {file_name} (PID: {process.pid})")
        else:
            log_file.close()
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                error_output = f.read()[-1000:]
            match = re.search(r"ModuleNotFoundError: No module named '(.+?)'", error_output)
            if match:
                module_name = match.group(1).strip()
                if attempt_install_pip(module_name, message_obj):
                    time.sleep(1)
                    run_script(script_path, script_owner_id, user_folder, file_name, message_obj, attempt + 1)
                    return
            error_msg = f"""
╔══════════════════════════════════════╗
║     ❌ <b>EXE CODEX: SCRIPT FAILED</b> ❌     ║
╠══════════════════════════════════════╣
║ 📄 <b>File:</b> <code>{file_name[:25]}</code>
║ ❗ <b>Exit Code:</b> {process.returncode}
╠══════════════════════════════════════╣
<code>{error_output[:400]}</code>
╚══════════════════════════════════════╝
"""
            try:
                bot.edit_message_text(error_msg, message_obj.chat.id, msg.message_id, parse_mode='HTML')
            except:
                bot.send_message(message_obj.chat.id, error_msg, parse_mode='HTML')
            cleanup_script(script_key)
    except Exception as e:
        logger.error(f"Error running script: {e}", exc_info=True)
        bot.send_message(message_obj.chat.id, f"❌ Error: {str(e)[:200]}")

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj, attempt=1):
    """Run JavaScript/Node.js script with animation"""
    max_attempts = 3
    if attempt > max_attempts:
        bot.send_message(message_obj.chat.id, f"❌ Failed to run '{file_name}' after {max_attempts} attempts.")
        return
    script_key = f"{script_owner_id}_{file_name}"
    logger.info(f"Running JS script: {script_path} (Attempt {attempt})")
    try:
        if not os.path.exists(script_path):
            bot.send_message(message_obj.chat.id, f"❌ Script '{file_name}' not found!")
            return
        terminal_msg = f"""
╔══════════════════════════════════════╗
║      🟢 <b>EXE CODEX: STARTING NODE.JS</b> 🟢║
╠══════════════════════════════════════╣
║ 📄 File: <code>{file_name[:25]}</code>
║ 👤 User: {script_owner_id}
║ 🔄 Attempt: {attempt}/{max_attempts}
╚══════════════════════════════════════╝
"""
        msg = send_animated_message(message_obj.chat.id, terminal_msg, "run", duration=2)
        log_file_path = os.path.join(LOGS_DIR, f"{script_key}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        process = subprocess.Popen(
            ['node', script_path],
            cwd=user_folder,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        bot_scripts[script_key] = {
            'process': process,
            'file_name': file_name,
            'user_id': script_owner_id,
            'start_time': datetime.now(),
            'log_file': log_file,
            'log_path': log_file_path,
            'script_key': script_key,
            'script_path': script_path,
            'type': 'js'
        }
        time.sleep(2)
        if process.poll() is None:
            success_msg = f"""
╔══════════════════════════════════════╗
║     ✅ <b>EXE CODEX: NODE.JS RUNNING</b> ✅  ║
╠══════════════════════════════════════╣
║ 📄 <b>File:</b> <code>{file_name[:25]}</code>
║ 🆔 <b>PID:</b> {process.pid}
║ ⏱️ <b>Started:</b> {datetime.now().strftime('%H:%M:%S')}
╚══════════════════════════════════════╝
"""
            try:
                bot.edit_message_text(success_msg, message_obj.chat.id, msg.message_id, parse_mode='HTML')
            except:
                bot.send_message(message_obj.chat.id, success_msg, parse_mode='HTML')
        else:
            log_file.close()
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                error_output = f.read()[-1000:]
            match = re.search(r"Cannot find module '(.+?)'", error_output)
            if match:
                module_name = match.group(1).strip()
                if attempt_install_npm(module_name, user_folder, message_obj):
                    time.sleep(1)
                    run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj, attempt + 1)
                    return
            error_msg = f"""
╔══════════════════════════════════════╗
║     ❌ <b>EXE CODEX: NODE.JS FAILED</b> ❌    ║
╠══════════════════════════════════════╣
║ 📄 <b>File:</b> <code>{file_name[:25]}</code>
║ ❗ <b>Exit Code:</b> {process.returncode}
╠══════════════════════════════════════╣
<code>{error_output[:400]}</code>
╚══════════════════════════════════════╝
"""
            try:
                bot.edit_message_text(error_msg, message_obj.chat.id, msg.message_id, parse_mode='HTML')
            except:
                bot.send_message(message_obj.chat.id, error_msg, parse_mode='HTML')
            cleanup_script(script_key)
    except FileNotFoundError:
        bot.send_message(message_obj.chat.id, "❌ Node.js not found! Install Node.js first.")
    except Exception as e:
        logger.error(f"Error running JS script: {e}", exc_info=True)
        bot.send_message(message_obj.chat.id, f"❌ Error: {str(e)[:200]}")

# --- Keyboard Layouts ---
def get_main_keyboard(user_id):
    """Get main keyboard based on user type"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if user_id == OWNER_ID or user_id in admin_ids:
        markup.row("📢 Updates Channel", "📤 Upload File")
        markup.row("📂 Check Files", "🟢 Running Bots")
        markup.row("⚡ Bot Speed", "📊 Statistics")
        markup.row("💳 Subscriptions", "📢 Broadcast")
        markup.row("🔒 Lock Bot", "👑 Admin Panel")
        markup.row("📞 Contact Owner")
    else:
        markup.row("📢 Updates Channel", "📤 Upload File")
        markup.row("📂 Check Files", "🟢 My Running Bots")
        markup.row("⚡ Bot Speed", "📊 My Stats")
        markup.row("📞 Contact Owner")
    return markup

def get_file_actions_keyboard(file_name, is_running=False):
    """Get inline keyboard for file actions"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.add(
            types.InlineKeyboardButton("🛑 Stop", callback_data=f"stop_{file_name}"),
            types.InlineKeyboardButton("📋 Logs", callback_data=f"logs_{file_name}")
        )
        markup.add(
            types.InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{file_name}")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("▶️ Run", callback_data=f"run_{file_name}"),
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{file_name}")
        )
        markup.add(
            types.InlineKeyboardButton("📥 Download", callback_data=f"download_{file_name}"),
            types.InlineKeyboardButton("📝 Edit", callback_data=f"edit_{file_name}")
        )
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_files"))
    return markup

# --- Command Handlers ---
@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    active_users.add(user_id)
    save_active_user(user_id, username)
    log_action(user_id, "START", "Started the bot")
    if bot_locked and user_id not in admin_ids and user_id != OWNER_ID:
        bot.reply_to(message, "🔒 𝐁𝐨𝐭 𝐢𝐬 𝐜𝐮𝐫𝐫𝐞𝐧𝐭𝐥𝐲 𝐥𝐨𝐜𝐤𝐞𝐝.")
        return
    welcome_text = f"""
╔══════════════════════════════════════╗
║    🤖 <b>EXE CODEX 🦁</b>                 ║
╠══════════════════════════════════════╣
║
║  👋 𝐖𝐞𝐥𝐜𝐨𝐦𝐞, <b>{message.from_user.first_name}</b>!
║
║  📤 𝐔𝐩𝐥𝐨𝐚𝐝 & 𝐇𝐨𝐬𝐭 𝐲𝐨𝐮𝐫 𝐛𝐨𝐭 𝐟𝐢𝐥𝐞𝐬
║  🚀 𝐑𝐮𝐧 𝐏𝐲𝐭𝐡𝐨𝐧 & 𝐍𝐨𝐝𝐞.𝐣𝐬 𝐬𝐜𝐫𝐢𝐩𝐭𝐬
║  📊 𝐌𝐨𝐧𝐢𝐭𝐨𝐫 𝐲𝐨𝐮𝐫 𝐫𝐮𝐧𝐧𝐢𝐧𝐠 𝐛𝐨𝐭𝐬
║  💾 𝐌𝐚𝐧𝐚𝐠𝐞 𝐲𝐨𝐮𝐫 𝐟𝐢𝐥𝐞𝐬 𝐞𝐚𝐬𝐢𝐥𝐲
║
╠══════════════════════════════════════╣
║  📌 <b>𝐘𝐨𝐮𝐫 𝐋𝐢𝐦𝐢𝐭𝐬:</b>
║  📁 𝐅𝐢𝐥𝐞𝐬: {get_user_file_count(user_id)}/{int(get_user_file_limit(user_id)) if get_user_file_limit(user_id) != float('inf') else '∞'}
║  💳 𝐒𝐭𝐚𝐭𝐮𝐬: {'👑 𝐎𝐰𝐧𝐞𝐫' if user_id == OWNER_ID else '⭐ 𝐀𝐝𝐦𝐢𝐧' if user_id in admin_ids else '🌟 𝐏𝐫𝐞𝐦𝐢𝐮𝐦' if user_id in user_subscriptions else '👤 𝐅𝐫𝐞𝐞'}
║
╚══════════════════════════════════════╝
𝐔𝐬𝐞 𝐭𝐡𝐞 𝐛𝐮𝐭𝐭𝐨𝐧𝐬 𝐛𝐞𝐥𝐨𝐰 𝐭𝐨 𝐧𝐚𝐯𝐢𝐠𝐚𝐭𝐞! ⬇️
"""
    send_animated_message(message.chat.id, welcome_text, "loading", duration=2)
    bot.send_message(message.chat.id, "𝐂𝐡𝐨𝐨𝐬𝐞 𝐚𝐧 𝐨𝐩𝐭𝐢𝐨𝐧:", reply_markup=get_main_keyboard(user_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    """Handle /help command"""
    help_text = """
╔══════════════════════════════════════╗
║       📚 <b>EXE CODEX HELP</b> 📚          ║
╠══════════════════════════════════════╣
║
║ <b>📤 𝐅𝐢𝐥𝐞 𝐌𝐚𝐧𝐚𝐠𝐞𝐦𝐞𝐧𝐭:</b>
║ • /upload - 𝐔𝐩𝐥𝐨𝐚𝐝 𝐚 𝐟𝐢𝐥𝐞
║ • /files - 𝐕𝐢𝐞𝐰 𝐲𝐨𝐮𝐫 𝐟𝐢𝐥𝐞𝐬
║ • /delete - 𝐃𝐞𝐥𝐞𝐭𝐞 𝐚 𝐟𝐢𝐥𝐞
║
║ <b>🤖 𝐁𝐨𝐭 𝐂𝐨𝐧𝐭𝐫𝐨𝐥:</b>
║ • /run - 𝐑𝐮𝐧 𝐚 𝐬𝐜𝐫𝐢𝐩𝐭
║ • /stop - 𝐒𝐭𝐨𝐩 𝐚 𝐫𝐮𝐧𝐧𝐢𝐧𝐠 𝐬𝐜𝐫𝐢𝐩𝐭
║ • /logs - 𝐕𝐢𝐞𝐰 𝐬𝐜𝐫𝐢𝐩𝐭 𝐥𝐨𝐠𝐬
║ • /running - 𝐒𝐞𝐞 𝐫𝐮𝐧𝐧𝐢𝐧𝐠 𝐬𝐜𝐫𝐢𝐩𝐭𝐬
║
║ <b>📊 𝐈𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧:</b>
║ • /stats - 𝐁𝐨𝐭 𝐬𝐭𝐚𝐭𝐢𝐬𝐭𝐢𝐜𝐬
║ • /speed - 𝐂𝐡𝐞𝐜𝐤 𝐛𝐨𝐭 𝐬𝐩𝐞𝐞𝐝
║ • /status - 𝐘𝐨𝐮𝐫 𝐚𝐜𝐜𝐨𝐮𝐧𝐭 𝐬𝐭𝐚𝐭𝐮𝐬
║
║ <b>🔧 𝐎𝐭𝐡𝐞𝐫:</b>
║ • /start - 𝐑𝐞𝐬𝐭𝐚𝐫𝐭 𝐛𝐨𝐭
║ • /help - 𝐓𝐡𝐢𝐬 𝐦𝐞𝐬𝐬𝐚𝐠𝐞
║
╚══════════════════════════════════════╝
"""
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')

@bot.message_handler(commands=['stats', 'statistics'])
def stats_command(message):
    """Handle /stats command"""
    user_id = message.from_user.id
    msg = send_spinner_animation(message.chat.id, "𝐆𝐚𝐭𝐡𝐞𝐫𝐢𝐧𝐠 EXE CODEX 𝐬𝐭𝐚𝐭𝐬...", duration=2)
    stats_text = create_system_stats_message()
    try:
        bot.edit_message_text(stats_text, message.chat.id, msg.message_id, parse_mode='HTML')
    except:
        bot.send_message(message.chat.id, stats_text, parse_mode='HTML')

@bot.message_handler(commands=['speed'])
def speed_command(message):
    """Handle /speed command"""
    msg = send_spinner_animation(message.chat.id, "𝐓𝐞𝐬𝐭𝐢𝐧𝐠 EXE CODEX 𝐬𝐩𝐞𝐞𝐝...", duration=2)
    start_time = time.time()
    latency = (time.time() - start_time) * 1000
    cpu = psutil.cpu_percent()
    memory = psutil.virtual_memory().percent
    speed_text = f"""
╔══════════════════════════════════════╗
║        ⚡ <b>EXE CODEX 𝐒𝐏𝐄𝐄𝐃</b> ⚡        ║
╠══════════════════════════════════════╣
║
║  🏓 <b>𝐋𝐚𝐭𝐞𝐧𝐜𝐲:</b> {latency:.2f}𝐦𝐬
║  🖥️ <b>𝐂𝐏𝐔:</b> {cpu}%
║  🧠 <b>𝐌𝐞𝐦𝐨𝐫𝐲:</b> {memory}%
║  ⏱️ <b>𝐔𝐩𝐭𝐢𝐦𝐞:</b> {get_uptime()}
║
║  {'🟢 𝐄𝐱𝐜𝐞𝐥𝐥𝐞𝐧𝐭!' if latency < 100 else '🟡 𝐆𝐨𝐨𝐝' if latency < 500 else '🔴 𝐒𝐥𝐨𝐰'}
║
╚══════════════════════════════════════╝
"""
    try:
        bot.edit_message_text(speed_text, message.chat.id, msg.message_id, parse_mode='HTML')
    except:
        bot.send_message(message.chat.id, speed_text, parse_mode='HTML')

@bot.message_handler(commands=['running'])
def running_command(message):
    """Show running bots"""
    user_id = message.from_user.id
    msg = send_spinner_animation(message.chat.id, "𝐅𝐞𝐭𝐜𝐡𝐢𝐧𝐠 EXE CODEX 𝐛𝐨𝐭𝐬...", duration=1)
    running_bots = []
    for script_key, info in bot_scripts.items():
        if is_bot_running_check(script_key):
            if user_id == OWNER_ID or user_id in admin_ids or info.get('user_id') == user_id:
                uptime = datetime.now() - info.get('start_time', datetime.now())
                running_bots.append({
                    'key': script_key,
                    'file': info.get('file_name', 'Unknown'),
                    'user': info.get('user_id', 'Unknown'),
                    'pid': info.get('process', {}).pid if info.get('process') else 'N/A',
                    'uptime': str(uptime).split('.')[0]
                })
    if running_bots:
        text = """
╔══════════════════════════════════════╗
║      🟢 <b>EXE CODEX 𝐁𝐎𝐓𝐒</b> 🟢           ║
╠══════════════════════════════════════╣
"""
        for i, bot_info in enumerate(running_bots, 1):
            text += f"""║ {i}. 📄 <code>{bot_info['file'][:20]}</code>
║    👤 𝐔𝐬𝐞𝐫: {bot_info['user']}
║    🆔 𝐏𝐈𝐃: {bot_info['pid']}
║    ⏱️ 𝐔𝐩𝐭𝐢𝐦𝐞: {bot_info['uptime']}
║ ──────────────────────────────────
"""
        text += "╚══════════════════════════════════════╝"
    else:
        text = """
╔══════════════════════════════════════╗
║      🔴 <b>𝐍𝐎 EXE CODEX 𝐁𝐎𝐓𝐒</b> 🔴        ║
╠══════════════════════════════════════╣
║
║  𝐍𝐨 𝐬𝐜𝐫𝐢𝐩𝐭𝐬 𝐚𝐫𝐞 𝐜𝐮𝐫𝐫𝐞𝐧𝐭𝐥𝐲 𝐫𝐮𝐧𝐧𝐢𝐧𝐠.
║  𝐔𝐩𝐥𝐨𝐚𝐝 𝐚 𝐟𝐢𝐥𝐞 𝐚𝐧𝐝 𝐫𝐮𝐧 𝐢𝐭!
║
╚══════════════════════════════════════╝
"""
    try:
        bot.edit_message_text(text, message.chat.id, msg.message_id, parse_mode='HTML')
    except:
        bot.send_message(message.chat.id, text, parse_mode='HTML')

@bot.message_handler(commands=['lock'])
def lock_command(message):
    """Lock/Unlock bot (Admin only)"""
    global bot_locked
    user_id = message.from_user.id
    if user_id != OWNER_ID and user_id not in admin_ids:
        bot.reply_to(message, "❌ 𝐘𝐨𝐮 𝐝𝐨𝐧'𝐭 𝐡𝐚𝐯𝐞 𝐩𝐞𝐫𝐦𝐢𝐬𝐬𝐢𝐨𝐧!")
        return
    bot_locked = not bot_locked
    status = "🔒 𝐋𝐎𝐂𝐊𝐄𝐃" if bot_locked else "🔓 𝐔𝐍𝐋𝐎𝐂𝐊𝐄𝐃"
    lock_text = f"""
╔══════════════════════════════════════╗
║         🔐 <b>EXE CODEX 𝐒𝐓𝐀𝐓𝐔𝐒</b> 🔐       ║
╠══════════════════════════════════════╣
║
║  𝐒𝐭𝐚𝐭𝐮𝐬: {status}
║  𝐁𝐲: {message.from_user.first_name}
║  𝐓𝐢𝐦𝐞: {datetime.now().strftime('%𝐇:%𝐌:%𝐒')}
║
╚══════════════════════════════════════╝
"""
    send_animated_message(message.chat.id, lock_text, "terminal", duration=1)

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    """Broadcast message to all users (Admin only)"""
    user_id = message.from_user.id
    if user_id != OWNER_ID and user_id not in admin_ids:
        bot.reply_to(message, "❌ 𝐘𝐨𝐮 𝐝𝐨𝐧'𝐭 𝐡𝐚𝐯𝐞 𝐩𝐞𝐫𝐦𝐢𝐬𝐬𝐢𝐨𝐧!")
        return
    msg = bot.reply_to(message, "📢 𝐒𝐞𝐧𝐝 𝐭𝐡𝐞 𝐦𝐞𝐬𝐬𝐚𝐠𝐞 𝐲𝐨𝐮 𝐰𝐚𝐧𝐭 𝐭𝐨 𝐛𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭:")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    """Process broadcast message"""
    broadcast_text = message.text
    if not broadcast_text:
        bot.reply_to(message, "❌ 𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐞𝐧𝐝 𝐚 𝐭𝐞𝐱𝐭 𝐦𝐞𝐬𝐬𝐚𝐠𝐞!")
        return
    progress_msg = bot.send_message(message.chat.id, "📢 𝐒𝐭𝐚𝐫𝐭𝐢𝐧𝐠 EXE CODEX 𝐛𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭...")
    success = 0
    failed = 0
    total = len(active_users)
    for i, user_id in enumerate(active_users):
        try:
            formatted_msg = f"""
╔══════════════════════════════════════╗
║      📢 <b>EXE CODEX 🦁 𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓</b> 📢    ║
╠══════════════════════════════════════╣
║
{broadcast_text}
║
╚══════════════════════════════════════╝
"""
            bot.send_message(user_id, formatted_msg, parse_mode='HTML')
            success += 1
        except:
            failed += 1
        if (i + 1) % 10 == 0:
            bar = "🟩" * ((i + 1) // (total // 4) if total > 0 else 0) + "⬜" * (4 - (i + 1) // (total // 4) if total > 0 else 4)
            bar = bar[:4].ljust(4, "⬜")
            try:
                bot.edit_message_text(
                    f"⚙️ 𝐋ᴏᴀᴅɪɴɢ... ({int((i+1)/total*100)}%)\n[{bar}] 𝐁𝐫𝐨𝐚𝐝𝐜𝐚𝐬𝐭𝐢𝐧𝐠...",
                    message.chat.id, progress_msg.message_id
                )
            except:
                pass
    result_text = f"""
╔══════════════════════════════════════╗
║     ✅ <b>EXE CODEX 𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐄</b> ✅ ║
╠══════════════════════════════════════╣
║
║  📤 𝐓𝐨𝐭𝐚𝐥: {total}
║  ✅ 𝐒𝐮𝐜𝐜𝐞𝐬𝐬: {success}
║  ❌ 𝐅𝐚𝐢𝐥𝐞𝐝: {failed}
║
╚══════════════════════════════════════╝
"""
    try:
        bot.edit_message_text(result_text, message.chat.id, progress_msg.message_id, parse_mode='HTML')
    except:
        bot.send_message(message.chat.id, result_text, parse_mode='HTML')

@bot.message_handler(commands=['subscribe', 'sub'])
def subscribe_command(message):
    """Handle subscription command (Admin only)"""
    user_id = message.from_user.id
    if user_id != OWNER_ID and user_id not in admin_ids:
        bot.reply_to(message, "❌ 𝐘𝐨𝐮 𝐝𝐨𝐧'𝐭 𝐡𝐚𝐯𝐞 𝐩𝐞𝐫𝐦𝐢𝐬𝐬𝐢𝐨𝐧!")
        return
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "𝐔𝐬𝐚𝐠𝐞: /subscribe <user_id> <days>")
        return
    try:
        target_user = int(parts[1])
        days = int(parts[2])
    except ValueError:
        bot.reply_to(message, "❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐮𝐬𝐞𝐫 𝐈𝐃 𝐨𝐫 𝐝𝐚𝐲𝐬!")
        return
    expiry = datetime.now() + timedelta(days=days)
    user_subscriptions[target_user] = {'expiry': expiry}
    save_subscription(target_user, expiry)
    sub_text = f"""
╔══════════════════════════════════════╗
║      ✅ <b>EXE CODEX 𝐒𝐔𝐁𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍</b> ✅   ║
╠══════════════════════════════════════╣
║
║  👤 𝐔𝐬𝐞𝐫: {target_user}
║  📅 𝐃𝐚𝐲𝐬: {days}
║  ⏰ 𝐄𝐱𝐩𝐢𝐫𝐞𝐬: {expiry.strftime('%𝐘-%𝐦-%𝐝 %𝐇:%𝐌')}
║
╚══════════════════════════════════════╝
"""
    send_animated_message(message.chat.id, sub_text, "loading", duration=1)
    try:
        bot.send_message(target_user, f"🎉 𝐘𝐨𝐮'𝐯𝐞 𝐛𝐞𝐞𝐧 𝐬𝐮𝐛𝐬𝐜𝐫𝐢𝐛𝐞𝐝 𝐟𝐨𝐫 {days} 𝐝𝐚𝐲𝐬 𝐛𝐲 EXE CODEX!")
    except:
        pass

# --- Text Message Handlers ---
@bot.message_handler(content_types=['text'])
def handle_text(message):
    """Handle text messages (button presses)"""
    user_id = message.from_user.id
    text = message.text
    active_users.add(user_id)
    if bot_locked and user_id not in admin_ids and user_id != OWNER_ID:
        bot.reply_to(message, "🔒 𝐁𝐨𝐭 𝐢𝐬 𝐥𝐨𝐜𝐤𝐞𝐝!")
        return
    if text == "📢 Updates Channel":
        bot.send_message(message.chat.id, f"📢 𝐉𝐨𝐢𝐧 𝐨𝐮𝐫 EXE CODEX 𝐮𝐩𝐝𝐚𝐭𝐞𝐬:\n{UPDATE_CHANNEL}")
    elif text == "📤 Upload File":
        handle_upload_request(message)
    elif text == "📂 Check Files":
        show_user_files(message)
    elif text == "🟢 Running Bots" or text == "🟢 My Running Bots":
        running_command(message)
    elif text == "⚡ Bot Speed":
        speed_command(message)
    elif text == "📊 Statistics" or text == "📊 My Stats":
        stats_command(message)
    elif text == "💳 Subscriptions":
        show_subscriptions(message)
    elif text == "📢 Broadcast":
        broadcast_command(message)
    elif text == "🔒 Lock Bot":
        lock_command(message)
    elif text == "👑 Admin Panel":
        show_admin_panel(message)
    elif text == "📞 Contact Owner":
        bot.send_message(message.chat.id, f"📞 𝐂𝐨𝐧𝐭𝐚𝐜𝐭: {YOUR_USERNAME}")

def handle_upload_request(message):
    """Handle file upload request"""
    user_id = message.from_user.id
    current_count = get_user_file_count(user_id)
    limit = get_user_file_limit(user_id)
    if current_count >= limit:
        bot.reply_to(message, f"❌ 𝐘𝐨𝐮'𝐯𝐞 𝐫𝐞𝐚𝐜𝐡𝐞𝐝 𝐲𝐨𝐮𝐫 𝐥𝐢𝐦𝐢𝐭 ({current_count}/{int(limit) if limit != float('inf') else '∞'})!")
        return
    upload_text = f"""
╔══════════════════════════════════════╗
║       📤 <b>EXE CODEX: FILE UPLOAD</b> 📤   ║
╠══════════════════════════════════════╣
║
║  𝐒𝐞𝐧𝐝 𝐲𝐨𝐮𝐫 𝐟𝐢𝐥𝐞 𝐧𝐨𝐰!
║
║  <b>𝐒𝐮𝐩𝐩𝐨𝐫𝐭𝐞𝐝 𝐟𝐨𝐫𝐦𝐚𝐭𝐬:</b>
║  • 𝐏𝐲𝐭𝐡𝐨𝐧 (.𝐩𝐲)
║  • 𝐉𝐚𝐯𝐚𝐒𝐜𝐫𝐢𝐩𝐭 (.𝐣𝐬)
║  • 𝐙𝐈𝐏 𝐚𝐫𝐜𝐡𝐢𝐯𝐞𝐬 (.𝐳𝐢𝐩)
║
║  📁 𝐅𝐢𝐥𝐞𝐬: {current_count}/{int(limit) if limit != float('inf') else '∞'}
║
╚══════════════════════════════════════╝
"""
    bot.send_message(message.chat.id, upload_text, parse_mode='HTML')

def show_user_files(message):
    """Show user's files with actions"""
    user_id = message.from_user.id
    msg = send_spinner_animation(message.chat.id, "𝐋𝐨𝐚𝐝𝐢𝐧𝐠 EXE CODEX 𝐟𝐢𝐥𝐞𝐬...", duration=1)
    files = user_files.get(user_id, [])
    if not files:
        text = """
╔══════════════════════════════════════╗
║       📂 <b>EXE CODEX: YOUR FILES</b> 📂   ║
╠══════════════════════════════════════╣
║
║  𝐘𝐨𝐮 𝐡𝐚𝐯𝐞𝐧'𝐭 𝐮𝐩𝐥𝐨𝐚𝐝𝐞𝐝 𝐚𝐧𝐲 𝐟𝐢𝐥𝐞𝐬 𝐲𝐞𝐭!
║
║  𝐔𝐬𝐞 📤 𝐔𝐩𝐥𝐨𝐚𝐝 𝐅𝐢𝐥𝐞 𝐭𝐨 𝐠𝐞𝐭 𝐬𝐭𝐚𝐫𝐭𝐞𝐝.
║
╚══════════════════════════════════════╝
"""
        try:
            bot.edit_message_text(text, message.chat.id, msg.message_id, parse_mode='HTML')
        except:
            bot.send_message(message.chat.id, text, parse_mode='HTML')
        return
    text = """
╔══════════════════════════════════════╗
║       📂 <b>EXE CODEX: YOUR FILES</b> 📂   ║
╠══════════════════════════════════════╣
"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    for i, (file_name, file_type) in enumerate(files, 1):
        is_running = is_bot_running(user_id, file_name)
        status = "🟢" if is_running else "🔴"
        type_icon = "🐍" if file_type == "py" else "🟨" if file_type == "js" else "📦"
        text += f"║ {i}. {status} {type_icon} <code>{file_name[:25]}</code>\n"
        markup.add(types.InlineKeyboardButton(
            f"{status} {file_name[:15]}",
            callback_data=f"file_{file_name}"
        ))
    text += "╚══════════════════════════════════════╝\n𝐒𝐞𝐥𝐞𝐜𝐭 𝐚 𝐟𝐢𝐥𝐞 𝐟𝐨𝐫 𝐚𝐜𝐭𝐢𝐨𝐧𝐬:"
    try:
        bot.edit_message_text(text, message.chat.id, msg.message_id, parse_mode='HTML', reply_markup=markup)
    except:
        bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)

def show_subscriptions(message):
    """Show subscription management (Admin only)"""
    user_id = message.from_user.id
    if user_id != OWNER_ID and user_id not in admin_ids:
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    active_subs = {uid: data for uid, data in user_subscriptions.items()
                   if data['expiry'] > datetime.now()}
    text = f"""
╔══════════════════════════════════════╗
║     💳 <b>EXE CODEX: SUBSCRIPTIONS</b> 💳    ║
╠══════════════════════════════════════╣
║
║  𝐀𝐜𝐭𝐢𝐯𝐞: {len(active_subs)}
║  𝐓𝐨𝐭𝐚𝐥 𝐄𝐯𝐞𝐫: {len(user_subscriptions)}
║
"""
    for uid, data in list(active_subs.items())[:10]:
        remaining = data['expiry'] - datetime.now()
        text += f"║  👤 {uid}: {remaining.days}𝐝 𝐥𝐞𝐟𝐭\n"
    text += """║
╠══════════════════════════════════════╣
║  <b>𝐀𝐝𝐝 𝐬𝐮𝐛:</b> /subscribe &lt;id&gt; &lt;days&gt;
╚══════════════════════════════════════╝
"""
    bot.send_message(message.chat.id, text, parse_mode='HTML')

def show_admin_panel(message):
    """Show admin panel"""
    user_id = message.from_user.id
    if user_id != OWNER_ID and user_id not in admin_ids:
        bot.reply_to(message, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    admin_text = f"""
╔══════════════════════════════════════╗
║       👑 <b>EXE CODEX: ADMIN PANEL</b> 👑   ║
╠══════════════════════════════════════╣
║
║  <b>📊 𝐒𝐭𝐚𝐭𝐢𝐬𝐭𝐢𝐜𝐬:</b>
║  • 𝐓𝐨𝐭𝐚𝐥 𝐔𝐬𝐞𝐫𝐬: {len(active_users)}
║  • 𝐀𝐜𝐭𝐢𝐯𝐞 𝐒𝐮𝐛𝐬: {len([u for u, d in user_subscriptions.items() if d['expiry'] > datetime.now()])}
║  • 𝐑𝐮𝐧𝐧𝐢𝐧𝐠 𝐁𝐨𝐭𝐬: {len([k for k in bot_scripts if is_bot_running_check(k)])}
║  • 𝐀𝐝𝐦𝐢𝐧𝐬: {len(admin_ids)}
║
║  <b>🔧 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬:</b>
║  • /broadcast - 𝐒𝐞𝐧𝐝 𝐭𝐨 𝐚𝐥𝐥
║  • /subscribe - 𝐀𝐝𝐝 𝐬𝐮𝐛𝐬𝐜𝐫𝐢𝐩𝐭𝐢𝐨𝐧
║  • /lock - 𝐋𝐨𝐜𝐤/𝐮𝐧𝐥𝐨𝐜𝐤 𝐛𝐨𝐭
║  • /addadmin - 𝐀𝐝𝐝 𝐚𝐝𝐦𝐢𝐧
║  • /removeadmin - 𝐑𝐞𝐦𝐨𝐯𝐞 𝐚𝐝𝐦𝐢𝐧
║  • /stopall - 𝐒𝐭𝐨𝐩 𝐚𝐥𝐥 𝐛𝐨𝐭𝐬
║
╚══════════════════════════════════════╝
"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛑 𝐒𝐭𝐨𝐩 𝐀𝐥𝐥 𝐁𝐨𝐭𝐬", callback_data="admin_stopall"),
        types.InlineKeyboardButton("🔄 𝐑𝐞𝐟𝐫𝐞𝐬𝐡 𝐒𝐭𝐚𝐭𝐬", callback_data="admin_refresh")
    )
    markup.add(
        types.InlineKeyboardButton("📊 𝐅𝐮𝐥𝐥 𝐒𝐭𝐚𝐭𝐢𝐬𝐭𝐢𝐜𝐬", callback_data="admin_fullstats"),
        types.InlineKeyboardButton("📋 𝐕𝐢𝐞𝐰 𝐋𝐨𝐠𝐬", callback_data="admin_logs")
    )
    bot.send_message(message.chat.id, admin_text, parse_mode='HTML', reply_markup=markup)

# --- File Upload Handler ---
@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Handle document uploads with progress animation"""
    user_id = message.from_user.id
    current_count = get_user_file_count(user_id)
    limit = get_user_file_limit(user_id)
    if current_count >= limit:
        bot.reply_to(message, f"❌ 𝐅𝐢𝐥𝐞 𝐥𝐢𝐦𝐢𝐭 𝐫𝐞𝐚𝐜𝐡𝐞𝐝! ({current_count}/{int(limit) if limit != float('inf') else '∞'})")
        return
    file_name = message.document.file_name
    file_size = message.document.file_size
    file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
    allowed_extensions = ['py', 'js', 'zip', 'json', 'txt', 'env', 'yml', 'yaml']
    if file_ext not in allowed_extensions:
        bot.reply_to(message, f"❌ 𝐔𝐧𝐬𝐮𝐩𝐩𝐨𝐫𝐭𝐞𝐝 𝐭𝐲𝐩𝐞: .{file_ext}")
        return
    upload_text = f"""
╔══════════════════════════════════════╗
║      📤 <b>EXE CODEX: UPLOADING</b> 📤     ║
╠══════════════════════════════════════╣
║
║  📄 𝐅𝐢𝐥𝐞: <code>{file_name[:25]}</code>
║  📦 𝐒𝐢𝐳𝐞: {format_size(file_size)}
║
"""
    progress_msg = bot.reply_to(message, upload_text + "║  ⏳ 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝𝐢𝐧𝐠...\n╚══════════════════════════════════════╝", parse_mode='HTML')
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        try:
            bot.edit_message_text(
                upload_text + "║  📥 𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠...\n╚══════════════════════════════════════╝",
                message.chat.id, progress_msg.message_id, parse_mode='HTML'
            )
        except:
            pass
        user_folder = get_user_folder(user_id)
        file_path = os.path.join(user_folder, file_name)
        if file_ext == 'zip':
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                tmp.write(downloaded_file)
                tmp_path = tmp.name
            try:
                with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                    zip_ref.extractall(user_folder)
                    extracted_files = []
                    for root, dirs, files in os.walk(user_folder):
                        for f in files:
                            if f.endswith(('.py', '.js')):
                                extracted_files.append(f)
                                if user_id not in user_files:
                                    user_files[user_id] = []
                                if (f, f.split('.')[-1]) not in user_files[user_id]:
                                    user_files[user_id].append((f, f.split('.')[-1]))
                                    save_user_file_db(user_id, f, f.split('.')[-1], 0)
                    os.unlink(tmp_path)
                    success_text = upload_text + f"""║  ✅ 𝐙𝐈𝐏 𝐄𝐱𝐭𝐫𝐚𝐜𝐭𝐞𝐝!
║  📁 𝐅𝐢𝐥𝐞𝐬: {len(extracted_files)}
╚══════════════════════════════════════╝
"""
            except zipfile.BadZipFile:
                bot.edit_message_text(
                    upload_text + "║  ❌ 𝐈𝐧𝐯𝐚𝐥𝐢𝐝 𝐙𝐈𝐏!\n╚══════════════════════════════════════╝",
                    message.chat.id, progress_msg.message_id, parse_mode='HTML'
                )
                return
        else:
            with open(file_path, 'wb') as f:
                f.write(downloaded_file)
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id] = [(n, t) for n, t in user_files[user_id] if n != file_name]
            user_files[user_id].append((file_name, file_ext))
            save_user_file_db(user_id, file_name, file_ext, file_size)
            success_text = upload_text + f"""║  ✅ 𝐔𝐩𝐥𝐨𝐚𝐝 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞!
╚══════════════════════════════════════╝
"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        if file_ext in ['py', 'js']:
            markup.add(
                types.InlineKeyboardButton("▶️ 𝐑𝐮𝐧 𝐍𝐨𝐰", callback_data=f"run_{file_name}"),
                types.InlineKeyboardButton("📂 𝐕𝐢𝐞𝐰 𝐅𝐢𝐥𝐞𝐬", callback_data="back_to_files")
            )
        else:
            markup.add(types.InlineKeyboardButton("📂 𝐕𝐢𝐞𝐰 𝐅𝐢𝐥𝐞𝐬", callback_data="back_to_files"))
        try:
            bot.edit_message_text(success_text, message.chat.id, progress_msg.message_id,
                                  parse_mode='HTML', reply_markup=markup)
        except:
            bot.send_message(message.chat.id, success_text, parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        try:
            bot.edit_message_text(
                upload_text + f"║  ❌ 𝐄𝐫𝐫𝐨𝐫: {str(e)[:30]}\n╚══════════════════════════════════════╝",
                message.chat.id, progress_msg.message_id, parse_mode='HTML'
            )
        except:
            bot.reply_to(message, f"❌ 𝐔𝐩𝐥𝐨𝐚𝐝 𝐟𝐚𝐢𝐥𝐞𝐝: {str(e)[:100]}")

# --- Callback Query Handler ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Handle all callback queries"""
    user_id = call.from_user.id
    data = call.data
    try:
        if data.startswith("file_"):
            file_name = data[5:]
            show_file_actions(call, file_name)
        elif data.startswith("run_"):
            file_name = data[4:]
            run_user_script(call, file_name)
        elif data.startswith("stop_"):
            file_name = data[5:]
            stop_user_script(call, file_name)
        elif data.startswith("delete_"):
            file_name = data[7:]
            delete_user_file(call, file_name)
        elif data.startswith("download_"):
            file_name = data[9:]
            download_user_file(call, file_name)
        elif data.startswith("logs_"):
            file_name = data[5:]
            show_script_logs(call, file_name)
        elif data.startswith("restart_"):
            file_name = data[8:]
            restart_user_script(call, file_name)
        elif data == "back_to_files":
            show_user_files_callback(call)
        elif data == "admin_stopall":
            stop_all_bots(call)
        elif data == "admin_refresh":
            refresh_admin_panel(call)
        elif data == "admin_fullstats":
            show_full_stats(call)
        elif data == "admin_logs":
            show_admin_logs(call)
        elif data.startswith("confirm_delete_"):
            file_name = data[15:]
            confirm_delete_file(call, file_name)
        elif data.startswith("cancel_delete_"):
            bot.answer_callback_query(call.id, "❌ 𝐂𝐚𝐧𝐜𝐞𝐥𝐥𝐞𝐝")
            show_user_files_callback(call)
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        bot.answer_callback_query(call.id, f"❌ 𝐄𝐫𝐫𝐨𝐫: {str(e)[:50]}")

def show_file_actions(call, file_name):
    """Show actions for a specific file"""
    user_id = call.from_user.id
    is_running = is_bot_running(user_id, file_name)
    file_type = "py"
    for name, ftype in user_files.get(user_id, []):
        if name == file_name:
            file_type = ftype
            break
    type_icon = "🐍" if file_type == "py" else "🟨" if file_type == "js" else "📄"
    status = "🟢 𝐑𝐮𝐧𝐧𝐢𝐧𝐠" if is_running else "🔴 𝐒𝐭𝐨𝐩𝐩𝐞𝐝"
    text = f"""
╔══════════════════════════════════════╗
║       📄 <b>EXE CODEX: FILE</b> 📄         ║
╠══════════════════════════════════════╣
║
║  {type_icon} <b>𝐍𝐚𝐦𝐞:</b> <code>{file_name[:25]}</code>
║  📁 <b>𝐓𝐲𝐩𝐞:</b> {file_type.upper()}
║  📊 <b>𝐒𝐭𝐚𝐭𝐮𝐬:</b> {status}
║
╚══════════════════════════════════════╝
"""
    markup = get_file_actions_keyboard(file_name, is_running)
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              parse_mode='HTML', reply_markup=markup)
    except:
        bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=markup)
    bot.answer_callback_query(call.id)

def run_user_script(call, file_name):
    """Run a user's script"""
    user_id = call.from_user.id
    user_folder = get_user_folder(user_id)
    script_path = os.path.join(user_folder, file_name)
    if not os.path.exists(script_path):
        bot.answer_callback_query(call.id, "❌ 𝐅𝐢𝐥𝐞 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝!")
        return
    if is_bot_running(user_id, file_name):
        bot.answer_callback_query(call.id, "⚠️ 𝐀𝐥𝐫𝐞𝐚𝐝𝐲 𝐫𝐮𝐧𝐧𝐢𝐧𝐠!")
        return
    bot.answer_callback_query(call.id, "🚀 𝐒𝐭𝐚𝐫𝐭𝐢𝐧𝐠...")
    if file_name.endswith('.py'):
        threading.Thread(target=run_script,
                         args=(script_path, user_id, user_folder, file_name, call.message)).start()
    elif file_name.endswith('.js'):
        threading.Thread(target=run_js_script,
                         args=(script_path, user_id, user_folder, file_name, call.message)).start()
    else:
        bot.send_message(call.message.chat.id, "❌ 𝐔𝐧𝐬𝐮𝐩𝐩𝐨𝐫𝐭𝐞𝐝 𝐭𝐲𝐩𝐞!")

def stop_user_script(call, file_name):
    """Stop a running script"""
    user_id = call.from_user.id
    script_key = f"{user_id}_{file_name}"
    if script_key not in bot_scripts:
        bot.answer_callback_query(call.id, "❌ 𝐒𝐜𝐫𝐢𝐩𝐭 𝐧𝐨𝐭 𝐫𝐮𝐧𝐧𝐢𝐧𝐠!")
        return
    bot.answer_callback_query(call.id, "🛑 𝐒𝐭𝐨𝐩𝐩𝐢𝐧𝐠...")
    stop_text = f"""
╔══════════════════════════════════════╗
║       🛑 <b>EXE CODEX: STOPPING</b> 🛑     ║
╠══════════════════════════════════════╣
║
║  📄 <code>{file_name[:25]}</code>
║  ⏳ 𝐏𝐥𝐞𝐚𝐬𝐞 𝐰𝐚𝐢𝐭...
║
╚══════════════════════════════════════╝
"""
    try:
        bot.edit_message_text(stop_text, call.message.chat.id, call.message.message_id, parse_mode='HTML')
    except:
        pass
    script_info = bot_scripts.get(script_key)
    if script_info:
        kill_process_tree(script_info)
        cleanup_script(script_key)
        time.sleep(1)
        success_text = f"""
╔══════════════════════════════════════╗
║       ✅ <b>EXE CODEX: STOPPED</b> ✅      ║
╠══════════════════════════════════════╣
║
║  📄 <code>{file_name[:25]}</code>
║  ✅ 𝐒𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥𝐥𝐲 𝐬𝐭𝐨𝐩𝐩𝐞𝐝!
║
╚══════════════════════════════════════╝
"""
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("▶️ 𝐑𝐮𝐧 𝐀𝐠𝐚𝐢𝐧", callback_data=f"run_{file_name}"),
            types.InlineKeyboardButton("🔙 𝐁𝐚𝐜𝐤", callback_data="back_to_files")
        )
        try:
            bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=markup)
        except:
            bot.send_message(call.message.chat.id, success_text, parse_mode='HTML', reply_markup=markup)
        log_action(user_id, "SCRIPT_STOP", f"Stopped {file_name}")

def delete_user_file(call, file_name):
    """Confirm file deletion"""
    user_id = call.from_user.id
    if is_bot_running(user_id, file_name):
        bot.answer_callback_query(call.id, "⚠️ 𝐒𝐭𝐨𝐩 𝐭𝐡𝐞 𝐬𝐜𝐫𝐢𝐩𝐭 𝐟𝐢𝐫𝐬𝐭!")
        return
    confirm_text = f"""
╔══════════════════════════════════════╗
║      ⚠️ <b>EXE CODEX: DELETE?</b> ⚠️      ║
╠══════════════════════════════════════╣
║
║  𝐀𝐫𝐞 𝐲𝐨𝐮 𝐬𝐮𝐫𝐞?
║  📄 <code>{file_name[:25]}</code>
║
║  ⚠️ 𝐓𝐡𝐢𝐬 𝐜𝐚𝐧𝐧𝐨𝐭 𝐛𝐞 𝐮𝐧𝐝𝐨𝐧𝐞!
║
╚══════════════════════════════════════╝
"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ 𝐘𝐞𝐬, 𝐃𝐞𝐥𝐞𝐭𝐞", callback_data=f"confirm_delete_{file_name}"),
        types.InlineKeyboardButton("❌ 𝐍𝐨", callback_data=f"cancel_delete_{file_name}")
    )
    try:
        bot.edit_message_text(confirm_text, call.message.chat.id, call.message.message_id,
                              parse_mode='HTML', reply_markup=markup)
    except:
        pass
    bot.answer_callback_query(call.id)

def confirm_delete_file(call, file_name):
    """Actually delete the file"""
    user_id = call.from_user.id
    user_folder = get_user_folder(user_id)
    file_path = os.path.join(user_folder, file_name)
    delete_text = f"""
╔══════════════════════════════════════╗
║       🗑️ <b>EXE CODEX: DELETING</b> 🗑️     ║
╠══════════════════════════════════════╣
║
║  📄 <code>{file_name[:25]}</code>
║  ⏳ 𝐏𝐥𝐞𝐚𝐬𝐞 𝐰𝐚𝐢𝐭...
║
╚══════════════════════════════════════╝
"""
    try:
        bot.edit_message_text(delete_text, call.message.chat.id, call.message.message_id, parse_mode='HTML')
    except:
        pass
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            if user_id in user_files:
                user_files[user_id] = [(n, t) for n, t in user_files[user_id] if n != file_name]
            remove_user_file_db(user_id, file_name)
            time.sleep(1)
            success_text = f"""
╔══════════════════════════════════════╗
║       ✅ <b>EXE CODEX: DELETED</b> ✅       ║
╠══════════════════════════════════════╣
║
║  📄 <code>{file_name[:25]}</code>
║  ✅ 𝐒𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥𝐥𝐲 𝐝𝐞𝐥𝐞𝐭𝐞𝐝!
║
╚══════════════════════════════════════╝
"""
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📂 𝐁𝐚𝐜𝐤 𝐭𝐨 𝐅𝐢𝐥𝐞𝐬", callback_data="back_to_files"))
            try:
                bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id,
                                      parse_mode='HTML', reply_markup=markup)
            except:
                bot.send_message(call.message.chat.id, success_text, parse_mode='HTML', reply_markup=markup)
            bot.answer_callback_query(call.id, "✅ 𝐃𝐞𝐥𝐞𝐭𝐞𝐝!")
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ 𝐄𝐫𝐫𝐨𝐫: {str(e)[:30]}")

def download_user_file(call, file_name):
    """Send file to user"""
    user_id = call.from_user.id
    user_folder = get_user_folder(user_id)
    file_path = os.path.join(user_folder, file_name)
    if not os.path.exists(file_path):
        bot.answer_callback_query(call.id, "❌ 𝐅𝐢𝐥𝐞 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝!")
        return
    bot.answer_callback_query(call.id, "📥 𝐒𝐞𝐧𝐝𝐢𝐧𝐠...")
    try:
        with open(file_path, 'rb') as f:
            bot.send_document(call.message.chat.id, f, caption=f"📄 {file_name}")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ 𝐄𝐫𝐫𝐨𝐫: {str(e)[:100]}")

def show_script_logs(call, file_name):
    """Show logs for a script"""
    user_id = call.from_user.id
    script_key = f"{user_id}_{file_name}"
    log_path = os.path.join(LOGS_DIR, f"{script_key}.log")
    if not os.path.exists(log_path):
        bot.answer_callback_query(call.id, "📋 𝐍𝐨 𝐥𝐨𝐠𝐬")
        return
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            logs = f.read()[-2000:]
            if not logs.strip():
                logs = "𝐍𝐨 𝐨𝐮𝐭𝐩𝐮𝐭 𝐲𝐞𝐭..."
        log_text = f"""
╔══════════════════════════════════════╗
║       📋 <b>EXE CODEX: LOGS</b> 📋         ║
╠══════════════════════════════════════╣
║ 📄 <code>{file_name[:25]}</code>
╠══════════════════════════════════════╣
<code>{logs[:1500]}</code>
╚══════════════════════════════════════╝
"""
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 𝐑𝐞𝐟𝐫𝐞𝐬𝐡", callback_data=f"logs_{file_name}"),
            types.InlineKeyboardButton("🔙 𝐁𝐚𝐜𝐤", callback_data=f"file_{file_name}")
        )
        try:
            bot.edit_message_text(log_text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=markup)
        except telebot.apihelper.ApiTelegramException:
            bot.answer_callback_query(call.id, "📋 𝐋𝐨𝐠𝐬 𝐮𝐧𝐜𝐡𝐚𝐧𝐠𝐞𝐝")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ 𝐄𝐫𝐫𝐨𝐫: {str(e)[:30]}")
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ 𝐄𝐫𝐫𝐨𝐫: {str(e)[:30]}")

def restart_user_script(call, file_name):
    """Restart a script"""
    user_id = call.from_user.id
    script_key = f"{user_id}_{file_name}"
    if script_key in bot_scripts:
        script_info = bot_scripts.get(script_key)
        if script_info:
            kill_process_tree(script_info)
            cleanup_script(script_key)
            time.sleep(1)
    run_user_script(call, file_name)

def show_user_files_callback(call):
    """Show files via callback"""
    class FakeMessage:
        def __init__(self, call):
            self.chat = call.message.chat
            self.from_user = call.from_user
    show_user_files(FakeMessage(call))
    bot.answer_callback_query(call.id)

def stop_all_bots(call):
    """Stop all running bots (Admin only)"""
    user_id = call.from_user.id
    if user_id != OWNER_ID and user_id not in admin_ids:
        bot.answer_callback_query(call.id, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    bot.answer_callback_query(call.id, "🛑 𝐒𝐭𝐨𝐩𝐩𝐢𝐧𝐠 𝐚𝐥𝐥 EXE CODEX 𝐛𝐨𝐭𝐬...")
    stopped = 0
    for script_key in list(bot_scripts.keys()):
        try:
            script_info = bot_scripts[script_key]
            kill_process_tree(script_info)
            cleanup_script(script_key)
            stopped += 1
        except:
            pass
    bot.send_message(call.message.chat.id, f"✅ 𝐒𝐭𝐨𝐩𝐩𝐞𝐝 {stopped} 𝐛𝐨𝐭𝐬!")

def refresh_admin_panel(call):
    """Refresh admin panel stats"""
    user_id = call.from_user.id
    if user_id != OWNER_ID and user_id not in admin_ids:
        bot.answer_callback_query(call.id, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    class FakeMessage:
        def __init__(self, call):
            self.chat = call.message.chat
            self.from_user = call.from_user
    show_admin_panel(FakeMessage(call))
    bot.answer_callback_query(call.id, "🔄 𝐑𝐞𝐟𝐫𝐞𝐬𝐡𝐞𝐝!")

def show_full_stats(call):
    """Show full statistics"""
    bot.answer_callback_query(call.id)
    stats_command(call.message)

def show_admin_logs(call):
    """Show admin logs"""
    user_id = call.from_user.id
    if user_id != OWNER_ID and user_id not in admin_ids:
        bot.answer_callback_query(call.id, "❌ 𝐀𝐝𝐦𝐢𝐧 𝐨𝐧𝐥𝐲!")
        return
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute('SELECT user_id, action, details, timestamp FROM bot_logs ORDER BY id DESC LIMIT 20')
        logs = c.fetchall()
        conn.close()
        if logs:
            text = "📋 <b>EXE CODEX: RECENT LOGS</b>\n"
            for log in logs:
                text += f"👤 {log[0]} | {log[1]}\n{log[2][:30]}...\n🕐 {log[3][:16]}\n"
        else:
            text = "📋 𝐍𝐨 𝐥𝐨𝐠𝐬."
        bot.send_message(call.message.chat.id, text[:4000], parse_mode='HTML')
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ 𝐄𝐫𝐫𝐨𝐫: {str(e)[:30]}")

# --- Cleanup on Exit ---
def cleanup_on_exit():
    """Cleanup running processes on exit"""
    logger.info("𝐂𝐥𝐞𝐚𝐧𝐢𝐧𝐠 𝐮𝐩 EXE CODEX...")
    for script_key in list(bot_scripts.keys()):
        try:
            script_info = bot_scripts[script_key]
            kill_process_tree(script_info)
        except:
            pass
    logger.info("𝐂𝐥𝐞𝐚𝐧𝐮𝐩 𝐜𝐨𝐦𝐩𝐥𝐞𝐭𝐞.")
atexit.register(cleanup_on_exit)

# --- Main ---
def main():
    """Main function to run the bot"""
    logger.info("=" * 50)
    logger.info("🤖 𝐒𝐭𝐚𝐫𝐭𝐢𝐧𝐠 EXE CODEX 🦁 𝐁𝐨𝐭...")
    logger.info(f"📁 𝐁𝐚𝐬𝐞 𝐃𝐢𝐫: {BASE_DIR}")
    logger.info(f"📁 𝐔𝐩𝐥𝐨𝐚𝐝 𝐃𝐢𝐫: {UPLOAD_BOTS_DIR}")
    logger.info(f"💾 𝐃𝐚𝐭𝐚𝐛𝐚𝐬𝐞: {DATABASE_PATH}")
    logger.info("=" * 50)
    keep_alive()
    while True:
        try:
            logger.info("🚀 𝐒𝐭𝐚𝐫𝐭𝐢𝐧𝐠 𝐛𝐨𝐭 𝐩𝐨𝐥𝐥𝐢𝐧𝐠...")
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except requests.exceptions.ConnectionError:
            logger.error("𝐂𝐨𝐧𝐧𝐞𝐜𝐭𝐢𝐨𝐧 𝐞𝐫𝐫𝐨𝐫! 𝐑𝐞𝐭𝐫𝐲𝐢𝐧𝐠...")
            time.sleep(10)
        except requests.exceptions.ReadTimeout:
            logger.error("𝐑𝐞𝐚𝐝 𝐭𝐢𝐦𝐞𝐨𝐮𝐭! 𝐑𝐞𝐭𝐫𝐲𝐢𝐧𝐠...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"EXE CODEX 𝐞𝐫𝐫𝐨𝐫: {e}", exc_info=True)
            time.sleep(5)

if __name__ == "__main__":
    main()