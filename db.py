import sqlite3, hashlib, hmac
from contextlib import closing
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent / 'ecoagent.db'
STATES = ['Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chhattisgarh','Goa','Gujarat','Haryana','Himachal Pradesh','Jharkhand','Karnataka','Kerala','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Mizoram','Nagaland','Odisha','Punjab','Rajasthan','Sikkim','Tamil Nadu','Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal']
STATE_TARIFF = {'Gujarat':7.0,'Maharashtra':8.0,'Rajasthan':7.5,'Karnataka':7.0,'Tamil Nadu':6.5,'Delhi':8.0,'Bihar':6.5,'Uttar Pradesh':7.0,'West Bengal':7.0}
DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS = 'admin', 'admin123'

def _conn():
    conn=sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def _hash(password):
    return hashlib.sha256(str(password).encode()).hexdigest()

def init_db():
    with closing(_conn()) as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, state TEXT, role TEXT DEFAULT 'user', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, appliance TEXT, hours REAL, quantity INTEGER, watts REAL, kwh REAL, cost REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS summary(user_id INTEGER PRIMARY KEY, monthly_kwh REAL DEFAULT 0, monthly_cost REAL DEFAULT 0, yearly_kwh REAL DEFAULT 0, yearly_cost REAL DEFAULT 0, co2_kg REAL DEFAULT 0, score REAL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        ''')
        if not conn.execute('SELECT id FROM users WHERE username=?',(DEFAULT_ADMIN_USER,)).fetchone():
            conn.execute('INSERT INTO users(username,password_hash,state,role) VALUES(?,?,?,?)',(DEFAULT_ADMIN_USER,_hash(DEFAULT_ADMIN_PASS),'Gujarat','admin'))
        conn.commit()

def register_user(username,password,state):
    username=str(username).strip()
    if not username or not password: return False,'Username and password are required.'
    if len(password)<6: return False,'Password must contain at least 6 characters.'
    try:
        with closing(_conn()) as c:
            c.execute("INSERT INTO users(username,password_hash,state,role) VALUES(?,?,?,'user')",(username,_hash(password),state)); c.commit()
        return True,'Registration successful. You can now log in.'
    except sqlite3.IntegrityError: return False,'That username already exists.'

def authenticate(username,password):
    with closing(_conn()) as c:
        row=c.execute('SELECT id,username,password_hash,state,role,created_at FROM users WHERE username=?',(str(username).strip(),)).fetchone()
        if row and hmac.compare_digest(row['password_hash'],_hash(password)):
            result=dict(row); result.pop('password_hash',None); return result
    return None

def get_user_by_name(username):
    with closing(_conn()) as c:
        r=c.execute('SELECT id,username,state,role,created_at FROM users WHERE username=?',(username,)).fetchone()
        return dict(r) if r else None

def save_usage(user_id,appliance,hours,quantity,watts,kwh,cost):
    with closing(_conn()) as c:
        c.execute('INSERT INTO usage(user_id,appliance,hours,quantity,watts,kwh,cost) VALUES(?,?,?,?,?,?,?)',(user_id,appliance,hours,quantity,watts,kwh,cost)); c.commit()

def get_usage(user_id):
    with closing(_conn()) as c: return pd.read_sql_query('SELECT id,appliance,hours,quantity,watts,kwh,cost,created_at FROM usage WHERE user_id=? ORDER BY created_at DESC',(c),params=(user_id,))

def save_summary(user_id,monthly_kwh,monthly_cost,yearly_kwh,yearly_cost,co2_kg,score):
    with closing(_conn()) as c:
        c.execute('''INSERT INTO summary(user_id,monthly_kwh,monthly_cost,yearly_kwh,yearly_cost,co2_kg,score,updated_at) VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET monthly_kwh=excluded.monthly_kwh,monthly_cost=excluded.monthly_cost,yearly_kwh=excluded.yearly_kwh,yearly_cost=excluded.yearly_cost,co2_kg=excluded.co2_kg,score=excluded.score,updated_at=CURRENT_TIMESTAMP''',(user_id,monthly_kwh,monthly_cost,yearly_kwh,yearly_cost,co2_kg,score)); c.commit()

def get_summary(user_id):
    with closing(_conn()) as c:
        r=c.execute('SELECT * FROM summary WHERE user_id=?',(user_id,)).fetchone(); return dict(r) if r else None

def list_users():
    with closing(_conn()) as c: return pd.read_sql_query('SELECT id,username,state,role,created_at FROM users ORDER BY id',c)

def state_summary():
    with closing(_conn()) as c: return pd.read_sql_query("SELECT state,COUNT(*) AS users FROM users WHERE role='user' GROUP BY state ORDER BY users DESC",c)

def admin_summary():
    with closing(_conn()) as c:
        return pd.read_sql_query("SELECT u.username,u.state,COALESCE(s.monthly_kwh,0) monthly_kwh,COALESCE(s.monthly_cost,0) monthly_cost,COALESCE(s.yearly_kwh,0) yearly_kwh,COALESCE(s.yearly_cost,0) yearly_cost,COALESCE(s.co2_kg,0) co2_kg FROM users u LEFT JOIN summary s ON u.id=s.user_id WHERE u.role='user' ORDER BY monthly_kwh DESC",c)

def delete_user(user_id):
    with closing(_conn()) as c: c.execute("DELETE FROM users WHERE id=? AND role!='admin'",(int(user_id),)); c.commit()
