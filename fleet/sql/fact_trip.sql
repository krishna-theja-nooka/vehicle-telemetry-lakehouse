SELECT event_id, vehicle_sk, vehicle_id, event_date AS date_key,
    event_ts, region, route_id, distance_km, duration_min, energy_kwh
FROM events WHERE event_type = 'trip'
