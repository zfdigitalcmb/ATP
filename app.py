# app.py (register orings_bp directly; show import error on /routes-import-error)
from flask import Flask, render_template, jsonify, request, Blueprint
from dotenv import load_dotenv
import os
import threading
import traceback
from blob_models import download_missing_models  # existing function; we call it from background
from db_time_tracking import get_conn_cursor_time_track
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from functools import lru_cache

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")

# --- simple in-memory download status ---
download_status = {
    "state": "not_started",
    "message": "",
    "started_at": None,
    "finished_at": None,
}

# -------------------- MODEL DOWNLOAD --------------------
def _download_worker():
    try:
        download_status["state"] = "running"
        download_status["message"] = "Download started."
        download_missing_models()
        download_status["state"] = "done"
        download_status["message"] = "All downloads finished."
    except Exception as e:
        download_status["state"] = "error"
        download_status["message"] = f"Error: {e}"
        traceback.print_exc()





@lru_cache(maxsize=1)
def get_app_version():
    try:
        for line in (Path(__file__).parent / "pyproject.toml").read_text().splitlines():
            line = line.strip()
            if line.startswith("version") and "=" in line:
                return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"

@app.route('/')
def index():
    version = get_app_version()
    return render_template('apps.html',version=version)

@app.route('/download-models', methods=['GET'])
def download_models_page():
    return render_template('download_models.html')

@app.route('/download-models/start', methods=['POST'])
def start_download():
    if download_status["state"] == "running":
        return jsonify({"ok": False, "message": "Download already running"}), 400

    download_status.update({"state": "not_started", "message": ""})
    t = threading.Thread(target=_download_worker, daemon=True)
    t.start()

    models_dir = os.path.join(os.getcwd(), "models")
    existing_files = os.listdir(models_dir) if os.path.isdir(models_dir) else []
    msg = f"Download started. {len(existing_files)} model files currently available."
    return jsonify({"ok": True, "message": msg, "files": existing_files})


@app.route('/download-status', methods=['GET'])
def get_download_status():
    models_dir = os.path.join(os.getcwd(), "models")
    existing_files = os.listdir(models_dir) if os.path.isdir(models_dir) else []
    status = dict(download_status)
    status["available_files"] = existing_files
    status["available_count"] = len(existing_files)
    status["message"] = f"{status.get('message', '')} ({len(existing_files)} file(s) available)"
    return jsonify(status)


@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

# -------------------- BLUEPRINT REGISTRATION --------------------
# If import fails, write traceback to file and register a small debug route so /ipv doesn't 404
IMPORT_TRACE_PATH = "/home/LogFiles/routes_import_error.log"  # Kudu-friendly path

def _write_import_traceback(tb_text: str):
    try:
        os.makedirs(os.path.dirname(IMPORT_TRACE_PATH), exist_ok=True)
        with open(IMPORT_TRACE_PATH, "w", encoding="utf-8") as fh:
            fh.write(tb_text)
    except Exception:
        # swallow; best-effort only
        print("Failed to write import traceback to file.", flush=True)

try:
    # Try to import and register the real blueprint which contains all your routes
    from routes.orings import orings_bp
    app.register_blueprint(orings_bp)  # registers every route defined inside orings_bp
    from routes.admin_ipv import admin_ipv_bp
    app.register_blueprint(admin_ipv_bp)
    from routes.admin_auth_ipv import admin_auth_bp
    app.register_blueprint(admin_auth_bp)
    from routes.pa_plates_bolts import plc_boltsai_bp
    app.register_blueprint(plc_boltsai_bp)
    from routes.iot_ipv import iot_ipv_app
    app.register_blueprint(iot_ipv_app)
    from routes.washers import washers_bp
    app.register_blueprint(washers_bp)


    print("✅ Registered blueprint", flush=True)
except Exception as exc:
    tb = traceback.format_exc()
    print("⚠️  Failed to import orings_bp — registering debug routes. Traceback written to:", IMPORT_TRACE_PATH, flush=True)
    print(tb, flush=True)
    _write_import_traceback(tb)

    
    fallback_bp = Blueprint("orings_fallback", __name__)

    @fallback_bp.route("/ipv", methods=["GET", "POST"])
    def ipv_fallback():
        # Friendly message if orings module couldn't be loaded
        return (
            "<h2>Orings blueprint not loaded</h2>"
            "<p>The <code>orings_bp</code> blueprint failed to import. "
            "Check the <code>/routes-import-error</code> page or application logs for details.</p>",
            200,
        )

    @fallback_bp.route("/routes-import-error", methods=["GET"])
    def show_import_error():
        # Try to show the saved traceback if present (useful in Azure/Kudu)
        if os.path.exists(IMPORT_TRACE_PATH):
            try:
                with open(IMPORT_TRACE_PATH, "r", encoding="utf-8") as fh:
                    tb_text = fh.read()
                # Show traceback in a <pre> for readability
                return "<h3>Blueprint import error (server)</h3><pre style='white-space: pre-wrap;'>" + tb_text + "</pre>", 200
            except Exception:
                pass
        # Fallback message
        return "<p>No traceback file available. Check application logs.</p>", 200

    app.register_blueprint(fallback_bp)
    print("✅ Registered fallback /ipv and /routes-import-error routes", flush=True)

