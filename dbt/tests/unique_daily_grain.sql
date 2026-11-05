SELECT vehicle_sk, event_date FROM {{ ref('mart_fleet') }}
GROUP BY vehicle_sk, event_date HAVING count(*) > 1
