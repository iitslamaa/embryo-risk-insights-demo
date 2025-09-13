import os, sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, abort
from dotenv import load_dotenv
from modules.scoring.pipeline import ScoringEngine
from modules.reports.pdf import generate_report_pdf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "demo.db")
CSV_PATH = os.path.join(DATA_DIR, "embryos.csv")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_db_conn(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        embryo_id TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        embryo_id TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        appt_time TEXT NOT NULL,
        notes TEXT
    )""")
    conn.commit(); conn.close()

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
API_TOKEN = os.getenv("DEMO_API_TOKEN", "demo123")

init_db()
engine = ScoringEngine(CSV_PATH)

def fetch_notes(embryo_id): 
    conn = get_db_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM notes WHERE embryo_id = ? ORDER BY created_at DESC", (embryo_id,))
    rows = cur.fetchall(); conn.close(); return rows

def fetch_appointments(embryo_id):
    conn = get_db_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM appointments WHERE embryo_id = ? ORDER BY appt_time DESC", (embryo_id,))
    rows = cur.fetchall(); conn.close(); return rows

@app.route("/")
def dashboard():
    summaries = sorted(engine.score_all(), key=lambda d: d["overall_score"], reverse=True)
    last_updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return render_template("dashboard.html", summaries=summaries, last_updated=last_updated)

@app.route("/embryos/<embryo_id>")
def embryo_detail(embryo_id):
    try:
        detail = engine.compute_detailed_scores(embryo_id)
    except KeyError:
        abort(404)
    notes = fetch_notes(embryo_id)
    appts = fetch_appointments(embryo_id)
    return render_template("embryo_detail.html", detail=detail, notes=notes, appts=appts)

@app.route("/embryos/<embryo_id>/notes", methods=["POST"])
def add_note(embryo_id):
    content = (request.form.get("content") or "").strip()
    if content:
        conn = get_db_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO notes (embryo_id, content, created_at) VALUES (?, ?, ?)",
                    (embryo_id, content, datetime.utcnow().isoformat()))
        conn.commit(); conn.close()
    return redirect(url_for("embryo_detail", embryo_id=embryo_id))

@app.route("/embryos/<embryo_id>/appointments", methods=["POST"])
def schedule_appt(embryo_id):
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    appt_time = (request.form.get("appt_time") or "").strip()
    notes = (request.form.get("notes") or "").strip() or None
    if name and email and appt_time:
        conn = get_db_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO appointments (embryo_id, name, email, appt_time, notes) VALUES (?, ?, ?, ?, ?)",
                    (embryo_id, name, email, appt_time, notes))
        conn.commit(); conn.close()
    return redirect(url_for("embryo_detail", embryo_id=embryo_id))

@app.route("/report/<embryo_id>.pdf")
def report_pdf(embryo_id):
    try:
        detail = engine.compute_detailed_scores(embryo_id)
    except KeyError:
        abort(404)
    path = generate_report_pdf(REPORTS_DIR, embryo_id, detail)
    return send_file(path, as_attachment=True, download_name=f"embryo_{embryo_id}_report.pdf")

def _check_token(req):
    token = req.headers.get("X-API-TOKEN") or req.args.get("token")
    return token == API_TOKEN

@app.route("/api/embryos")
def api_list():
    if not _check_token(request): return jsonify({"error":"unauthorized"}), 401
    return jsonify(engine.score_all())

@app.route("/api/embryos/<embryo_id>")
def api_detail(embryo_id):
    if not _check_token(request): return jsonify({"error":"unauthorized"}), 401
    try:
        detail = engine.compute_detailed_scores(embryo_id)
    except KeyError:
        return jsonify({"error":"not found"}), 404
    return jsonify(detail)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
