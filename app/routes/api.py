"""
API route handlers for the Loom config generator workflow.

Flow:
    POST /api/upload          → parse files, store in session, show data_preview
    POST /api/mapping         → show variable mapping UI
    POST /api/ai/suggest-mapping → AI-suggested column→variable mapping
    POST /api/preview-configs → render Jinja2 templates with mapped data
    POST /api/ai/review-config → AI security & best-practice review
    POST /api/generate        → save to DB, show generation results
    GET  /api/download-zip    → download all last-generated configs as ZIP
    GET  /api/download-template/{type} → download blank Excel template
"""

import io
import json
import os
import zipfile
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Cookie, File, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.models.config import Configuration
from app.models.database import engine as engine_db
from app.services.ai_service import AIService
from app.services.data_processor import DataProcessor, clean_val
from app.services.session_store import COOKIE_NAME, store as session_store
from app.services.template_engine import TemplateEngine
from app.services.validator import ConfigValidator

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

_template_engine = TemplateEngine()
_ai = AIService()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLLECTIONS = {"vlans", "etherchannels", "interfaces"}
_PREFIXES = ("vlan.", "portchannel.", "port.")


def _is_global_var(var: str) -> bool:
    return var not in _COLLECTIONS and not any(var.startswith(p) for p in _PREFIXES)


def _get_session_id(loom_session: str | None) -> str:
    """Return existing session ID or create a new one."""
    if loom_session and session_store.exists(loom_session):
        return loom_session
    return session_store.create()


def _set_session_cookie(response: HTMLResponse, session_id: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
    )


def _build_config_context(device: dict, all_vars: list[str], mappings: dict) -> dict:
    """
    Build the full Jinja2 rendering context for one device by applying
    user-defined column→variable mappings across all data sources.
    """
    context: dict = {}

    # 1. Global (device-level) variables
    for var in all_vars:
        if _is_global_var(var):
            col = mappings.get(var)
            if col:
                context[var] = clean_val(device.get(col, ""))

    # 2. VLANs
    context["vlans"] = []
    for vlan_row in device.get("vlans", []):
        v_ctx: dict = {}
        for var in all_vars:
            if var.startswith("vlan."):
                _, attr = var.split(".", 1)
                col = mappings.get(var)
                if col:
                    v_ctx[attr] = clean_val(vlan_row.get(col, ""))
        if v_ctx:
            context["vlans"].append(v_ctx)

    # 3. Etherchannels
    context["etherchannels"] = []
    for eth_row in device.get("etherchannels", []):
        e_ctx: dict = {}
        for var in all_vars:
            if var.startswith("portchannel."):
                _, attr = var.split(".", 1)
                col = mappings.get(var)
                if col:
                    e_ctx[attr] = clean_val(eth_row.get(col, ""))
        if e_ctx:
            context["etherchannels"].append(e_ctx)

    # 4. Interfaces
    context["interfaces"] = []
    for port_row in device.get("interfaces", []):
        p_ctx: dict = {}
        for var in all_vars:
            if var.startswith("port."):
                _, attr = var.split(".", 1)
                col = mappings.get(var)
                if col:
                    p_ctx[attr] = clean_val(port_row.get(col, ""))
        if p_ctx:
            context["interfaces"].append(p_ctx)

    return context


# ---------------------------------------------------------------------------
# Template downloads
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Shared (vendor-agnostic) column definitions — column names are identical
# across all platforms; only sample values differ.
# ---------------------------------------------------------------------------

_CISCO_PARAMS_HEADERS = [
    "hostname", "timezone", "domain_name", "stp_mode", "vtp_domain",
    "vtp_version", "vtp_mode", "logging_console", "logging_buffer_size",
    "http_server", "errdisable", "errdisable_recovery_interval", "lldp",
    "username", "algorithm_type", "password", "enable_password",
    "ssh_key_size", "ssh_version", "vty_lines", "login_local", "timeout",
    "transport_input", "transport_output",
]

_ARISTA_PARAMS_HEADERS = [
    "hostname", "timezone", "domain_name", "stp_mode", "lldp",
    "logging_console", "logging_buffer_size", "http_server",
    "username", "algorithm_type", "password", "enable_password",
    "ssh_key_size", "ssh_version", "vty_lines", "timeout",
]

