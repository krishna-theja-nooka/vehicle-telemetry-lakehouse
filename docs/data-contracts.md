# Data contracts and metric definitions

All events have `event_id`, `vehicle_id`, `event_type`, `schema_version=1`, positive integer `revision`, `event_time` (UTC `YYYY-MM-DDTHH:MM:SSZ`) and informational `emitted_at`. Valid event types: telemetry, trip, charging, maintenance, toll. `emitted_at` is retained but not used for ordering or latency claims. `ingested_at` is assigned by the Bronze sink.

| Type | Required measurements | Validation |
| --- | --- | --- |
| Telemetry | latitude, longitude, speed_kph, soc_pct, battery_temp_c | Latitude ±90; longitude ±180; speed 0–250; SOC 0–100; temperature −40–90; reject null/NaN |
| Trip | distance_km, duration_min, energy_kwh, route_id | Distance >0 up to 2,000; duration >0 up to 1,440; energy 0–500; `R-NN` route |
| Charging | energy_kwh, duration_min, cost_usd | Positive energy/duration, bounded to 500 kWh/1,440 min; cost 0–10,000 |
| Maintenance | severity, code, cost_usd | info/warning/critical; bounded alphanumeric code; cost 0–100,000 |
| Toll | cost_usd | 0–1,000 |

Event IDs are bounded to 100 letters, digits, underscores or hyphens. Vehicle IDs use `EV-NNN` or `EV-NNNN`. Revisions are 1–10,000. Future event times beyond one day after ingestion fail validation. Unknown vehicle versions, unsupported schemas and malformed JSON are retained in quarantine. More than 5% invalid unique Bronze payloads blocks publication. Gold dimension overlaps and same-ID/revision conflicts also block publication.

The source contract assumes trip and charging events summarize completed sessions, not cumulative counters or charging power. All currency values are USD. Floating-point values are suitable for synthetic analytics, not accounting-grade reconciliation.

## Metric semantics

- **Active vehicles:** distinct vehicle IDs with accepted events in the selected region/date window. A moved vehicle can appear in two regional counts; regional vehicle counts therefore do not necessarily sum to the fleet distinct count.
- **Distance:** sum of canonical completed trip distances. Telemetry samples do not add mileage.
- **Efficiency:** `100 × sum(trip energy_kwh) / sum(trip distance_km)`. This is a weighted ratio, not an average of per-trip ratios.
- **Recorded costs:** charging costs + maintenance costs + toll costs. Excludes depreciation, labor not present in an event, insurance and all other unmodeled costs.
- **Battery shown:** last telemetry SOC by event time in the selected region's history. It is not a current live reading. Daily minimum SOC and maximum temperature are also retained.
- **Telemetry alert:** one sample with SOC <15%, temperature >45°C or speed >120 kph. Multiple rules on one sample still count as one alert event.
- **Maintenance alert:** one critical maintenance event. A vehicle with a historical alert may currently have normal measurements. The UI labels historical alert events accordingly.
- **Quality pass rate:** `(unique Bronze payloads − quarantined payloads) / unique Bronze payloads`. It includes valid older revisions; Silver event count is smaller when corrections exist.
- **Charged versus consumed:** charging energy and trip energy are separate facts. No equality or energy-balance guarantee is asserted because initial/final battery inventory is not modeled.

The reference history includes EV-004 moving from Austin to Denver at October 4, 2026 00:00 UTC when generating four or more days. No SCD2 intervals overlap. The default data deliberately includes out-of-arrival-order timestamps and a revision-2 correction to an older trip.
