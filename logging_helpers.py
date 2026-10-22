# logging_helpers.py
from db import get_conn_cursor
from datetime import datetime

def insert_internal_log(order_number, employee_id, model_name, stage, subtask,
                        current_quantity, required_quantity, status,
                        image_path, predicted_image_path):
    with get_conn_cursor() as (conn, cur):
        cur.execute("""
            INSERT INTO ipv_ai_logs
            (order_number, employee_id, model, stage, subtask, current_quantity, required_quantity, status, image_path, predicted_image_path, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (order_number, employee_id, model_name, stage, subtask, current_quantity,
              required_quantity, status, image_path, predicted_image_path, datetime.now()))
        return cur.fetchone()

def read_logs_from_db(limit=None):
    with get_conn_cursor() as (conn, cur):
        q = "SELECT * FROM ipv_ai_logs ORDER BY created_at DESC"
        if limit:
            cur.execute(q + " LIMIT %s", (limit,))
        else:
            cur.execute(q)
        return cur.fetchall()

def insert_predicted_image_record(blob_path, local_path):
    with get_conn_cursor() as (conn, cur):
        cur.execute("""
            INSERT INTO ipv_ai_predicted_images (blob_path, local_path, uploaded_at)
            VALUES (%s,%s,%s) RETURNING id
        """, (blob_path, local_path, datetime.now()))
        return cur.fetchone()
