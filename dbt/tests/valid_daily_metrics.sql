SELECT * FROM {{ ref('mart_fleet') }}
WHERE distance_km < 0 OR consumed_kwh < 0 OR operating_cost_usd < 0
   OR trip_count < 0 OR last_soc_pct NOT BETWEEN 0 AND 100
