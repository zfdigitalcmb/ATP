-- Templates for orings (replaces oring_template.xlsx)
CREATE TABLE IF NOT EXISTS ipv_ai_templates (
  id SERIAL PRIMARY KEY,
  model TEXT NOT NULL,
  subtask INTEGER NOT NULL,
  required_orings INTEGER,
  stage TEXT,
  description TEXT,
  sample_image TEXT,
  class_to_find TEXT,
  class_index INTEGER,
  model_yolo TEXT,
  UNIQUE(model, stage, subtask)
);

CREATE INDEX IF NOT EXISTS idx_ipv_ai_templates_model ON ipv_ai_templates (model);
CREATE INDEX IF NOT EXISTS idx_ipv_ai_templates_stage ON ipv_ai_templates (stage);

-- Logs replacing internal CSV log (internalpartslog)
CREATE TABLE IF NOT EXISTS ipv_ai_logs (
  id BIGSERIAL PRIMARY KEY,
  order_number TEXT NOT NULL,
  employee_id TEXT,
  model TEXT,
  stage TEXT,
  subtask INTEGER,
  current_quantity INTEGER,
  required_quantity INTEGER,
  status TEXT,
  image_path TEXT,
  predicted_image_path TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ipv_ai_logs_order ON ipv_ai_logs (order_number);
CREATE INDEX IF NOT EXISTS idx_ipv_ai_logs_model ON ipv_ai_logs (model);
CREATE INDEX IF NOT EXISTS idx_ipv_ai_logs_created_at ON ipv_ai_logs (created_at);

-- Predicted images
CREATE TABLE IF NOT EXISTS ipv_ai_predicted_images (
  id BIGSERIAL PRIMARY KEY,
  blob_path TEXT,
  local_path TEXT,
  uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- YOLO models metadata
CREATE TABLE IF NOT EXISTS ipv_ai_yolo_models (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE,              -- e.g., "ORING-COUNT-2025.pt"
  blob_path TEXT,                -- path inside container
  local_path TEXT,               -- last downloaded local path
  last_updated TIMESTAMP WITH TIME ZONE
);

-- Admins for IPV AI module
CREATE TABLE IF NOT EXISTS ipv_admins (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  full_name TEXT,
  email TEXT,
  password_hash TEXT NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ipv_admins_username ON ipv_admins (username);


-- Table to replace the Excel sheet: PA-MA-PLC-PLATES-STAND
CREATE TABLE IF NOT EXISTS plc_boltsai_plate_bolt_entries (
    id SERIAL PRIMARY KEY,
    cell TEXT NOT NULL,
    status TEXT NOT NULL,                  -- 'OK', 'NOK', 'WIP', etc.
    image_filename TEXT,                   -- filename stored in blob container
    image_url TEXT,                        -- optional full blob url (no SAS)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    stand TEXT,                            -- e.g. 'A', 'B' or stand identifier
    approval_status TEXT DEFAULT 'PENDING',-- PENDING / APPROVED / REJECTED
    created_by INTEGER NULL,               -- optional user id if you have auth
    bolt_count INTEGER NULL,               -- convenience column
    set_statuses TEXT NULL                 -- JSON/text summary like '["Set1: OK", ...]'
);

-- Useful index for fast lookups by cell and created_at
CREATE INDEX IF NOT EXISTS idx_plc_boltsai_cell_created_at ON plc_boltsai_plate_bolt_entries (cell, created_at DESC);


CREATE TABLE IF NOT EXISTS ipv_ai_devices (
  id BIGSERIAL PRIMARY KEY,
  device_name TEXT NOT NULL UNIQUE,    -- e.g. "Pi1"
  nick_name TEXT NULL,                 -- friendly name
  position TEXT NULL,                  -- e.g. "Line-1 Station-2"
  ip INET NULL,
  mac TEXT NULL UNIQUE,                -- MAC address
  model_name TEXT NULL,
  stage INTEGER NULL,
  subtask INTEGER NULL,
  user_id TEXT NULL,                   -- optional operator assigned
  password_hash TEXT NULL,             -- optional hashed pass for device UI
  ssid TEXT NULL,
  ssid_key_encrypted TEXT NULL,       -- encrypted wifi key (binary)
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now(),
  last_seen_at TIMESTAMPTZ NULL,
  is_active BOOLEAN DEFAULT TRUE
);


CREATE TABLE IF NOT EXISTS device_pairs (
  id BIGSERIAL PRIMARY KEY,
  device_id INT NOT NULL REFERENCES ipv_ai_devices(id) ON DELETE CASCADE,
  order_number TEXT NOT NULL,
  paired_by TEXT NULL,
  paired_at TIMESTAMPTZ,
  auto_capture BOOLEAN DEFAULT TRUE,
  status TEXT DEFAULT 'PENDING',
  last_capture_at TIMESTAMPTZ NULL
);

ALTER TABLE device_pairs ADD COLUMN IF NOT EXISTS subtask INTEGER NULL;

