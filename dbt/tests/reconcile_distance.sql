SELECT 1 AS mismatch
WHERE abs(
  (SELECT coalesce(sum(distance_km), 0) FROM {{ ref('mart_fleet') }}) -
  (SELECT coalesce(sum(distance_km), 0) FROM {{ ref('fact_trip') }})
) > 0.001
