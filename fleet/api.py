import json
import logging
import re
import time
from pathlib import Path
from typing import Literal
from uuid import uuid4

import duckdb
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from fleet.config import Paths

STATIC = Path(__file__).parent / "static"
REGIONS = Literal["All", "Austin", "Dallas", "Denver"]
logger = logging.getLogger("fleet.api")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False


def snapshot(paths: Paths) -> Path:
    pointer = paths.serving / "CURRENT"
    if not pointer.exists():
        raise HTTPException(503, "No published data yet. Run fleet generate, then fleet run.")
    run_id = pointer.read_text().strip()
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}-[a-f0-9]{8}", run_id):
        raise HTTPException(503, "The data snapshot pointer is invalid. Republish the pipeline.")
    return paths.serving / run_id


def rows(conn, sql, params=None):
    result = conn.execute(sql, params or [])
    keys = [item[0] for item in result.description]
    return [dict(zip(keys, values, strict=True)) for values in result.fetchall()]


def create_app(paths: Paths | None = None):
    paths = paths or Paths.from_env()
    app = FastAPI(title="Fleet Pulse · Vehicle Telemetry Analytics", version="0.1.0")
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )

    @app.middleware("http")
    async def trace(request: Request, call_next):
        request_id, started = str(uuid4()), time.perf_counter()
        try:
            response = await call_next(request)
        except (OSError, duckdb.Error, ValueError):
            from fastapi.responses import JSONResponse

            response = JSONResponse(
                {"detail": "Snapshot unavailable. Check the pipeline report."}, 503
            )
        response.headers.update(
            {
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; style-src 'self'; "
                "script-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
            }
        )
        # Swagger uses external assets. Keep the dashboard strict; allow Swagger's default assets.
        if request.url.path == "/docs":
            del response.headers["Content-Security-Policy"]
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
        )
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "synthetic": True}

    @app.get("/ready")
    def ready():
        current = snapshot(paths)
        with duckdb.connect(str(current / "analytics.duckdb"), read_only=True) as conn:
            conn.execute("SELECT count(*) FROM mart_fleet").fetchone()
        return {"status": "ready", "run_id": current.name}

    @app.get("/api/overview")
    def overview(region: REGIONS = "All"):
        current = snapshot(paths)
        params = [region, region]
        clause = "WHERE (? = 'All' OR region = ?)"
        with duckdb.connect(str(current / "analytics.duckdb"), read_only=True) as conn:
            summary = rows(
                conn,
                f"""
                SELECT count(DISTINCT vehicle_id) AS vehicles, sum(trip_count) AS trips,
                sum(distance_km) AS distance_km, sum(consumed_kwh) AS consumed_kwh,
                100 * sum(consumed_kwh) / nullif(sum(distance_km),0) AS kwh_per_100km,
                sum(operating_cost_usd) AS cost_usd, sum(alert_count) AS alerts,
                min(event_date) AS start_date, max(event_date) AS end_date
                FROM mart_fleet {clause}
            """,
                params,
            )[0]
            series = rows(
                conn,
                f"""
                SELECT event_date, sum(distance_km) AS distance_km, sum(consumed_kwh) AS energy_kwh,
                sum(charged_kwh) AS charged_kwh, sum(alert_count) AS alerts
                FROM mart_fleet {clause} GROUP BY event_date ORDER BY event_date
            """,
                params,
            )
            vehicles = rows(
                conn,
                f"""
                SELECT vehicle_id, arg_max(region, event_date) AS region,
                sum(distance_km) AS distance_km, sum(trip_count) AS trips,
                arg_max(last_soc_pct, event_date) AS soc_pct,
                max(max_battery_temp_c) AS max_temp_c, sum(alert_count) AS alerts,
                100 * sum(consumed_kwh) / nullif(sum(distance_km),0) AS efficiency
                FROM mart_fleet {clause} GROUP BY vehicle_id
                ORDER BY alerts DESC, vehicle_id LIMIT 500
            """,
                params,
            )
            regions = rows(
                conn,
                """
                SELECT region, count(DISTINCT vehicle_id) AS vehicles,
                sum(distance_km) AS distance_km FROM mart_fleet GROUP BY region ORDER BY region
            """,
            )
        return {
            "summary": summary,
            "series": series,
            "vehicles": vehicles,
            "regions": regions,
            "pipeline": json.loads((current / "report.json").read_text()),
            "synthetic": True,
        }

    @app.get("/api/vehicles/{vehicle_id}/trips")
    def trips(vehicle_id: str):
        if not re.fullmatch(r"EV-\d{3,4}", vehicle_id):
            raise HTTPException(422, "Use a vehicle ID such as EV-001.")
        current = snapshot(paths)
        with duckdb.connect(str(current / "analytics.duckdb"), read_only=True) as conn:
            result = rows(
                conn,
                """
                SELECT event_id, date_key, region, route_id, distance_km, duration_min, energy_kwh
                FROM fact_trip WHERE vehicle_id = ? ORDER BY event_ts DESC LIMIT 100
            """,
                [vehicle_id],
            )
        if not result:
            raise HTTPException(404, "Vehicle not found in this snapshot.")
        return {"vehicle_id": vehicle_id, "trips": result}

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
