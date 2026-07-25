# Runs developer script support for collect syslogs.
import os, json, time, platform, sqlite3, hashlib, threading
from datetime import datetime, UTC
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Windows event log support
if platform.system() == "Windows":
    import win32evtlog

BASE_LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(BASE_LOG_DIR, exist_ok=True)
DB_FILE = os.path.join(BASE_LOG_DIR, "system_logs.db")

db_lock = threading.Lock()

def utc_timestamp():
    return datetime.now(UTC).isoformat()

def row_hash(*args):
    h = hashlib.sha256()
    for a in args:
        h.update(str(a).encode("utf-8"))
    return h.hexdigest()

def export_log_txt(source, log_type, timestamp, summary, raw):
    """Write logs to /logs/<source>_<type>.txt"""
    path = os.path.join(BASE_LOG_DIR, f"{source}_{log_type}.txt")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {summary}\n{raw}\n{'-'*60}\n")

def export_log_json(source, log_type, timestamp, summary, raw):
    """Write logs in pretty JSON format to /logs/<source>_<type>.jsonl"""
    log_entry = {
        "timestamp": timestamp,
        "source": source,
        "event_type": log_type,
        "summary": summary,
        "raw": raw.strip(),
    }
    path = os.path.join(BASE_LOG_DIR, f"{source}_{log_type}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, indent=2, ensure_ascii=False) + "\n")

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        source TEXT,
        log_type TEXT,
        summary TEXT,
        raw TEXT,
        hash TEXT UNIQUE
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS fileops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        event_type TEXT,
        path TEXT,
        is_dir INTEGER,
        src_path TEXT,
        summary TEXT,
        hash TEXT UNIQUE
    )""")
    conn.commit()
    return conn

def store_log(conn, source, log_type, summary, raw):
    ts = utc_timestamp()
    h = row_hash(ts, source, log_type, summary)
    with db_lock:
        cur = conn.cursor()
        cur.execute("SELECT id FROM logs WHERE hash=?", (h,))
        if cur.fetchone():
            return
        cur.execute("INSERT INTO logs (timestamp, source, log_type, summary, raw, hash) VALUES (?, ?, ?, ?, ?, ?)",
                    (ts, source, log_type, summary, raw, h))
        conn.commit()
    export_log_txt(source, log_type, ts, summary, raw)
    export_log_json(source, log_type, ts, summary, raw)

def store_fileop(conn, event_type, path, is_dir, src_path=None):
    ts = utc_timestamp()
    summary = f"{event_type.upper()} {'directory' if is_dir else 'file'}: {path}"
    h = row_hash(ts, event_type, path, src_path)
    with db_lock:
        cur = conn.cursor()
        cur.execute("SELECT id FROM fileops WHERE hash=?", (h,))
        if cur.fetchone():
            return
        cur.execute("INSERT INTO fileops (timestamp, event_type, path, is_dir, src_path, summary, hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ts, event_type, path, int(is_dir), src_path or "", summary, h))
        conn.commit()
    export_log_txt("fileops", event_type, ts, summary, "")
    export_log_json("fileops", event_type, ts, summary, "")

class FileActivityHandler(FileSystemEventHandler):
    def __init__(self, conn):
        self.conn = conn

    def on_created(self, event):
        store_fileop(self.conn, "created", event.src_path, event.is_directory)

    def on_modified(self, event):
        store_fileop(self.conn, "modified", event.src_path, event.is_directory)

    def on_deleted(self, event):
        store_fileop(self.conn, "deleted", event.src_path, event.is_directory)

    def on_moved(self, event):
        store_fileop(self.conn, "moved", event.dest_path, event.is_directory, src_path=event.src_path)

def collect_windows_logs(conn):
    sources = ["System", "Application", "Security"]
    for source in sources:
        try:
            hand = win32evtlog.OpenEventLog(None, source)
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            events = win32evtlog.ReadEventLog(hand, flags, 0)
            for ev_obj in events:
                summary = f"{ev_obj.SourceName} - EventID:{ev_obj.EventID} - Type:{ev_obj.EventType}"
                raw = str(ev_obj.StringInserts)
                store_log(conn, source, "event", summary, raw)
        except Exception as e:
            print(f"[Windows collector] error reading {source}: {e}")

def collect_linux_logs(conn):
    log_files = ["/var/log/syslog", "/var/log/auth.log", "/var/log/messages"]
    for file_path in log_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.strip():
                            store_log(conn, os.path.basename(file_path), "syslog", line.strip(), line)
            except Exception as e:
                print(f"[Linux collector] error reading {file_path}: {e}")

def start_file_monitor(conn, path="."):
    handler = FileActivityHandler(conn)
    observer = Observer()
    observer.schedule(handler, path, recursive=True)
    observer.start()
    print(f"[+] File monitoring started on: {os.path.abspath(path)}")
    return observer

def start_system_collector(conn):
    def run():
        while True:
            if platform.system() == "Windows":
                collect_windows_logs(conn)
            else:
                collect_linux_logs(conn)
            time.sleep(60)
    t = threading.Thread(target=run, daemon=True)
    t.start()

def main():
    conn = init_db()
    print(f"[+] Database initialized at: {DB_FILE}")
    start_system_collector(conn)
    observer = start_file_monitor(conn, path=".")
    print("[+] Collecting system & file logs in real-time... Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        conn.close()
        print("[+] Stopped and database closed.")

if __name__ == "__main__":
    main()
