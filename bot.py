import os, sqlite3, zipfile, subprocess, signal, shutil, psutil, time, datetime, threading
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit

running_procs = {}

socketio = SocketIO()

def get_db():
    db_path = os.path.join(os.getcwd(), 'storage/nehost.db')
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists('storage'): os.makedirs('storage')
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fname TEXT, lname TEXT, username TEXT, email TEXT, password TEXT, pfp TEXT DEFAULT 'default.png',
        role TEXT DEFAULT 'free', 
        status TEXT DEFAULT 'active',
        server_limit INTEGER DEFAULT 1,
        notifications TEXT DEFAULT ''
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS servers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, name TEXT, folder TEXT, 
        status TEXT, startup TEXT, pid INTEGER,
        server_status TEXT DEFAULT 'active'
    )''')
    
    # Safe Update DB Columns
    try: db.execute('ALTER TABLE servers ADD COLUMN auto_restart INTEGER DEFAULT 0')
    except: pass
    try: db.execute('ALTER TABLE servers ADD COLUMN req_file TEXT DEFAULT "requirements.txt"')
    except: pass
    try: db.execute('ALTER TABLE servers ADD COLUMN timed_restart TEXT DEFAULT "never"')
    except: pass
    try: db.execute('ALTER TABLE servers ADD COLUMN next_restart_at INTEGER DEFAULT 0')
    except: pass
    try: db.execute('ALTER TABLE servers ADD COLUMN first_start INTEGER DEFAULT 0')
    except: pass

    db.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, subject TEXT, message TEXT, status TEXT DEFAULT 'open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS admin_settings (
        id INTEGER PRIMARY KEY, 
        username TEXT, password TEXT,
        popup_title TEXT, popup_msg TEXT, popup_img TEXT, show_popup INTEGER DEFAULT 0
    )''')
    
    new_admin_user = "exe"
    new_admin_pass = "1100" 
    if not db.execute('SELECT * FROM admin_settings WHERE id=1').fetchone():
        db.execute('INSERT INTO admin_settings (id, username, password) VALUES (1, ?, ?)', (new_admin_user, new_admin_pass))
    else:
        db.execute('UPDATE admin_settings SET username=?, password=? WHERE id=1', (new_admin_user, new_admin_pass))
    
    db.commit()
    db.close()

def srv_restart_logic(folder):
    db = get_db()
    srv = db.execute('SELECT startup, next_restart_at, timed_restart, pid, first_start FROM servers WHERE folder=?', (folder,)).fetchone()
    if not srv: db.close(); return

    old_pid = srv['pid']
    if folder in running_procs or (old_pid and psutil.pid_exists(old_pid)):
        try: os.killpg(os.getpgid(running_procs[folder].pid if folder in running_procs else old_pid), signal.SIGKILL)
        except: pass
    
    startup_file = srv['startup'] if srv['startup'] else 'main.py'
    path_srv = os.path.join(os.getcwd(), 'storage/instances', folder)
    log_file_path = os.path.join(path_srv, 'console.log')
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with open(log_file_path, 'a') as f_log:
        f_log.write(f"\n[{now_str}] ⏰ TIMED AUTO-RESTART Triggered Successfully!\n")
    
    proc = subprocess.Popen(f"python3 {startup_file}", cwd=path_srv, shell=True, preexec_fn=os.setsid)
    running_procs[folder] = proc
    
    hours = 0
    if srv['timed_restart'] == '6h': hours = 6
    elif srv['timed_restart'] == '12h': hours = 12
    elif srv['timed_restart'] == '24h': hours = 24
    
    next_time = int(time.time()) + (hours * 3600) if hours > 0 else 0
    fs_val = srv['first_start'] if srv['first_start'] > 0 else int(time.time())
    db.execute('UPDATE servers SET pid=?, next_restart_at=?, first_start=? WHERE folder=?', (proc.pid, next_time, fs_val, folder))
    db.commit(); db.close()

