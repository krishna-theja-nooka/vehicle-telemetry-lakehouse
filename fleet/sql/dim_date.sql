SELECT DISTINCT event_date AS date_key, year(event_date) AS year,
    month(event_date) AS month, dayofmonth(event_date) AS day,
    date_format(event_date, 'EEEE') AS weekday
FROM events
