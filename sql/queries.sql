-- Purchase-to-pay analysis in SQL (DuckDB reads the CSV directly, no database setup needed)
-- Run with:  python src/run_sql.py

-- 1. Most common process steps
SELECT activity, COUNT(*) AS events
FROM 'data/events.csv'
GROUP BY activity
ORDER BY events DESC
LIMIT 10;

-- 2. Data quality: events with impossible dates
SELECT YEAR(timestamp::TIMESTAMP) AS year, COUNT(*) AS events
FROM 'data/events.csv'
GROUP BY year
ORDER BY year;

-- 3. Rework: how many order items needed a price or quantity change?
SELECT
    COUNT(DISTINCT case_id) AS cases_with_rework,
    ROUND(100.0 * COUNT(DISTINCT case_id) /
          (SELECT COUNT(DISTINCT case_id) FROM 'data/events.csv'), 1) AS pct_of_all_cases
FROM 'data/events.csv'
WHERE activity IN ('Change Price', 'Change Quantity');

-- 4. Median days from vendor invoice to payment, per matching type
WITH per_case AS (
    SELECT
        case_id,
        ANY_VALUE(item_category) AS item_category,
        MIN(CASE WHEN activity = 'Vendor creates invoice' THEN timestamp::TIMESTAMP END) AS invoiced,
        MAX(CASE WHEN activity = 'Clear Invoice'          THEN timestamp::TIMESTAMP END) AS paid
    FROM 'data/events.csv'
    GROUP BY case_id
)
SELECT
    item_category,
    COUNT(*) AS paid_cases,
    MEDIAN(DATE_DIFF('day', invoiced, paid)) AS median_days_invoice_to_pay
FROM per_case
WHERE paid >= invoiced AND YEAR(invoiced) BETWEEN 2017 AND 2019
GROUP BY item_category
ORDER BY paid_cases DESC;

-- 5. Vendors with the most payment blocks
SELECT
    vendor,
    COUNT(DISTINCT case_id) AS cases_with_block
FROM 'data/events.csv'
WHERE activity = 'Remove Payment Block'
GROUP BY vendor
ORDER BY cases_with_block DESC
LIMIT 10;
