# oring_db_helpers.py
from db import get_conn_cursor
from collections import defaultdict

def get_orings_data_from_db():
    """
    Returns nested dict identical shape to your previous get_orings_data():
    { model: { stage: [ {subtask, required_orings, sample_image, description, class, class_index, model_yolo}, ... ] } }
    """
    orings_data = {}
    sql = """
        SELECT model, subtask, required_orings, stage, description, sample_image,
               class_to_find, class_index, model_yolo
        FROM ipv_ai_templates
        ORDER BY model, stage, subtask
    """
    with get_conn_cursor() as (conn, cur):
        cur.execute(sql)
        rows = cur.fetchall()

    for r in rows:
        model = r['model']
        stage = r['stage']
        if model not in orings_data:
            orings_data[model] = {}
        if stage not in orings_data[model]:
            orings_data[model][stage] = []
        orings_data[model][stage].append({
            'subtask': int(r['subtask']) if r['subtask'] is not None else None,
            'required_orings': r['required_orings'],
            'sample_image': r['sample_image'],
            'description': r['description'],
            'class': r['class_to_find'],
            'class_index': r['class_index'],
            'model_yolo': r['model_yolo']
        })
    return orings_data


def read_logs_from_db(limit=None):
    """
    Returns list of logs with keys matching previous code expectations:
    order_number, employee_id, model, stage, subtask, current_quantity, required_quantity, status, image_path, predicted_image_path, date_time
    If limit provided, limits number of rows returned (descending by created_at).
    """
    sql = """
        SELECT order_number, employee_id, model, stage, subtask,
               current_quantity, required_quantity, status, image_path, predicted_image_path,
               created_at
        FROM ipv_ai_logs
        ORDER BY created_at DESC
    """
    if limit:
        sql = sql.replace("ORDER BY created_at DESC", "ORDER BY created_at DESC LIMIT %s")
        params = (limit,)
    else:
        params = ()

    with get_conn_cursor() as (conn, cur):
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        rows = cur.fetchall()

    # normalize to list of dicts with date_time string like before
    logs = []
    for r in rows:
        logs.append({
            'order_number': r['order_number'],
            'employee_id': r['employee_id'],
            'model': r['model'],
            'stage': r['stage'],
            'subtask': r['subtask'],
            'current_quantity': r['current_quantity'],
            'required_quantity': r['required_quantity'],
            'status': r['status'],
            'image_path': r['image_path'],
            'predicted_image_path': r['predicted_image_path'],
            'date_time': r['created_at'].strftime('%Y-%m-%d %H:%M:%S') if r['created_at'] else None
        })
    return logs


def get_required_quantity_from_db(model_name, subtask, stage):
    """
    Returns required_orings (int) for this model/stage/subtask or None if not found.
    """
    sql = """
        SELECT required_orings
        FROM ipv_ai_templates
        WHERE model = %s AND stage = %s AND subtask = %s
        LIMIT 1
    """
    with get_conn_cursor() as (conn, cur):
        cur.execute(sql, (model_name, stage, subtask))
        row = cur.fetchone()
    return row['required_orings'] if row else None


def get_all_required_subtasks_from_db(stage, model_name):
    """
    Returns list of subtasks for model+stage (ordered) — similar to previous get_all_required_subtasks
    """
    sql = """
        SELECT subtask
        FROM ipv_ai_templates
        WHERE model = %s AND stage = %s
        ORDER BY subtask
    """
    with get_conn_cursor() as (conn, cur):
        cur.execute(sql, (model_name, stage))
        rows = cur.fetchall()
    return [r['subtask'] for r in rows]


def insert_log_db(order_number, employee_id, model, stage, subtask,
                  current_quantity, required_quantity, status,
                  image_path=None, predicted_image_path=None):
    """
    Insert a log row into ipv_ai_logs. Returns inserted id.
    """
    sql = """
        INSERT INTO ipv_ai_logs
            (order_number, employee_id, model, stage, subtask,
             current_quantity, required_quantity, status, image_path, predicted_image_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, created_at
    """
    params = (
        order_number, employee_id, model, stage, subtask,
        current_quantity, required_quantity, status, image_path, predicted_image_path
    )
    with get_conn_cursor() as (conn, cur):
        cur.execute(sql, params)
        row = cur.fetchone()
    return row  # dict with id and created_at


def insert_predicted_image_record(blob_path, local_path=None):
    sql = """
        INSERT INTO ipv_ai_predicted_images (blob_path, local_path)
        VALUES (%s, %s)
        RETURNING id, uploaded_at
    """
    with get_conn_cursor() as (conn, cur):
        cur.execute(sql, (blob_path, local_path))
        row = cur.fetchone()
    return row


def is_stage_fully_completed(order_number, model, stage):
    with get_conn_cursor() as (conn, cur):

        # 1. required subtasks
        cur.execute("""
            SELECT subtask
            FROM ipv_ai_templates
            WHERE model = %s AND stage = %s
            ORDER BY subtask
        """, (model, stage))
        required = {r['subtask'] for r in cur.fetchall()}

        if not required:
            return False, [], []  # no template → treat as incomplete

        # 2. completed (latest PASS)
        cur.execute("""
            SELECT DISTINCT ON (subtask) subtask
            FROM ipv_ai_logs
            WHERE order_number = %s
              AND model = %s
              AND stage = %s
              AND status = 'pass'
            ORDER BY subtask, created_at DESC
        """, (order_number, model, stage))
        completed = {r['subtask'] for r in cur.fetchall()}

    pending = sorted(required - completed)
    return len(pending) == 0, sorted(required), sorted(completed)