_ARUBA_PARAMS_HEADERS = [
    "hostname", "timezone", "domain_name", "stp_mode", "lldp",
    "logging_console", "logging_buffer_size", "http_server",
    "username", "algorithm_type", "password",
    "ssh_key_size", "ssh_version", "vty_lines", "timeout",
]

_VLAN_HEADERS = ["hostname", "id", "name", "ip_addr", "mask", "desc"]
_ETHERCHANNEL_HEADERS = [
    "hostname", "id", "type", "mode", "access_vlan", "native_vlan",
    "allowed_vlans", "ip_addr", "mask", "desc",
]

_TEMPLATE_DEFINITIONS: dict[str, tuple[list[str], list[list], str]] = {
    # ------------------------------------------------------------------
    # Generic / Cisco IOS style
    # ------------------------------------------------------------------
    "params": (
        _CISCO_PARAMS_HEADERS,
        [[
            "Switch-01", "GMT +7", "loom.local", "rapid-pvst", "LOOM", "3",
            "server", "7", "8192", "no", "yes", "300", "yes", "admin", "scrypt",
            "Cisco123!", "Enable123!", "2048", "2", "15", "yes", "5", "ssh", "all",
        ]],
        "01_params.xlsx",
    ),
    "vlans": (
        _VLAN_HEADERS,
        [
            ["Switch-01", "10", "USERS", "192.168.10.1", "255.255.255.0", "User VLAN"],
            ["Switch-01", "20", "SERVERS", "192.168.20.1", "255.255.255.0", "Server VLAN"],
        ],
        "02_vlans.xlsx",
    ),
    "etherchannels": (
        _ETHERCHANNEL_HEADERS,
        [["Switch-01", "1", "L2", "trunk", "", "1", "all", "", "", "Core Uplink"]],
        "03_etherchannels.xlsx",
    ),
    "ports": (
        ["hostname", "name", "mode", "access_vlan", "voice_vlan", "native_vlan",
         "allowed_vlans", "portfast", "bpduguard", "portsecurity", "description"],
        [
            ["Switch-01", "GigabitEthernet0/1", "access", "10", "100", "", "", "yes", "yes", "yes", "User Port"],
            ["Switch-01", "GigabitEthernet0/2", "trunk", "", "", "1", "all", "no", "no", "no", "Uplink"],
        ],
        "04_port_mapping.xlsx",
    ),
    # ------------------------------------------------------------------
    # Arista EOS — params only differ (no VTP); ports use Ethernet1 style
    # ------------------------------------------------------------------
    "arista-params": (
        _ARISTA_PARAMS_HEADERS,
        [["Arista-01", "GMT +7", "loom.local", "rapid-pvst", "yes",
          "7", "8192", "no", "admin", "sha256", "Arista123!", "Enable123!",
          "2048", "2", "15", "5"]],
        "01_arista_params.xlsx",
    ),
    "arista-vlans": (
        _VLAN_HEADERS,
        [
            ["Arista-01", "10", "USERS", "192.168.10.1", "24", "User VLAN"],
            ["Arista-01", "20", "SERVERS", "192.168.20.1", "24", "Server VLAN"],
        ],
        "02_arista_vlans.xlsx",
    ),
    "arista-etherchannels": (
        _ETHERCHANNEL_HEADERS,
        [["Arista-01", "1", "L2", "trunk", "", "1", "all", "", "", "Core Uplink"]],
        "03_arista_etherchannels.xlsx",
    ),
    "arista-ports": (
        ["hostname", "name", "mode", "access_vlan", "voice_vlan", "native_vlan",
         "allowed_vlans", "portfast", "bpduguard", "portsecurity", "description"],
        [
            ["Arista-01", "Ethernet1", "access", "10", "", "", "", "yes", "yes", "no", "User Port"],
            ["Arista-01", "Ethernet2", "trunk", "", "", "1", "all", "no", "no", "no", "Uplink"],
        ],
        "04_arista_port_mapping.xlsx",
    ),
    # ------------------------------------------------------------------
    # Aruba AOS-CX — params differ (no VTP/errdisable); ports use 1/1/x style
    # ------------------------------------------------------------------
    "aruba-params": (
        _ARUBA_PARAMS_HEADERS,
        [["Aruba-01", "GMT +7", "loom.local", "rapid-pvst", "yes",
          "6", "8192", "yes", "admin", "sha256", "Aruba123!",
          "2048", "2", "15", "5"]],
        "01_aruba_params.xlsx",
    ),
    "aruba-vlans": (
        _VLAN_HEADERS,
        [
            ["Aruba-01", "10", "USERS", "192.168.10.1", "24", "User VLAN"],
            ["Aruba-01", "20", "SERVERS", "192.168.20.1", "24", "Server VLAN"],
        ],
        "02_aruba_vlans.xlsx",
    ),
    "aruba-etherchannels": (
        _ETHERCHANNEL_HEADERS,
        [["Aruba-01", "1", "L2", "trunk", "", "1", "all", "", "", "Core Uplink"]],
        "03_aruba_etherchannels.xlsx",
    ),
    "aruba-ports": (
        ["hostname", "name", "mode", "access_vlan", "voice_vlan", "native_vlan",
         "allowed_vlans", "portfast", "bpduguard", "portsecurity", "description"],
        [
            ["Aruba-01", "1/1/1", "access", "10", "", "", "", "yes", "yes", "no", "User Port"],
            ["Aruba-01", "1/1/2", "trunk", "", "", "1", "all", "no", "no", "no", "Uplink"],
        ],
        "04_aruba_port_mapping.xlsx",
    ),
}


