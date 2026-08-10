-- =====================================================
-- LOGGER SETUP SCRIPT (PostgreSQL)
-- Run this ONCE per database
-- =====================================================

-- 1. Optional: Create schema for organization
CREATE SCHEMA IF NOT EXISTS app_utils;

-- =====================================================
-- 2. Log Level ENUM (cleaner than free text)
-- =====================================================
DO $$
BEGIN
IF NOT EXISTS (
SELECT 1 FROM pg_type WHERE typname = 'log_level_enum'
) THEN
CREATE TYPE app_utils.log_level_enum AS ENUM ('DEBUG', 'INFO', 'WARN', 'ERROR');
END IF;
END $$;

-- =====================================================
-- 3. Central Log Table
-- =====================================================
CREATE TABLE IF NOT EXISTS app_utils.app_logger (
log_id           BIGSERIAL PRIMARY KEY,
log_timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
log_level        app_utils.log_level_enum,
user_name        TEXT,
session_id       INT,
function_name    TEXT,
message          TEXT,
query_text       TEXT,
execution_time   INTERVAL,
error_detail     TEXT,
extra_data       JSONB
);

-- =====================================================
-- 4. Indexes (important for scaling)
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_logger_time
ON app_utils.app_logger(log_timestamp);

CREATE INDEX IF NOT EXISTS idx_logger_user
ON app_utils.app_logger(user_name);

CREATE INDEX IF NOT EXISTS idx_logger_level
ON app_utils.app_logger(log_level);

-- =====================================================
-- 5. Core Logging Function
-- =====================================================
CREATE OR REPLACE FUNCTION app_utils.log_event(
p_level app_utils.log_level_enum,
p_message TEXT,
p_function_name TEXT DEFAULT NULL,
p_query TEXT DEFAULT NULL,
p_execution_time INTERVAL DEFAULT NULL,
p_error TEXT DEFAULT NULL,
p_extra JSONB DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
INSERT INTO app_utils.app_logger (
log_level,
user_name,
session_id,
function_name,
message,
query_text,
execution_time,
error_detail,
extra_data
)
VALUES (
p_level,
current_user,
pg_backend_pid(),
p_function_name,
p_message,
p_query,
p_execution_time,
p_error,
p_extra
);

```
-- Optional: also print to pgAdmin Messages panel
RAISE NOTICE '[%] %', p_level, p_message;
```

END;
$$;

-- =====================================================
-- 6. Query Execution Wrapper (optional utility)
-- =====================================================
CREATE OR REPLACE FUNCTION app_utils.log_query_execution(p_query TEXT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
start_time TIMESTAMP;
end_time TIMESTAMP;
BEGIN
start_time := clock_timestamp();

```
EXECUTE p_query;

end_time := clock_timestamp();

PERFORM app_utils.log_event(
    'INFO',
    'Query executed successfully',
    'log_query_execution',
    p_query,
    end_time - start_time,
    NULL,
    NULL
);
```

EXCEPTION WHEN OTHERS THEN
end_time := clock_timestamp();

```
PERFORM app_utils.log_event(
    'ERROR',
    'Query failed',
    'log_query_execution',
    p_query,
    end_time - start_time,
    SQLERRM,
    jsonb_build_object('sqlstate', SQLSTATE)
);

RAISE;
```

END;
$$;

-- =====================================================
-- 7. Helper View (pretty logs)
-- =====================================================
CREATE OR REPLACE VIEW app_utils.v_app_logs AS
SELECT
log_id,
to_char(log_timestamp, 'YYYY-MM-DD HH24:MI:SS') AS log_time,
log_level,
user_name,
function_name,
message,
execution_time,
error_detail,
extra_data
FROM app_utils.app_logger
ORDER BY log_id DESC;

-- =====================================================
-- 8. Cleanup Function (basic retention)
-- =====================================================
CREATE OR REPLACE FUNCTION app_utils.cleanup_logs(p_days INT DEFAULT 7)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
DELETE FROM app_utils.app_logger
WHERE log_timestamp < NOW() - (p_days || ' days')::INTERVAL;
END;
$$;

-- =====================================================
-- DONE
-- =====================================================
-- Usage examples:
-- SELECT app_utils.log_event('INFO', 'Test log');
-- SELECT * FROM app_utils.v_app_logs;
