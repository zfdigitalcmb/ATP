# washer_db_helpers.py
# DB helper functions for washer detection.
# Mirrors oring_db_helpers.py — uses washer_ai_templates / washer_ai_logs tables.
from db import get_conn_cursor
from collections import defaultdict


def get_washers_data_from_db():
    """
    Returns nested dict identical in shape to get_orings_data_from_db():
    { model: { stage: [ {subtask, required_washers, sample_image, description,
                          class, class_index, model_yolo}, ... ] } }
    """
    washers_data = {}
    sql = """
        SELECT model, subtask, required_washers, stage, description, sample_image,
               class_to_find, class_index, model_yolo
        FROM washer_ai_templates
        ORDER BY model, stage, subtask
    """
    with get_conn_cursor() as (conn, cur):
        cur.execute(sql)
        rows = cur.fetchall()

    for r in rows:
        model = r['model']
        stage = r['stage']
        if model not in washers_data:
            washers_data[model] = {}
        if stage not in washers_data[model]:
            washers_data[model][stage] = []
        washers_data[model][stage].append({
            'subtask':          int(r['subtask']) if r['subtask'] is not None else None,
            'required_washers': r['required_washers'],
            'sample_image':     r['sample_image'],
            'description':      r['description'],
            'class':            r['class_to_find'],
            'class_index':      r['class_index'],
            'model_yolo':       r['model_yolo'],
        })
    return washers_data


def read_washer_logs_from_db(limit=None):
    """
    Returns a list of washer inspection log dicts.
    Keys match the oring log shape:
      order_number, employee_id, model, stage, subtask,
      current_quantity, required_quantity, status,
      image_path, predicted_image_path, date_time
    """
    sql = """
        SELECT order_number, employee_id, model, stage, subtask,
               current_quantity, required_quantity, status,
               image_path, predicted_image_path, created_at
        FROM washer_ai_logs
        ORDER BY created_at DESC
    """
    if limit:
        sql = sql.replace("ORDER BY created_at DESC",
                          "ORDER BY created_at DESC LIMIT %s")
        params = (limit,)
    else:
        params = ()

    with get_conn_cursor() as (conn, cur):
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        rows = cur.fetchall()

    logs = []
    for r in rows:
        logs.append({
            'order_number':         r['order_number'],
            'employee_id':          r['employee_id'],
            'model':                r['model'],
            'stage':                r['stage'],
            'subtask':              r['subtask'],
            'current_quantity':     r['current_quantity'],
            'required_quantity':    r['required_quantity'],
            'status':               r['status'],
            'image_path':           r['image_path'],
            'predicted_image_path': r['predicted_image_path'],
            'date_time': (r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                          if r['created_at'] else None),
        })
    return logs


def get_washer_required_quantity_from_db(model_name, subtask, stage):
    """
    Returns required_washers (int) for this model/stage/subtask, or None if not found.
    """
    sql = """
        SELECT required_washers
        FROM washer_ai_templates
        WHERE model = %s AND stage = %s AND subtask = %s
        LIMIT 1
    """
    with get_conn_cursor() as (conn, cur):
        cur.execute(sql, (model_name, stage, subtask))
        row = cur.fetchone()
    return row['required_washers'] if row else None


def get_all_required_washer_subtasks_from_db(stage, model_name):
    """
    Returns ordered list of subtasks for model + stage.
    """
    sql = """
        SELECT subtask
        FROM washer_ai_templates
        WHERE model = %s AND stage = %s
        ORDER BY subtask
    """
    with get_conn_cursor() as (conn, cur):
        cur.execute(sql, (model_name, stage))
        rows = cur.fetchall()
    return [r['subtask'] for r in rows]


def insert_washer_log_db(order_number, employee_id, model, stage, subtask,
                         current_quantity, required_quantity, status,
                         image_path=None, predicted_image_path=None):
    """
    Insert a washer inspection log row. Returns dict with id and created_at.
    """
    sql = """
        INSERT INTO washer_ai_logs
            (order_number, employee_id, model, stage, subtask,
             current_quantity, required_quantity, status,
             image_path, predicted_image_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, created_at
    """
    params = (
        order_number, employee_id, model, stage, subtask,
        current_quantity, required_quantity, status,
        image_path, predicted_image_path,
    )
    with get_conn_cursor() as (conn, cur):
        cur.execute(sql, params)
        row = cur.fetchone()
    return row  # dict: {id, created_at}


def insert_washer_predicted_image_record(blob_path, local_path=None):
    """
    Record a predicted (annotated) washer image in washer_ai_predicted_images.
    Returns dict with id and uploaded_at.
    """
    sql = """
        INSERT INTO washer_ai_predicted_images (blob_path, local_path)
        VALUES (%s, %s)
        RETURNING id, uploaded_at
    """
    with get_conn_cursor() as (conn, cur):
        cur.execute(sql, (blob_path, local_path))
        row = cur.fetchone()
    return row


def is_washer_stage_fully_completed(order_number, model, stage):
    """
    Returns (all_done: bool, required: list, completed: list).
    Mirrors is_stage_fully_completed() from oring_db_helpers.py.
    """
    with get_conn_cursor() as (conn, cur):

        # 1. Required subtasks
        cur.execute("""
            SELECT subtask
            FROM washer_ai_templates
            WHERE model = %s AND stage = %s
            ORDER BY subtask
        """, (model, stage))
        required = {r['subtask'] for r in cur.fetchall()}

        if not required:
            return False, [], []  # no template → treat as incomplete

        # 2. Completed subtasks (latest PASS)
        cur.execute("""
            SELECT DISTINCT ON (subtask) subtask
            FROM washer_ai_logs
            WHERE order_number = %s
              AND model = %s
              AND stage = %s
              AND status = 'pass'
            ORDER BY subtask, created_at DESC
        """, (order_number, model, stage))
        completed = {r['subtask'] for r in cur.fetchall()}

    pending = sorted(required - completed)
    return len(pending) == 0, sorted(required), sorted(completed)