@router.get("/download-template/{file_type}")
async def download_template(file_type: str):
    definition = _TEMPLATE_DEFINITIONS.get(file_type.lower())
    if not definition:
        return {"error": f"Unknown template type: {file_type!r}"}

    headers, sample_data, filename = definition
    df = pd.DataFrame(sample_data, columns=headers)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# Step 1 — Upload & parse
# ---------------------------------------------------------------------------

@router.post("/upload", response_class=HTMLResponse)
async def upload_file(
    request: Request,
    global_file: UploadFile = File(...),
    port_file: UploadFile = File(...),
    vlan_file: UploadFile = File(None),
    etherchannel_file: UploadFile = File(None),
    loom_session: str | None = Cookie(default=None),
):
    session_id = _get_session_id(loom_session)
    form_data = await request.form()
    device_type: str = form_data.get("device_type", "")

    try:
        global_bytes = await global_file.read()
        port_bytes = await port_file.read()
        vlan_bytes = await vlan_file.read() if vlan_file and vlan_file.filename else None
        ether_bytes = await etherchannel_file.read() if etherchannel_file and etherchannel_file.filename else None

        global_result = await DataProcessor.process_file(global_bytes, global_file.filename)
        port_result = await DataProcessor.process_file(port_bytes, port_file.filename)
        vlan_result = (
            await DataProcessor.process_file(vlan_bytes, vlan_file.filename)
            if vlan_bytes else {"data": [], "columns": [], "validation": []}
        )
        ether_result = (
            await DataProcessor.process_file(ether_bytes, etherchannel_file.filename)
            if ether_bytes else {"data": [], "columns": [], "validation": []}
        )

        merged_data = DataProcessor.merge_device_data(
            global_data=global_result["data"],
            port_data=port_result["data"],
            vlan_data=vlan_result["data"],
            ether_data=ether_result["data"],
        )

        # Deduplicated column list for fallback dropdowns
        all_cols = (
            global_result["columns"]
            + port_result["columns"]
            + vlan_result["columns"]
            + ether_result["columns"]
        )

        session_store.update(session_id, {
            "global_columns": global_result["columns"],
            "port_columns": port_result["columns"],
            "vlan_columns": vlan_result["columns"],
            "ether_columns": ether_result["columns"],
            "columns": list(dict.fromkeys(all_cols)),
            "data": merged_data,
            "validation": global_result["validation"],
            "device_type": device_type,
        })

        filenames = [global_file.filename, port_file.filename]
        if vlan_file and vlan_file.filename:
            filenames.append(vlan_file.filename)
        if etherchannel_file and etherchannel_file.filename:
            filenames.append(etherchannel_file.filename)

        response = templates.TemplateResponse(
            request,
            "components/data_preview.html",
            {
                "columns": global_result["columns"],
                "data": merged_data,
                "validation": global_result["validation"],
                "filename": " + ".join(filenames),
                "row_count": len(merged_data),
                "device_type": device_type,
            },
        )
        _set_session_cookie(response, session_id)
        return response

    except Exception as exc:
        import traceback
        traceback.print_exc()
        response = HTMLResponse(
            content=f'<div class="p-4 bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-xl border border-red-200 dark:border-red-800"><strong>Error processing files:</strong> {exc}</div>'
        )
        _set_session_cookie(response, session_id)
        return response


