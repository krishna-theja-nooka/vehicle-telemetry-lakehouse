SELECT *,
    charging_cost_usd + maintenance_cost_usd + toll_cost_usd AS operating_cost_usd,
    100.0 * consumed_kwh / nullif(distance_km, 0) AS kwh_per_100km,
    telemetry_alerts + critical_maintenance AS alert_count
FROM read_parquet('{{ env_var("FLEET_EXPORTS") }}/fleet_daily/*.parquet')
