-- schema_washer.sql
-- Washer detection tables (mirrors the o-ring pattern)
-- Run once against your PostgreSQL database.

-- ──────────────────────────────────────────────
-- Templates: defines what washers are expected at each model/stage/subtask
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS washer_ai_templates (
  id               SERIAL PRIMARY KEY,
  model            TEXT        NOT NULL,
  subtask          INTEGER     NOT NULL,
  required_washers INTEGER,
  stage            TEXT,
  description      TEXT,
  sample_image     TEXT,
  class_to_find    TEXT,        -- YOLO class label to detect
  class_index      INTEGER,     -- YOLO class index
  model_yolo       TEXT,        -- filename of the .pt model to use
  UNIQUE (model, stage, subtask)
);

CREATE INDEX IF NOT EXISTS idx_washer_ai_templates_model ON washer_ai_templates (model);
CREATE INDEX IF NOT EXISTS idx_washer_ai_templates_stage ON washer_ai_templates (stage);

-- ──────────────────────────────────────────────
-- Logs: one row per washer inspection attempt
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS washer_ai_logs (
  id                   BIGSERIAL PRIMARY KEY,
  order_number         TEXT      NOT NULL,
  employee_id          TEXT,
  model                TEXT,
  stage                TEXT,
  subtask              INTEGER,
  current_quantity     INTEGER,
  required_quantity    INTEGER,
  status               TEXT,     -- 'pass' | 'fail'
  image_path           TEXT,
  predicted_image_path TEXT,
  created_at           TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_washer_ai_logs_order      ON washer_ai_logs (order_number);
CREATE INDEX IF NOT EXISTS idx_washer_ai_logs_model      ON washer_ai_logs (model);
CREATE INDEX IF NOT EXISTS idx_washer_ai_logs_created_at ON washer_ai_logs (created_at);

-- ──────────────────────────────────────────────
-- Predicted images (for washer inference results)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS washer_ai_predicted_images (
  id          BIGSERIAL PRIMARY KEY,
  blob_path   TEXT,
  local_path  TEXT,
  uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