# ---------------------------------------------------------------------------
# Step 2 — Variable mapping UI
# ---------------------------------------------------------------------------

def _categorise_vars(all_vars: list[str]) -> dict[str, list[str]]:
    return {
        "global_vars": [v for v in all_vars if _is_global_var(v)],
        "vlan_vars": [v for v in all_vars if v.startswith("vlan.")],
        "ether_vars": [v for v in all_vars if v.startswith("portchannel.")],
        "interface_vars": [v for v in all_vars if v.startswith("port.")],
    }


@router.post("/mapping", response_class=HTMLResponse)
async def get_mapping_ui(
    request: Request,
    loom_session: str | None = Cookie(default=None),
):
    session_id = _get_session_id(loom_session)
    sess = session_store.get(session_id)
    form_data = await request.form()
    template_name: str = form_data.get("template", "")

    if not template_name:
        return HTMLResponse('<div class="p-4 bg-amber-100 text-amber-700 rounded-xl">Please select a template first.</div>')

    tpl_path = f"{template_name}.j2"
    try:
        all_vars = _template_engine.get_template_variables(tpl_path)
    except Exception as exc:
        return HTMLResponse(f'<div class="p-4 bg-red-100 text-red-700 rounded-xl">Template error: {exc}</div>')

    ctx = {
        "template_name": template_name,
        **_categorise_vars(all_vars),
        "global_columns": sess.get("global_columns", []),
        "vlan_columns": sess.get("vlan_columns", []),
        "ether_columns": sess.get("ether_columns", []),
        "port_columns": sess.get("port_columns", []),
        "columns": sess.get("columns", []),
    }
    response = templates.TemplateResponse(request, "components/mapping_ui.html", ctx)
    _set_session_cookie(response, session_id)
    return response


# ---------------------------------------------------------------------------
# AI — suggest mappings
# ---------------------------------------------------------------------------

@router.post("/ai/suggest-mapping", response_class=HTMLResponse)
async def ai_suggest_mapping(
    request: Request,
    loom_session: str | None = Cookie(default=None),
):
    session_id = _get_session_id(loom_session)
    sess = session_store.get(session_id)
    form_data = await request.form()
    template_name: str = form_data.get("template", "")

    if not template_name:
        return HTMLResponse("Select a template first.")

    tpl_path = f"{template_name}.j2"
    try:
        all_vars = _template_engine.get_template_variables(tpl_path)
    except Exception:
        all_vars = []

    columns = sess.get("columns", [])
    suggestions = await _ai.suggest_mappings(columns, all_vars)

    ctx = {
        "template_name": template_name,
        **_categorise_vars(all_vars),
        "global_columns": sess.get("global_columns", []),
        "vlan_columns": sess.get("vlan_columns", []),
        "ether_columns": sess.get("ether_columns", []),
        "port_columns": sess.get("port_columns", []),
        "columns": columns,
        "suggestions": suggestions,
    }
    response = templates.TemplateResponse(request, "components/mapping_form.html", ctx)
    _set_session_cookie(response, session_id)
    return response


# ---------------------------------------------------------------------------
# Step 3 — Preview generated configs
# ---------------------------------------------------------------------------

@router.post("/preview-configs", response_class=HTMLResponse)
async def preview_configs(
    request: Request,
    loom_session: str | None = Cookie(default=None),
):
    session_id = _get_session_id(loom_session)
    sess = session_store.get(session_id)
    form_data = await request.form()
    template_name: str = form_data.get("template", "")

    if not template_name:
        return HTMLResponse("No template selected.")

    mappings = {
        k.replace("map_", "", 1): v
        for k, v in form_data.items()
        if k.startswith("map_")
    }

    tpl_path = f"{template_name}.j2"
    try:
        all_vars = _template_engine.get_template_variables(tpl_path)
    except Exception as exc:
        return HTMLResponse(f'<div class="p-4 bg-red-100 text-red-700 rounded-xl">Template error: {exc}</div>')

    results: list[dict] = []
    for i, device in enumerate(sess.get("data", [])):
        context = _build_config_context(device, all_vars, mappings)

        # Pydantic validation (warnings only)
        validation = ConfigValidator.validate(context)
        v_header = ""
        if not validation["is_valid"]:
            v_header = (
                "! Validation Warnings:\n"
                + "\n".join(f"! - {k}: {v}" for k, v in validation["errors"].items())
                + "\n"
            )

        try:
            rendered = _template_engine.render(tpl_path, context)
            config_content = v_header + rendered if v_header else rendered
        except Exception as exc:
            config_content = f"! Error rendering template: {exc}\n"

        name = context.get("hostname") or f"config_{i + 1}"
        results.append({"name": name, "content": config_content})

    session_store.set(session_id, "preview_results", results)
    session_store.set(session_id, "template_name", template_name)

    response = templates.TemplateResponse(
        request,
        "components/config_preview.html",
        {"results": results, "template_name": template_name},
    )
    _set_session_cookie(response, session_id)
    return response


