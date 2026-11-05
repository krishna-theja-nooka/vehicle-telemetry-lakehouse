SELECT event_id, vehicle_sk, vehicle_id, event_date AS date_key,
    event_ts, region, duration_min, energy_kwh, cost_usd
FROM events WHERE event_type = 'charging'
