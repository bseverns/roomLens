"""Lightweight FastAPI control surface for Room Lens mappings.

This module stays intentionally self-contained: importable from notebooks or
``host/python/app.py`` without bringing in the rest of the CLI glue. The API
mirrors the mapping dict that drives the live pipeline so edits can hit OSC in
real time, be inspected in a browser, and be written back to YAML when the room
is tuned.
"""
from __future__ import annotations

import datetime as _dt
import difflib
import json
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, MutableMapping, Optional

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from roomlens import MappingPipeline, demo_frame
from roomlens.mapping import clone_mapping, update_axis_mapping


class MappingState:
    """Shared mapping state and edit history.

    The object is intentionally conservative: edits take copies, a rollback stack
    is maintained, and every mutation is timestamped so workshops can replay what
    happened. The FastAPI routes simply proxy into this stateful helper.
    """

    def __init__(self, pipeline: MappingPipeline, mapping_path: Path) -> None:
        self.pipeline = pipeline
        self.mapping_path = mapping_path
        self.lock = threading.Lock()
        self.mapping: MutableMapping[str, Any] = clone_mapping(pipeline.mapping)
        self.history: list[MutableMapping[str, Any]] = []
        self.log: list[Dict[str, Any]] = []
        self.last_payload: Dict[str, Any] | None = None
        try:
            self.baseline_text = mapping_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.baseline_text = ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _stamp(self) -> str:
        return _dt.datetime.now().isoformat(timespec="seconds")

    def _record(self, action: str, axis: str | None = None, detail: str = "") -> None:
        self.log.append({
            "t": self._stamp(),
            "action": action,
            "axis": axis,
            "detail": detail,
        })

    def _push_history(self) -> None:
        self.history.append(clone_mapping(self.mapping))
        # keep the stack small so long-lived servers do not eat RAM
        if len(self.history) > 32:
            self.history.pop(0)

    def set_last_payload(self, payload: Dict[str, Any]) -> None:
        self.last_payload = payload

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def routes(self) -> list[Dict[str, Any]]:
        sensors = self.mapping.get("sensors", {}) or {}
        axes_meta = self.mapping.get("axes", {}) or {}
        routes: list[Dict[str, Any]] = []
        for sensor_name, sensor_cfg in sensors.items():
            for feature_name, feature_cfg in (sensor_cfg.get("features", {}) or {}).items():
                map_to = feature_cfg.get("map_to", {}) or {}
                axis = map_to.get("axis")
                if not axis:
                    continue
                meta = axes_meta.get(axis, {})
                routes.append({
                    "sensor": sensor_name,
                    "feature": feature_name,
                    "axis": axis,
                    "label": feature_cfg.get("label", feature_name),
                    "range": map_to.get("range", [0.0, 1.0]),
                    "expo": map_to.get("expo", 1.0),
                    "offset": map_to.get("offset", 0.0),
                    "transform": feature_cfg.get("transform", feature_cfg.get("doc_transform")),
                    "notes": feature_cfg.get("notes", ""),
                    "axis_meta": meta,
                })
        return routes

    def diff(self) -> str:
        current_text = yaml.safe_dump(self.mapping, sort_keys=False)
        diff_lines = difflib.unified_diff(
            self.baseline_text.splitlines(),
            current_text.splitlines(),
            fromfile=str(self.mapping_path),
            tofile="current",
            lineterm="",
        )
        return "\n".join(diff_lines)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------
    def patch_axis(
        self,
        axis: str,
        *,
        range_values: tuple[float, float] | None = None,
        expo: float | None = None,
        offset: float | None = None,
    ) -> MutableMapping[str, Any]:
        with self.lock:
            self._push_history()
            update_axis_mapping(self.mapping, axis, range_values=range_values, expo=expo, offset=offset)
            self.pipeline.update_mapping(self.mapping)
            detail = f"range={range_values} expo={expo} offset={offset}"
            self._record("patch", axis, detail)
            self._mirror_to_osc(axis)
            return self.mapping

    def undo(self) -> MutableMapping[str, Any]:
        with self.lock:
            if not self.history:
                raise RuntimeError("Nothing to undo")
            self.mapping = self.history.pop()
            self.pipeline.update_mapping(self.mapping)
            self._record("undo", None, "Reverted to previous snapshot")
            self._mirror_to_osc("undo")
            return self.mapping

    def save(self, path: Optional[Path] = None, message: str = "") -> Path:
        dest = path or self.mapping_path
        with self.lock:
            yaml.safe_dump(self.mapping, dest.open("w", encoding="utf-8"), sort_keys=False)
            self.baseline_text = dest.read_text(encoding="utf-8")
            self._record("save", None, message or f"Saved to {dest}")
        return dest

    def send_test(self, frame: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        frame = frame or demo_frame(_dt.datetime.now().timestamp())
        payload = self.pipeline.process_frame(frame)
        self.pipeline.emit_osc(payload)
        self.set_last_payload(payload)
        self._record("osc-test", None, json.dumps(payload.get("axes", {})))
        return payload

    def _mirror_to_osc(self, axis: str) -> None:
        # For tiny controllers we just send a mid-point ping to the axis that moved.
        if not self.pipeline.has_osc_client:
            return
        axes = {axis: 0.5}
        payload = {"t": self._stamp(), "axes": axes}
        self.pipeline.emit_osc(payload)
        self.last_payload = payload


# ---------------------------------------------------------------------------
# FastAPI factory
# ---------------------------------------------------------------------------

def build_api(pipeline: MappingPipeline, mapping_path: Path) -> FastAPI:
    state = MappingState(pipeline, mapping_path)
    app = FastAPI(title="Room Lens mapping workbench", version="0.2")
    app.state.mapping_state = state

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:  # pragma: no cover - HTML shell only
        return _HTML_SHELL

    @app.get("/mappings")
    def get_mappings() -> Dict[str, Any]:
        return {
            "routes": state.routes(),
            "mapping": state.mapping,
            "log": state.log,
            "last_payload": state.last_payload,
        }

    @app.get("/diff")
    def get_diff() -> Dict[str, Any]:
        return {"diff": state.diff()}

    @app.get("/log")
    def get_log() -> Dict[str, Any]:
        return {"log": state.log}

    @app.patch("/axis/{axis}")
    def patch_axis(axis: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        range_values = None
        if "range" in payload:
            rng = payload.get("range")
            if isinstance(rng, Iterable):
                rng_list = list(rng)
                if len(rng_list) == 2:
                    range_values = (float(rng_list[0]), float(rng_list[1]))
        expo = payload.get("expo")
        offset = payload.get("offset")
        updated = state.patch_axis(axis, range_values=range_values, expo=expo, offset=offset)
        return {"mapping": updated, "routes": state.routes()}

    @app.post("/undo")
    def undo() -> Dict[str, Any]:
        try:
            mapping = state.undo()
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"mapping": mapping, "routes": state.routes()}

    @app.post("/send-test")
    def send_test(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return state.send_test(payload)

    @app.post("/save")
    def save(payload: Dict[str, Any]) -> Dict[str, Any]:
        dest = payload.get("path")
        message = payload.get("message", "")
        path_obj = Path(dest) if dest else mapping_path
        saved_path = state.save(path_obj, message)
        return {"saved": str(saved_path)}

    return app


# Minimal HTML/JS shell so users get a browser-native inspector without PyQt.
_HTML_SHELL = """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Room Lens mapper</title>
  <style>
    body { font-family: Inter, Arial, sans-serif; margin: 1.5rem; background: #0d0d0f; color: #f2f2f2; }
    h1 { margin-bottom: 0.2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem; }
    .card { border: 1px solid #333; border-radius: 8px; padding: 0.75rem; background: #16171a; box-shadow: 0 8px 20px rgba(0,0,0,0.35); }
    .axis { font-weight: 700; color: #9efc9c; }
    label { display: block; font-size: 0.85rem; margin-top: 0.35rem; }
    input[type=\"range\"] { width: 100%; }
    .meta { color: #aaa; font-size: 0.85rem; }
    .log { background: #111; padding: 0.75rem; border-radius: 8px; height: 200px; overflow-y: scroll; border: 1px solid #333; }
    button { background: #f83e8c; color: #fff; border: none; padding: 0.6rem 1rem; border-radius: 6px; cursor: pointer; }
    button.secondary { background: #444; }
    pre { white-space: pre-wrap; font-size: 0.85rem; }
  </style>
</head>
<body>
  <h1>Room Lens mapping inspector</h1>
  <p class=\"meta\">Live OSC tweaks, panic/undo, and a log for workshop post-mortems.</p>
  <div style=\"margin:0.5rem 0 1rem;\">
    <button onclick=\"panicUndo()\">Panic / Undo</button>
    <button class=\"secondary\" onclick=\"sendTest()\">Send OSC test ping</button>
    <button class=\"secondary\" onclick=\"saveYaml()\">Save to YAML</button>
    <button class=\"secondary\" onclick=\"fetchDiff()\">Show diff</button>
  </div>
  <div id=\"routes\" class=\"grid\"></div>
  <h3>Edit log</h3>
  <div id=\"log\" class=\"log\"></div>
  <h3>Diff preview</h3>
  <pre id=\"diff\">(empty)</pre>
<script>
async function loadMappings() {
  const res = await fetch('/mappings');
  const data = await res.json();
  renderRoutes(data.routes);
  renderLog(data.log);
}

function renderRoutes(routes) {
  const container = document.getElementById('routes');
  container.innerHTML = '';
  routes.forEach((r, idx) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="meta">${r.sensor} → <span class="axis">${r.axis}</span></div>
      <div>${r.label}</div>
      <div class="meta">transform: ${r.transform || 'identity'}</div>
      <label>min: <input type="number" step="0.01" value="${r.range[0]}" id="min-${idx}"></label>
      <label>max: <input type="number" step="0.01" value="${r.range[1]}" id="max-${idx}"></label>
      <label>expo: <input type="number" step="0.1" value="${r.expo}" id="expo-${idx}"></label>
      <label>offset: <input type="number" step="0.01" value="${r.offset}" id="offset-${idx}"></label>
      <button onclick="apply(${idx}, '${r.axis}')">Apply</button>
      <div class="meta">${r.notes || ''}</div>
    `;
    container.appendChild(card);
  });
}

async function apply(idx, axis) {
  const payload = {
    range: [parseFloat(document.getElementById(`min-${idx}`).value), parseFloat(document.getElementById(`max-${idx}`).value)],
    expo: parseFloat(document.getElementById(`expo-${idx}`).value),
    offset: parseFloat(document.getElementById(`offset-${idx}`).value)
  };
  await fetch(`/axis/${axis}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  loadMappings();
}

async function panicUndo() {
  await fetch('/undo', { method: 'POST' });
  loadMappings();
}

async function sendTest() {
  await fetch('/send-test', { method: 'POST' });
  loadMappings();
}

async function saveYaml() {
  const message = prompt('Add a save note (e.g., show, workshop):', '');
  await fetch('/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }) });
  fetchDiff();
}

async function fetchDiff() {
  const res = await fetch('/diff');
  const data = await res.json();
  document.getElementById('diff').textContent = data.diff || '(no changes)';
}

function renderLog(entries) {
  const logBox = document.getElementById('log');
  logBox.innerHTML = entries.map(e => `${e.t} — ${e.action}${e.axis ? ' ['+e.axis+']' : ''} ${e.detail || ''}`).join('\n');
}

loadMappings();
</script>
</body>
</html>
"""