# ---------------------------------------------------------------------------
# AI — review a single config
# ---------------------------------------------------------------------------

@router.post("/ai/review-config", response_class=HTMLResponse)
async def ai_review_config(
    request: Request,
    loom_session: str | None = Cookie(default=None),
):
    session_id = _get_session_id(loom_session)
    sess = session_store.get(session_id)
    form_data = await request.form()

    config_text: str = form_data.get("config_content", "")
    config_name: str = form_data.get("config_name", "config")
    os_type: str = sess.get("device_type", "cisco_ios")

    if not config_text.strip():
        return HTMLResponse('<div class="p-4 text-slate-500">No configuration content to review.</div>')

    review = await _ai.review_config(config_text, os_type)

    response = templates.TemplateResponse(
        request,
        "components/ai_review_panel.html",
        {"review": review, "config_name": config_name},
    )
    _set_session_cookie(response, session_id)
    return response


# ---------------------------------------------------------------------------
# Step 4 — Confirm & save to DB
# ---------------------------------------------------------------------------

@router.post("/generate", response_class=HTMLResponse)
async def generate_configs(
    request: Request,
    loom_session: str | None = Cookie(default=None),
):
    session_id = _get_session_id(loom_session)
    sess = session_store.get(session_id)
    form_data = await request.form()

    os_type = sess.get("device_type", "")
    template_name = sess.get("template_name", "")
    results: list[dict] = []

    i = 0
    while f"config_content_{i}" in form_data:
        if form_data.get(f"approved_{i}") == "on":
            name = form_data.get(f"config_name_{i}", f"config_{i}")
            content = form_data.get(f"config_content_{i}", "")
            results.append({"name": name, "content": content})

            try:
                with Session(engine_db) as db_session:
                    db_config = Configuration(
                        device_name=name,
                        os_type=os_type,
                        template_name=template_name,
                        generated_content=content,
                    )
                    db_session.add(db_config)
                    db_session.commit()
            except Exception as exc:
                print(f"[DB] Failed to save config for {name!r}: {exc}")
        i += 1

    session_store.set(session_id, "last_results", results)

    response = templates.TemplateResponse(
        request,
        "components/generation_results.html",
        {"results": results},
    )
    _set_session_cookie(response, session_id)
    return response


# ---------------------------------------------------------------------------
# Download ZIP
# ---------------------------------------------------------------------------

@router.get("/download-zip")
async def download_zip(loom_session: str | None = Cookie(default=None)):
    session_id = _get_session_id(loom_session)
    sess = session_store.get(session_id)
    results = sess.get("last_results", [])

    if not results:
        return HTMLResponse(
            '<div class="p-4 text-red-500">No configs available. Please generate configs first.</div>'
        )

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in results:
            zf.writestr(f"{item['name']}.txt", item["content"])
    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": "attachment; filename=loom_configs.zip"},
    )


# ---------------------------------------------------------------------------
# Download single config (from generation results)
# ---------------------------------------------------------------------------

@router.get("/download-single")
async def download_single(name: str, loom_session: str | None = Cookie(default=None)):
    session_id = _get_session_id(loom_session)
    sess = session_store.get(session_id)
    results = sess.get("last_results", [])

    target = next((r for r in results if r["name"] == name), None)
    if not target:
        return HTMLResponse('<div class="p-4 text-red-500">Config not found.</div>')

    content_bytes = target["content"].encode("utf-8")
    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={name}.txt"},
    )
