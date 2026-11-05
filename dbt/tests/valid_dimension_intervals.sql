SELECT a.vehicle_sk
FROM {{ ref('dim_vehicle') }} a JOIN {{ ref('dim_vehicle') }} b
 ON a.vehicle_id = b.vehicle_id AND a.vehicle_sk != b.vehicle_sk
 AND a.valid_from < b.valid_to AND b.valid_from < a.valid_to
