"use strict";
const $ = (id) => document.getElementById(id);
let dataset = null;
const num = (value, digits = 0) =>
  Number(value || 0).toLocaleString("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
const node = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
};
async function fetchJSON(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Could not load fleet data.",
    );
  return data;
}
function svg(tag, attrs, text) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
  if (text !== undefined) el.textContent = text;
  return el;
}
function chart(series) {
  const width = Math.max(320, $("energy-chart").clientWidth - 34);
  const canvas = svg("svg", { viewBox: `0 0 ${width} 210` });
  const max =
    Math.max(1, ...series.flatMap((s) => [s.energy_kwh, s.charged_kwh])) * 1.15;
  const start = 45,
    end = width - 15,
    top = 12,
    bottom = 175;
  for (let i = 0; i < 4; i++) {
    const y = bottom - (i * (bottom - top)) / 3;
    canvas.append(
      svg("line", {
        x1: start,
        y1: y,
        x2: end,
        y2: y,
        stroke: "#edf1ef",
        "stroke-dasharray": "3 4",
      }),
    );
    canvas.append(
      svg(
        "text",
        {
          x: 34,
          y: y + 3,
          "text-anchor": "end",
          "font-size": 9,
          fill: "#8ca198",
        },
        num((max * i) / 3),
      ),
    );
  }
  if (series.length) {
    const step = (end - start) / series.length;
    const width = Math.min(19, step * 0.28);
    series.forEach((s, i) => {
      const x = start + step * (i + 0.5);
      [
        ["energy_kwh", "#238e79", -width - 2],
        ["charged_kwh", "#bddbcc", 2],
      ].forEach(([key, color, offset]) => {
        const height = (s[key] / max) * (bottom - top);
        const bar = svg("rect", {
          x: x + offset,
          y: bottom - height,
          width,
          height,
          fill: color,
          rx: 3,
        });
        bar.append(
          svg(
            "title",
            {},
            `${s.event_date}: ${key === "energy_kwh" ? "Consumed" : "Charged"} ${num(s[key], 1)} kWh`,
          ),
        );
        canvas.append(bar);
      });
      canvas.append(
        svg(
          "text",
          {
            x,
            y: 197,
            "text-anchor": "middle",
            "font-size": 9,
            fill: "#869b90",
          },
          s.event_date.slice(5).replace("-", "/"),
        ),
      );
    });
  }
  $("energy-chart").replaceChildren(canvas);
}
function table() {
  if (!dataset) return;
  const query = $("vehicle-search").value.trim().toUpperCase();
  const rows = dataset.vehicles.filter((v) => v.vehicle_id.includes(query));
  $("vehicle-rows").replaceChildren();
  rows.forEach((v) => {
    const tr = node("tr");
    const id = node("td");
    const button = node("button", undefined, "vehicle-button");
    button.append(
      node("span", "▱", "vehicle-icon"),
      node("span", v.vehicle_id),
    );
    button.setAttribute("aria-label", "View trips for " + v.vehicle_id);
    button.addEventListener("click", () => showTrips(v.vehicle_id));
    id.append(button);
    tr.append(
      id,
      node("td", v.region),
      node("td", num(v.distance_km, 1) + " km"),
    );
    const soc = node("td");
    const wrap = node("span", undefined, "soc");
    const battery = node(
      "span",
      undefined,
      "battery" + (v.soc_pct < 15 ? " low" : ""),
    );
    const fill = node("i");
    fill.style.width = Math.max(0, Math.min(100, v.soc_pct || 0)) + "%";
    battery.append(fill);
    wrap.append(
      battery,
      node("span", v.soc_pct === null ? "—" : num(v.soc_pct) + "%"),
    );
    soc.append(wrap);
    tr.append(soc, node("td", num(v.efficiency, 1) + " kWh/100 km"));
    const alerts = node("td");
    alerts.append(
      node(
        "span",
        v.alerts ? num(v.alerts) + " flagged" : "Clear",
        v.alerts ? "alert-pill" : "clear-pill",
      ),
    );
    tr.append(alerts, node("td", "↗"));
    $("vehicle-rows").append(tr);
  });
  if (!rows.length) {
    const td = node("td", "No vehicles match your search.");
    td.colSpan = 7;
    const tr = node("tr");
    tr.append(td);
    $("vehicle-rows").append(tr);
  }
  $("table-count").textContent =
    `${rows.length} of ${dataset.vehicles.length} vehicles`;
}
function render(data) {
  dataset = data;
  const s = data.summary,
    p = data.pipeline;
  $("vehicles-kpi").textContent = num(s.vehicles);
  $("distance-kpi").textContent = num(s.distance_km);
  $("efficiency-kpi").textContent = num(s.kwh_per_100km, 1);
  $("cost-kpi").textContent = "$" + num(s.cost_usd);
  $("trip-total").textContent = num(s.trips) + " trips recorded";
  $("date-range").textContent = `${s.start_date || "—"} — ${s.end_date || "—"}`;
  $("snapshot-label").textContent = "Published snapshot · " + p.mode;
  $("bronze-count").textContent = num(p.bronze_unique_payloads);
  $("silver-count").textContent = num(p.silver_events);
  $("quarantine-count").textContent = num(p.quarantined);
  $("quality-badge").textContent =
    num(p.quality_pass_pct, 2) + "% raw records valid";
  $("run-id").textContent = "RUN " + p.run_id;
  $("run-time").textContent =
    `${num(p.duration_seconds, 1)}s pipeline · dbt checks passed`;
  chart(data.series);
  table();
  $("regions").replaceChildren();
  data.regions.forEach((r) => {
    const line = node("div", undefined, "region-row");
    line.append(
      node("strong", r.region),
      node("span", `${r.vehicles} vehicles · ${num(r.distance_km)} km`),
    );
    $("regions").append(line);
  });
}
async function refresh() {
  const selected = $("region").value;
  $("refresh").disabled = true;
  $("region").disabled = true;
  $("error").hidden = true;
  try {
    render(
      await fetchJSON("/api/overview?region=" + encodeURIComponent(selected)),
    );
  } catch (error) {
    $("error").textContent = error.message;
    $("error").hidden = false;
    $("snapshot-label").textContent = "No snapshot available";
  } finally {
    $("refresh").disabled = false;
    $("region").disabled = false;
  }
}
async function showTrips(id) {
  $("trip-title").textContent = id + " · Recent trips";
  $("trip-content").textContent = "Loading trips…";
  $("trip-dialog").showModal();
  try {
    const data = await fetchJSON(
      "/api/vehicles/" + encodeURIComponent(id) + "/trips",
    );
    const t = node("table");
    const head = node("tr");
    ["DATE", "ROUTE", "DISTANCE", "DURATION", "ENERGY"].forEach((x) =>
      head.append(node("th", x)),
    );
    const thead = node("thead");
    thead.append(head);
    t.append(thead);
    const body = node("tbody");
    data.trips.forEach((r) => {
      const row = node("tr");
      [
        r.date_key,
        r.route_id,
        num(r.distance_km, 1) + " km",
        num(r.duration_min) + " min",
        num(r.energy_kwh, 1) + " kWh",
      ].forEach((x) => row.append(node("td", x)));
      body.append(row);
    });
    t.append(body);
    $("trip-content").replaceChildren(t);
  } catch (error) {
    $("trip-content").textContent = error.message;
  }
}
$("region").addEventListener("change", refresh);
$("refresh").addEventListener("click", refresh);
$("vehicle-search").addEventListener("input", table);
$("close-dialog").addEventListener("click", () => $("trip-dialog").close());
$("export").addEventListener("click", () => {
  if (!dataset) return;
  const columns = [
    "vehicle_id",
    "region",
    "distance_km",
    "trips",
    "soc_pct",
    "efficiency",
    "alerts",
  ];
  const escape = (value) =>
    '"' + String(value ?? "").replaceAll('"', '""') + '"';
  const csv = [
    columns.join(","),
    ...dataset.vehicles.map((row) =>
      columns.map((c) => escape(row[c])).join(","),
    ),
  ].join("\r\n");
  const url = URL.createObjectURL(
    new Blob([csv], { type: "text/csv;charset=utf-8;" }),
  );
  const a = node("a");
  a.href = url;
  a.download = "synthetic-fleet-" + $("region").value.toLowerCase() + ".csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
window.addEventListener("resize", () => {
  if (dataset) chart(dataset.series);
});
refresh();
