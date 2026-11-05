# Two-minute demo

1. Run the default generator and pipeline. Open the dashboard and point out the **synthetic data** label.
2. Explain distance-weighted efficiency and recorded cost scope. Show the consumed-versus-charged chart without implying those totals must match.
3. Filter to Austin, then Denver. Explain that EV-004's historical assignment changes on October 4 and facts use event-time SCD2 joins.
4. Search `EV-008` in the full fleet view, open its trip detail and export vehicle metrics as CSV. Historical temperature alerts are rule-based flags, not a predictive maintenance model.
5. Show the quality panel: valid Silver events, five quarantined examples, and the run ID. Open the run report and dbt results.
6. In a terminal run `fleet run --mode stream` and explain checkpointed micro-batches and idempotent replay. The file-source path is real Structured Streaming, not a Kafka performance benchmark.

Suggested screenshots to capture from your own browser: `screenshots/overview.png`, `screenshots/vehicle-detail.png`, `screenshots/quality.png`. Keep credentials and local private paths out of recordings. Label every capture as synthetic demo data. The supplied SVG banner is original repository artwork, not a screenshot or evidence of a cloud deployment.