def run_restart_scheduler():
    while True:
        try:
            time.sleep(60)
            db = get_db(); now = int(time.time())
            rows = db.execute('SELECT folder, pid FROM servers WHERE timed_restart != "never" AND next_restart_at > 0 AND next_restart_at <= ?', (now,)).fetchall()
            db.close()
            for row in rows:
                folder, saved_pid = row['folder'], row['pid']
                online = False
                if saved_pid and psutil.pid_exists(saved_pid): online = True
                elif folder in running_procs and running_procs[folder].poll() is None: online = True
                if online: srv_restart_logic(folder)
        except Exception as e: print("Scheduler Error:", str(e))

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'nehost_ultra_pro_max_99'
    app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=30)
    app.config['BASE_STORAGE'] = os.path.join(os.getcwd(), 'storage/instances')
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'static/uploads')
    
    if not os.path.exists(app.config['BASE_STORAGE']): os.makedirs(app.config['BASE_STORAGE'])
    if not os.path.exists(app.config['UPLOAD_FOLDER']): os.makedirs(app.config['UPLOAD_FOLDER'])
        
    init_db()
    socketio.init_app(app)
    threading.Thread(target=run_restart_scheduler, daemon=True).start()

    def get_precise_uptime(start_timestamp):
        if not start_timestamp or start_timestamp == 0: return "Offline"
        diff = int(time.time() - start_timestamp)
        months, rem = divmod(diff, 2592000)
        days, rem = divmod(rem, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        parts = []
        if months > 0: parts.append(f"{months}mo")
        if days > 0: parts.append(f"{days}d")
        if hours > 0: parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)
    
    @app.route('/')
    def home(): return render_template('index.html')

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if 'user_id' in session: return redirect(url_for('dashboard'))
        if request.method == 'POST':
            fname, lname = request.form.get('fname'), request.form.get('lname')
            username, email = request.form.get('username'), request.form.get('email')
            pwd, cpwd = request.form.get('password'), request.form.get('confirm_password')
            pfp = request.files.get('pfp')
            if pwd != cpwd: return jsonify({'status': 'error', 'msg': 'Passwords do not match!'}), 400
            db = get_db()
            if db.execute('SELECT id FROM users WHERE email=? OR username=?', (email, username)).fetchone():
                db.close(); return jsonify({'status': 'error', 'msg': 'Email or Username taken!'}), 400
            pfp_name = 'default.png'
            if pfp:
                pfp_name = secure_filename(pfp.filename)
                pfp.save(os.path.join(app.config['UPLOAD_FOLDER'], pfp_name))
            db.execute('INSERT INTO users (fname, lname, username, email, password, pfp) VALUES (?,?,?,?,?,?)', (fname, lname, username, email, pwd, pfp_name))
            db.commit(); db.close()
            return jsonify({'status': 'success', 'url': url_for('login')})
        return render_template('web/signup.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if 'user_id' in session: return redirect(url_for('dashboard'))
        if request.method == 'POST':
            email, pwd = request.form.get('email'), request.form.get('password')
            db = get_db()
            user = db.execute('SELECT * FROM users WHERE (email=? OR username=?) AND password=?', (email, email, pwd)).fetchone()
            db.close()
            if user:
                if user['status'] == 'banned': return jsonify({'status': 'banned', 'msg': 'Suspended!'}), 403
                session.permanent = True; session['user_id'] = user['id']
                return jsonify({'status': 'success', 'url': url_for('dashboard')}), 200
            return jsonify({'status': 'error', 'msg': 'Invalid credentials!'}), 401
        return render_template('web/login.html')

    @app.route('/logout')
    def logout(): session.clear(); return redirect(url_for('login'))

    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session: return redirect(url_for('login'))
        db = get_db(); user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone(); db.close()
        return render_template('web/dashboard.html', user=user)

    @app.route('/profile/update', methods=['POST'])
    def update_profile():
        if 'user_id' not in session: return jsonify({'status': 'error'})
        uid, fname, lname, pwd = session['user_id'], request.form.get('fname'), request.form.get('lname'), request.form.get('password')
        db = get_db()
        if pwd: db.execute('UPDATE users SET fname=?, lname=?, password=? WHERE id=?', (fname, lname, pwd, uid))
        else: db.execute('UPDATE users SET fname=?, lname=? WHERE id=?', (fname, lname, uid))
        db.commit(); db.close(); return jsonify({'status': 'success'})

    @app.route('/api/announcement')
    def get_announcement():
        db = get_db(); conf = db.execute('SELECT popup_title, popup_msg, popup_img, show_popup FROM admin_settings WHERE id=1').fetchone(); db.close()
        return jsonify(dict(conf))

    # --- ADMIN ROUTES BLOCK ---
    @app.route('/exe-owner', methods=['GET', 'POST'])
    def admin_login():
        if request.method == 'POST':
            user, pwd = request.form.get('username'), request.form.get('password')
            db = get_db(); admin = db.execute('SELECT * FROM admin_settings WHERE username=? AND password=?', (user, pwd)).fetchone(); db.close()
            if admin:
                session['admin_logged'] = True; return redirect(url_for('admin_panel'))
        return render_template('web/admin_login.html')

    @app.route('/admin/panel')
    def admin_panel():
        if not session.get('admin_logged'): return redirect(url_for('admin_login'))
        return render_template('web/admin_panel.html')

    @app.route('/admin/stats')
    def admin_stats():
        if not session.get('admin_logged'): return jsonify({})
        db = get_db(); users = db.execute('SELECT * FROM users').fetchall(); user_list = []
        total_cpu, total_ram = psutil.cpu_percent(), psutil.virtual_memory().percent
        for u in users:
            srvs = db.execute('SELECT * FROM servers WHERE user_id=?', (u['id'],)).fetchall()
            active_srvs = sum(1 for s in srvs if (s['pid'] and psutil.pid_exists(s['pid'])) or (s['folder'] in running_procs and running_procs[s['folder']].poll() is None))
            user_list.append({'id': u['id'], 'fname': u['fname'], 'email': u['email'], 'srv_count': len(srvs), 'active_srvs': active_srvs, 'status': u['status'], 'role': u['role'], 'server_limit': u['server_limit']})
        db.close(); return jsonify({'users': user_list, 'sys_cpu': f"{total_cpu}%", 'sys_ram': f"{total_ram}%"})

    @app.route('/admin/user/update', methods=['POST'])
    def update_user():
        if not session.get('admin_logged'): return jsonify({'status':'error'})
        d = request.json; db = get_db(); db.execute('UPDATE users SET role=?, status=?, server_limit=? WHERE id=?', (d['role'], d['status'], d['limit'], d['user_id']))
        db.commit(); db.close(); return jsonify({'status': 'success'})

    @app.route('/admin/delete-user/<int:uid>', methods=['POST'])
    def delete_user(uid):
        if not session.get('admin_logged'): return jsonify({'status': 'error'})
        db = get_db(); srvs = db.execute('SELECT folder FROM servers WHERE user_id=?', (uid,)).fetchall()
        for s in srvs:
            path = os.path.join(app.config['BASE_STORAGE'], s['folder'])
            if os.path.exists(path): shutil.rmtree(path)
        db.execute('DELETE FROM servers WHERE user_id=?', (uid,)); db.execute('DELETE FROM users WHERE id=?', (uid,))
        db.commit(); db.close(); return jsonify({'status': 'deleted'})

    # --- SERVER & FILE MANAGEMENT ROUTES ---
    @app.route('/files/save/<folder>/<name>', methods=['POST'])
    def fsave(folder, name):
        sub_path = request.args.get('path', '')
        p = os.path.join(app.config['BASE_STORAGE'], folder, sub_path, name)
        try:
            with open(p, 'w', encoding='utf-8') as f: f.write(request.json.get('content'))
            db = get_db()
            srv = db.execute('SELECT auto_restart, pid, startup, req_file, timed_restart, first_start FROM servers WHERE folder=?', (folder,)).fetchone()
            if srv and srv['auto_restart'] == 1:
                old_pid = srv['pid']
                if folder in running_procs or (old_pid and psutil.pid_exists(old_pid)):
                    try: os.killpg(os.getpgid(running_procs[folder].pid if folder in running_procs else old_pid), signal.SIGKILL)
                    except: pass
                
                path_srv = os.path.join(app.config['BASE_STORAGE'], folder)
                startup_file = srv['startup']
                if not startup_file or not os.path.exists(os.path.join(path_srv, startup_file)):
                    for cand in ['main.py', 'bot.py', 'exe.py', 'app.py', 'index.py']:
                        if os.path.exists(os.path.join(path_srv, cand)): startup_file = cand; break
                if not startup_file: startup_file = 'main.py'
                
                req_file = srv['req_file'] if srv['req_file'] else 'requirements.txt'
                log_file_path = os.path.join(path_srv, 'console.log')
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                hours = 0
                if srv['timed_restart'] == '6h': hours = 6
                elif srv['timed_restart'] == '12h': hours = 12
                elif srv['timed_restart'] == '24h': hours = 24
                next_time = int(time.time()) + (hours * 3600) if hours > 0 else 0
                
                with open(log_file_path, 'a') as f_log:
                    if os.path.exists(os.path.join(path_srv, req_file)):
                        f_log.write(f"\n[{now_str}] 🔄 AUTO-RESTART: Installing {req_file}...\n")
                        cmd = f"pip install -r {req_file} && python3 {startup_file}"
                    else:
                        f_log.write(f"\n[{now_str}] 🔄 AUTO-RESTART: File Updated\n")
                        cmd = f"python3 {startup_file}"
                
                proc = subprocess.Popen(cmd, cwd=path_srv, shell=True, preexec_fn=os.setsid)
                running_procs[folder] = proc
                fs_val = srv['first_start'] if srv['first_start'] > 0 else int(time.time())
                db.execute('UPDATE servers SET startup=?, pid=?, next_restart_at=?, first_start=? WHERE folder=?', (startup_file, proc.pid, next_time, fs_val, folder))
                db.commit()
            db.close(); return jsonify({'status': 'saved'})
        except Exception as e: return jsonify({'status': 'error', 'msg': str(e)})

    @app.route('/server/settings/<folder>')
    def get_server_settings(folder):
        db = get_db(); s = db.execute('SELECT startup, auto_restart, req_file, timed_restart FROM servers WHERE folder=?', (folder,)).fetchone(); db.close()
        return jsonify(dict(s) if s else {'startup':'main.py', 'auto_restart':0, 'req_file':'requirements.txt', 'timed_restart':'never'})

    @app.route('/server/set-settings/<folder>', methods=['POST'])
    def save_server_settings(folder):
        d = request.json; db = get_db(); tr = d.get('timed_restart', 'never')
        hours = 0
        if tr == '6h': hours = 6
        elif tr == '12h': hours = 12
        elif tr == '24h': hours = 24
        next_time = int(time.time()) + (hours * 3600) if hours > 0 else 0
        db.execute('UPDATE servers SET startup=?, req_file=?, auto_restart=?, timed_restart=?, next_restart_at=? WHERE folder=?', (d.get('startup'), d.get('req_file'), d.get('auto_restart'), tr, next_time, folder))
        db.commit(); db.close(); return jsonify({'status': 'success'})

    @app.route('/server/action/<folder>/<act>', methods=['POST'])
    def server_action(folder, act):
        db = get_db()
        srv_data = db.execute('SELECT server_status, req_file, timed_restart, first_start, startup FROM servers WHERE folder=?', (folder,)).fetchone()
        if srv_data and srv_data['server_status'] == 'suspended': db.close(); return jsonify({'status': 'error', 'msg': 'Suspended!'})
        path = os.path.join(app.config['BASE_STORAGE'], folder); log_file_path = os.path.join(path, 'console.log'); now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if act in ['start', 'restart']:
            row = db.execute('SELECT pid FROM servers WHERE folder=?', (folder,)).fetchone()
            if row and (folder in running_procs or (row['pid'] and psutil.pid_exists(row['pid']))):
                try: os.killpg(os.getpgid(running_procs[folder].pid if folder in running_procs else row['pid']), signal.SIGKILL)
                except: pass
            
            # AUTO STARTUP FILE DETECTOR LOGIC
            startup_file = srv_data['startup']
            if not startup_file or not os.path.exists(os.path.join(path, startup_file)):
                for cand in ['main.py', 'bot.py', 'exe.py', 'app.py', 'index.py']:
                    if os.path.exists(os.path.join(path, cand)): startup_file = cand; break
            if not startup_file: startup_file = 'main.py'

            req_file = srv_data['req_file'] if srv_data['req_file'] else 'requirements.txt'
            hours = 0
            if srv_data['timed_restart'] == '6h': hours = 6
            elif srv_data['timed_restart'] == '12h': hours = 12
            elif srv_data['timed_restart'] == '24h': hours = 24
            next_time = int(time.time()) + (hours * 3600) if hours > 0 else 0
            
            with open(log_file_path, 'a') as f_log:
                if os.path.exists(os.path.join(path, req_file)):
                    f_log.write(f"\n[{now_str}] 🚀 Auto-Installing & Starting...\n")
                    cmd = f"pip install -r {req_file} && python3 {startup_file}"
                else:
                    f_log.write(f"\n[{now_str}] 🚀 Instance Started\n")
                    cmd = f"python3 {startup_file}"
            
            proc = subprocess.Popen(cmd, cwd=path, shell=True, preexec_fn=os.setsid)
            running_procs[folder] = proc
            fs_val = srv_data['first_start'] if srv_data['first_start'] > 0 else int(time.time())
            db.execute('UPDATE servers SET startup=?, pid=?, next_restart_at=?, first_start=? WHERE folder=?', (startup_file, proc.pid, next_time, fs_val, folder))
            db.commit(); db.close(); return jsonify({'status': 'started'})
        elif act == 'stop':
            row = db.execute('SELECT pid FROM servers WHERE folder=?', (folder,)).fetchone()
            try: os.killpg(os.getpgid(running_procs[folder].pid if folder in running_procs else row['pid']), signal.SIGKILL)
            except: pass
            if folder in running_procs: del running_procs[folder]
            db.execute('UPDATE servers SET pid=NULL, next_restart_at=0, first_start=0 WHERE folder=?', (folder,))
            db.commit(); db.close()
            with open(log_file_path, 'a') as f: f.write(f"\n[{now_str}] 🛑 Stopped\n")
            return jsonify({'status': 'stopped'})
        db.close(); return jsonify({'status': 'ok'})

    @app.route('/files/list/<folder>')
    def flist(folder):
        sub_path = request.args.get('path', '')
        full_path = os.path.normpath(os.path.join(app.config['BASE_STORAGE'], folder, sub_path))
        if not full_path.startswith(app.config['BASE_STORAGE']) or not os.path.exists(full_path): return jsonify([])
        return jsonify([{'name': f, 'is_dir': os.path.isdir(os.path.join(full_path, f)), 'is_zip': f.lower().endswith('.zip'), 'rel_path': os.path.join(sub_path, f)} for f in sorted(os.listdir(full_path)) if f != 'console.log'])

    @app.route('/files/content/<folder>/<name>')
    def fcontent(folder, name):
        try:
            with open(os.path.join(app.config['BASE_STORAGE'], folder, request.args.get('path', ''), name), 'r', encoding='utf-8', errors='ignore') as f: return jsonify({'content': f.read()})
        except: return jsonify({'content': 'Error'})

    @app.route('/files/delete-bulk/<folder>', methods=['POST'])
    def delete_bulk(folder):
        base = os.path.join(app.config['BASE_STORAGE'], folder, request.json.get('path', ''))
        for name in request.json.get('names', []):
            p = os.path.join(base, name); 
            if name != 'console.log':
                try: shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
                except: pass
        return jsonify({"status": "ok"})

    @app.route('/files/create-file/<folder>', methods=['POST'])
    def create_file(folder):
        with open(os.path.join(app.config['BASE_STORAGE'], folder, request.json.get('path', ''), secure_filename(request.json.get('name'))), 'w') as f: f.write("")
        return jsonify({'status': 'success'})

    @app.route('/files/create-folder/<folder>', methods=['POST'])
    def create_folder(folder):
        os.makedirs(os.path.join(app.config['BASE_STORAGE'], folder, request.json.get('path', ''), secure_filename(request.json.get('name'))), exist_ok=True); return jsonify({'status': 'success'})

    @app.route('/files/upload/<folder>', methods=['POST'])
    def upload_file(folder):
        dest = os.path.join(app.config['BASE_STORAGE'], folder, request.form.get('path', ''))
        os.makedirs(dest, exist_ok=True); request.files['file'].save(os.path.join(dest, secure_filename(request.files['file'].filename))); return jsonify({'status': 'success'})

    @app.route('/files/rename/<folder>', methods=['POST'])
    def rename_file(folder):
        base = os.path.join(app.config['BASE_STORAGE'], folder, request.json.get('path', ''))
        os.rename(os.path.join(base, request.json['old']), os.path.join(base, request.json['new'])); return jsonify({'status': 'success'})

    @app.route('/files/unzip/<folder>', methods=['POST'])
    def unzip_file(folder):
        base = os.path.join(app.config['BASE_STORAGE'], folder, request.json.get('path', ''))
        zip_path = os.path.join(base, request.json.get('name'))
        if os.path.exists(zip_path) and zipfile.is_zipfile(zip_path):
            with zipfile.ZipFile(zip_path, 'r') as z: z.extractall(base)
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'msg': 'Invalid zip'})

    @app.route('/server/log/<folder>')
    def server_log(folder):
        path = os.path.join(app.config['BASE_STORAGE'], folder, 'console.log')
        if os.path.exists(path):
            with open(path, 'r') as f: return jsonify({'log': f.read()[-5000:]})
        return jsonify({'log': 'Waiting for logs...'})

    @app.route('/servers')
    def list_servers():
        if 'user_id' not in session: return jsonify({'servers': []})
        db = get_db(); rows = db.execute('SELECT * FROM servers WHERE user_id=?', (session['user_id'],)).fetchall(); db.close(); srvs = []
        for r in rows:
            f, saved_pid = r['folder'], r['pid']
            online = True if (saved_pid and psutil.pid_exists(saved_pid)) or (f in running_procs and running_procs[f].poll() is None) else False
            uptime = get_precise_uptime(r['first_start']) if online and r['first_start'] > 0 else ("Online" if online else "Offline")
            cpu, ram = "0%", "0MB"
            if online:
                try:
                    process = psutil.Process(running_procs[f].pid if f in running_procs else saved_pid)
                    cpu, ram = f"{process.cpu_percent(interval=None)}%", f"{process.memory_info().rss / (1024 * 1024):.1f}MB"
                except: pass
            srvs.append({'name': r['name'], 'folder': f, 'online': online, 'startup': r['startup'], 'uptime': uptime, 'cpu': cpu, 'ram': ram, 'status': r['server_status']})
        return jsonify({'servers': srvs})

    @app.route('/add', methods=['POST'])
    def add_srv():
        if 'user_id' not in session: return jsonify({'status': 'error'})
        db = get_db()
        user = db.execute('SELECT server_limit FROM users WHERE id=?', (session['user_id'],)).fetchone()
        count = db.execute('SELECT COUNT(*) as count FROM servers WHERE user_id=?', (session['user_id'],)).fetchone()['count']
        if count >= user['server_limit']: 
            db.close(); return jsonify({'status': 'error', 'msg': f"Limit Reached! Max: {user['server_limit']}"})
        name = request.json.get('name'); folder = secure_filename(name).lower() + "_" + str(int(time.time()))
        db.execute('INSERT INTO servers (user_id, name, folder, status, startup) VALUES (?,?,?,?,?)', (session['user_id'], name, folder, 'Offline', ''))
        db.commit(); db.close(); os.makedirs(os.path.join(app.config['BASE_STORAGE'], folder), exist_ok=True)
        return jsonify({'status': 'success'})

    return app

app = create_app()

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=3022, debug=True)
