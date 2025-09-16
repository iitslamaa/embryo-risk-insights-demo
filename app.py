# app.py
import os, sqlite3
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for,
    send_file, jsonify, abort
)
from functools import wraps
from dotenv import load_dotenv

# --- project modules ---
from modules.scoring.pipeline import ScoringEngine  # your engine
# The IO helpers are optional: if you've created modules/scoring/io.py (Part C), these will work.
try:
    from modules.scoring.io import save_engine_state, load_engine_state
    _HAS_IO = True
except Exception:
    _HAS_IO = False

# ----------------------------
# Paths & basic setup
# ----------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
DB_PATH    = os.path.join(DATA_DIR, "demo.db")
CSV_PATH   = os.path.join(DATA_DIR, "embryos.csv")
REPORTS_DIR= os.path.join(BASE_DIR, "reports")
STATE_PATH = os.path.join(DATA_DIR, "weights.pkl")

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

# Accept either DEMO_API_TOKEN (your existing var) or API_TOKEN
API_TOKEN = os.getenv("DEMO_API_TOKEN") or os.getenv("API_TOKEN") or "demo123"

# ----------------------------
# DB helpers
# ----------------------------
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

init_db()

# ----------------------------
# Scoring engine
# ----------------------------
# Your existing constructor that reads the CSV internally
engine = ScoringEngine(CSV_PATH)

# If you added persistence (Part C) and a prior state exists, load it:
if _HAS_IO and Path(STATE_PATH).exists():
    try:
        state = load_engine_state(STATE_PATH)
        # Expect keys: condition_weights, monogenic_penalties, config
        if "condition_weights" in state:
            engine.condition_weights = state["condition_weights"]
        if "monogenic_penalties" in state:
            engine.monogenic_penalties = state["monogenic_penalties"]
        if "config" in state and hasattr(engine, "update_config"):
            engine.update_config(**state["config"])
        print(f"[engine] loaded state from {STATE_PATH}")
    except Exception as e:
        print(f"[engine] warning: could not load state: {e}")

# ----------------------------
# Token helpers
# ----------------------------
def require_token(f):
    """Accepts either:
       - Authorization: Bearer <token>
       - X-API-TOKEN: <token>
       - ?token=<token> (query)  (legacy)
    """
    @wraps(f)
    def _wrap(*args, **kwargs):
        # New: Authorization header
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
            if token == API_TOKEN:
                return f(*args, **kwargs)

        # Legacy headers/params you already used
        x_token = request.headers.get("X-API-TOKEN") or request.args.get("token")
        if x_token == API_TOKEN:
            return f(*args, **kwargs)

        return jsonify({"error": "unauthorized"}), 401
    return _wrap

def _check_token(req):
    # Accept Authorization: Bearer <token>, X-API-TOKEN header, or ?token= query
    auth = req.headers.get("Authorization", "")
    bearer = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else ""
    token = bearer or req.headers.get("X-API-TOKEN") or req.args.get("token")
    return token == API_TOKEN


# ----------------------------
# Pages
# ----------------------------
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
    notes = _fetch_notes(embryo_id)
    appts = _fetch_appointments(embryo_id)
    return render_template("embryo_detail.html", detail=detail, notes=notes, appts=appts)

# ----------------------------
# DB-backed actions
# ----------------------------
def _fetch_notes(embryo_id):
    conn = get_db_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM notes WHERE embryo_id = ? ORDER BY created_at DESC", (embryo_id,))
    rows = cur.fetchall(); conn.close(); return rows

def _fetch_appointments(embryo_id):
    conn = get_db_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM appointments WHERE embryo_id = ? ORDER BY appt_time DESC", (embryo_id,))
    rows = cur.fetchall(); conn.close(); return rows

@app.route("/embryos/<embryo_id>/notes", methods=["POST"])
def add_note(embryo_id):
    content = (request.form.get("content") or "").strip()
    if content:
        conn = get_db_conn(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO notes (embryo_id, content, created_at) VALUES (?, ?, ?)",
            (embryo_id, content, datetime.utcnow().isoformat())
        )
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
        cur.execute(
            "INSERT INTO appointments (embryo_id, name, email, appt_time, notes) VALUES (?, ?, ?, ?, ?)",
            (embryo_id, name, email, appt_time, notes)
        )
        conn.commit(); conn.close()
    return redirect(url_for("embryo_detail", embryo_id=embryo_id))

# ----------------------------
# Reporting
# ----------------------------
from modules.reports.pdf import generate_report_pdf

@app.route("/report/<embryo_id>.pdf")
def report_pdf(embryo_id):
    try:
        detail = engine.compute_detailed_scores(embryo_id)
    except KeyError:
        abort(404)
    path = generate_report_pdf(REPORTS_DIR, embryo_id, detail)
    return send_file(path, as_attachment=True, download_name=f"embryo_{embryo_id}_report.pdf")

# ----------------------------
# JSON API (existing)
# ----------------------------
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

# ----------------------------
# NEW: Config & Model state endpoints
# ----------------------------
@app.get("/api/config")
@require_token
def get_config():
    # Requires engine to expose .config with .seed / .scale
    cfg = getattr(engine, "config", None)
    if cfg is None:
        # Graceful fallback if pipeline wasn't upgraded yet
        return jsonify({"error": "config not supported by engine"}), 501
    return jsonify({"seed": getattr(cfg, "seed", None), "scale": getattr(cfg, "scale", None)})

@app.post("/api/config")
@require_token
def set_config():
    data = request.get_json(force=True, silent=True) or {}
    seed  = data.get("seed")
    scale = data.get("scale")

    # Validate
    if seed is not None:
        try: seed = int(seed)
        except Exception: return jsonify({"error": "seed must be int"}), 400
    if scale is not None:
        try: scale = float(scale)
        except Exception: return jsonify({"error": "scale must be float"}), 400

    if not hasattr(engine, "update_config"):
        return jsonify({"error": "engine cannot update config"}), 501

    engine.update_config(seed=seed, scale=scale)
    cfg = engine.config
    return jsonify({"ok": True, "config": {"seed": cfg.seed, "scale": cfg.scale}})

@app.post("/api/model/save")
@require_token
def save_model():
    if not _HAS_IO:
        return jsonify({"ok": False, "error": "IO helpers not available"}), 501
    try:
        save_engine_state(engine, STATE_PATH)
        return jsonify({"ok": True, "path": STATE_PATH})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/model/load")
@require_token
def load_model():
    if not _HAS_IO:
        return jsonify({"ok": False, "error": "IO helpers not available"}), 501
    try:
        state = load_engine_state(STATE_PATH)
        if "condition_weights" in state:
            engine.condition_weights = state["condition_weights"]
        if "monogenic_penalties" in state:
            engine.monogenic_penalties = state["monogenic_penalties"]
        if "config" in state and hasattr(engine, "update_config"):
            engine.update_config(**state["config"])
        return jsonify({"ok": True, "config": state.get("config", {})})
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "no saved state"}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ----------------------------
# Debug helper (optional)
# ----------------------------
@app.get("/_debug/routes")
def _routes():
    return jsonify(sorted([str(r) for r in app.url_map.iter_rules()]))

@app.get("/settings")
def settings():
    # passes the API token so the page JS can call the protected endpoints
    return render_template("settings.html", api_token=API_TOKEN)

@app.get("/compare")
def compare():
    # pass the token so the React app can call protected APIs
    return render_template("compare.html", api_token=API_TOKEN)


# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
