SELECT vehicle_id, vehicle_sk, region, event_date,
    count(*) AS event_count,
    sum(CASE WHEN event_type = 'trip' THEN 1 ELSE 0 END) AS trip_count,
    sum(CASE WHEN event_type = 'trip' THEN distance_km ELSE 0 END) AS distance_km,
    sum(CASE WHEN event_type = 'trip' THEN duration_min ELSE 0 END) AS driving_minutes,
    sum(CASE WHEN event_type = 'trip' THEN energy_kwh ELSE 0 END) AS consumed_kwh,
    sum(CASE WHEN event_type = 'charging' THEN energy_kwh ELSE 0 END) AS charged_kwh,
    sum(CASE WHEN event_type = 'charging' THEN cost_usd ELSE 0 END) AS charging_cost_usd,
    sum(CASE WHEN event_type = 'maintenance' THEN cost_usd ELSE 0 END) AS maintenance_cost_usd,
    sum(CASE WHEN event_type = 'toll' THEN cost_usd ELSE 0 END) AS toll_cost_usd,
    sum(CASE WHEN event_type = 'maintenance' THEN 1 ELSE 0 END) AS maintenance_count,
    min(soc_pct) AS min_soc_pct,
    max_by(soc_pct, event_ts) FILTER (WHERE event_type = 'telemetry') AS last_soc_pct,
    max(battery_temp_c) AS max_battery_temp_c,
    sum(CASE WHEN event_type = 'telemetry'
        AND (soc_pct < 15 OR battery_temp_c > 45 OR speed_kph > 120)
        THEN 1 ELSE 0 END) AS telemetry_alerts,
    sum(CASE WHEN event_type = 'maintenance' AND severity = 'critical'
        THEN 1 ELSE 0 END) AS critical_maintenance
FROM events
GROUP BY vehicle_id, vehicle_sk, region, event_date
