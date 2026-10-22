WITH required_subtasks AS (
    -- total required subtasks per model + stage
    SELECT
        model,
        stage,
        COUNT(*) AS required_count
    FROM ipv_ai_templates
    GROUP BY model, stage
),
order_completion AS (
    -- completed (PASS) subtasks per order
    SELECT
        order_number,
        model,
        stage,
        COUNT(DISTINCT subtask) FILTER (WHERE status = 'pass') AS completed_count
    FROM ipv_ai_logs
    GROUP BY order_number, model, stage
),
incomplete_orders AS (
    -- only orders that are truly incomplete
    SELECT
        o.order_number,
        o.model,
        o.stage
    FROM order_completion o
    JOIN required_subtasks r
      ON r.model = o.model
     AND r.stage = o.stage
    WHERE o.completed_count < r.required_count
)
SELECT
    l.employee_id,
    COUNT(DISTINCT l.order_number) AS incomplete_orders_count
FROM ipv_ai_logs l
JOIN incomplete_orders io
  ON io.order_number = l.order_number
GROUP BY l.employee_id
ORDER BY incomplete_orders_count DESC;