@app.route('/ordernumbers/<model>', methods=['GET'])
def ordernumbers_for_model(model):
    """
    Return order numbers (JSON) for the given model_code created in the last 7 days.
    Example: GET /ordernumbers/ZM129
    """
    try:
        # Use non-dict cursor to get simple tuples (order_number, created_at)
        with get_conn_cursor_time_track(dict_cursor=False) as (conn, cur):
            sql = """
                SELECT o.order_number, o.created_at
                FROM orders o
                JOIN models m ON o.model_id = m.id
                WHERE lower(m.model_code) = lower(%s)
                  AND o.created_at >= (now() - interval '7 days')
                ORDER BY o.created_at DESC
            """
            cur.execute(sql, (model,))
            rows = cur.fetchall()

        order_numbers = [row[0] for row in rows]

        return jsonify({
            "model": model,
            "order_numbers": order_numbers,
            "count": len(order_numbers)
        }), 200

    except Exception as exc:
        app.logger.exception("Error fetching order numbers for model=%s", model)
        return jsonify({"error": "failed to fetch order numbers", "details": str(exc)}), 500

@app.route('/operators/<model>/<order_number>/<stage>', methods=['GET'])
def operators_for_order_stage(model, order_number, stage):
    """
    Return operator info for given model, order_number, and stage.
    Uses order_stage_operators (not andon_events) to get operator IDs.
    """
    try:
        with get_conn_cursor_time_track(dict_cursor=False) as (conn, cur):
            # 1) Find order id (ensure model matches)
            cur.execute("""
                SELECT o.id, o.model_id
                FROM orders o
                JOIN models m ON o.model_id = m.id
                WHERE lower(m.model_code) = lower(%s)
                  AND o.order_number = %s
                LIMIT 1
            """, (model, order_number))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "order not found for given model/order_number"}), 404

            order_id, model_id = row[0], row[1]

            # 2) Resolve stage -> stage_id (accept ID or name)
            try:
                stage_id = int(stage)
            except ValueError:
                cur.execute("SELECT id FROM stages WHERE lower(name) = lower(%s) LIMIT 1", (stage,))
                srow = cur.fetchone()
                if not srow:
                    return jsonify({"error": "stage not found"}), 404
                stage_id = srow[0]

            # 3) Fetch distinct operators from order_stage_operators (last 7 days optional)
            #    Join to users by comparing ids as text so it works if operator_id is text/int.
            cur.execute("""
                SELECT DISTINCT oso.operator_id,
                       u.full_name,
                       u.username
                FROM order_stage_operators oso
                LEFT JOIN users u ON u.id::text = oso.operator_id::text
                WHERE oso.order_id = %s
                  AND oso.stage_id = %s
                  -- optionally filter by recent assignments; comment out if not desired
                  AND (oso.assigned_at IS NULL OR oso.assigned_at >= (now() - interval '7 days'))
                ORDER BY u.full_name NULLS LAST
            """, (order_id, stage_id))
            ops_raw = cur.fetchall()
            ops = []
            for r in ops_raw:
                opid = int(r[0]) if r[0] is not None and str(r[0]).isdigit() else (r[0] if r[0] is not None else None)
                ops.append({
                    "id": opid,
                    "full_name": r[1] or "",
                    "username": r[2] or ""
                })

            # 4) Fetch latest assigned operator from order_stage_operators.
            #    Try ordering by assigned_at (if column exists), else fallback to id.
            latest = None
            try:
                cur.execute("""
                    SELECT oso.operator_id, u.full_name, u.username, oso.assigned_at
                    FROM order_stage_operators oso
                    LEFT JOIN users u ON u.id::text = oso.operator_id::text
                    WHERE oso.order_id = %s AND oso.stage_id = %s
                    ORDER BY oso.assigned_at DESC
                    LIMIT 1
                """, (order_id, stage_id))
                last = cur.fetchone()
            except Exception:
                # fallback if assigned_at column does not exist
                cur.execute("""
                    SELECT oso.operator_id, u.full_name, u.username, NULL AS assigned_at
                    FROM order_stage_operators oso
                    LEFT JOIN users u ON u.id::text = oso.operator_id::text
                    WHERE oso.order_id = %s AND oso.stage_id = %s
                    ORDER BY oso.id DESC
                    LIMIT 1
                """, (order_id, stage_id))
                last = cur.fetchone()

            if last:
                opid, fullname, username, assigned_at = last
                latest = {
                    "id": int(opid) if opid is not None and str(opid).isdigit() else (opid if opid is not None else None),
                    "full_name": fullname or "",
                    "username": username or "",
                    "event_type": "assigned",              # semantic replacement for andon 'event_type'
                    "ts": assigned_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(assigned_at, "strftime") else (str(assigned_at) if assigned_at is not None else None)
                }

        return jsonify({
            "model": model,
            "order_number": order_number,
            "stage": stage,
            "latest_operator": latest,
            "operators": ops,
            "count": len(ops)
        }), 200

    except Exception as exc:
        app.logger.exception("Error fetching operators for model=%s order=%s stage=%s", model, order_number, stage)
        return jsonify({"error": "failed to fetch operators", "details": str(exc)}), 500



# -------------------- MAIN --------------------
if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True, port=8000)
