import os
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.services.data_processor import DataProcessor
from app.services.template_engine import TemplateEngine
from app.services.ai_service import AIService
from app.models.database import engine as engine_db
from app.models.config import Configuration
from sqlmodel import Session

router = APIRouter(prefix="/api")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
template_engine_service = TemplateEngine()
ai = AIService()

# In-memory storage for prototype (Replace with Redis/Session in Phase 3)
LAST_UPLOADED_DATA = {}

def clean_val(val):
    """Helper to convert any value (including NaN/None/Float) to a cleaned string.
    Specifically handles floats that are actually integers (e.g., 10.0 -> '10').
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    
    # Handle floats that are mathematically integers (e.g., 10.0)
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
        
    return str(val).strip()

@router.get("/download-template/{file_type}")
async def download_template(file_type: str):
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    
    file_type = file_type.lower()
    if file_type == "params":
        headers = [
            "hostname", "timezone", "domain_name", "stp_mode", "vtp_domain", "vtp_version", "vtp_mode",
            "logging_console", "logging_buffer_size", "http_server", "errdisable", "errdisable_recovery_interval",
            "lldp", "username", "algorithm_type", "password", "enable_password", "ssh_key_size", "ssh_version",
            "vty_lines", "login_local", "timeout", "transport_input", "transport_output"
        ]
        sample_data = [
            ["Switch-01", "GMT +7", "loom.local", "rapid-pvst", "LOOM", "3", "server", "7", "8192", "no", "yes", "300", "yes", "admin", "scrypt", "Cisco123!", "Enable123!", "2048", "2", "15", "yes", "5", "ssh", "all"]
        ]
        filename = "01_params.xlsx"
    elif file_type == "vlans":
        headers = ["hostname", "id", "name", "ip_addr", "mask", "desc"]
        sample_data = [
            ["Switch-01", "10", "USERS", "192.168.10.1", "255.255.255.0", "User VLAN"],
            ["Switch-01", "20", "SERVERS", "192.168.20.1", "255.255.255.0", "Server VLAN"]
        ]
        filename = "02_vlans.xlsx"
    elif file_type == "etherchannels":
        headers = ["hostname", "id", "type", "mode", "access_vlan", "native_vlan", "allowed_vlans", "ip_addr", "mask", "desc"]
        sample_data = [
            ["Switch-01", "1", "L2", "trunk", "", "1", "all", "", "", "Core Uplink"]
        ]
        filename = "03_etherchannels.xlsx"
    elif file_type == "ports":
        headers = ["hostname", "name", "mode", "access_vlan", "voice_vlan", "native_vlan", "allowed_vlans", "portfast", "bpduguard", "portsecurity", "description"]
        sample_data = [
            ["Switch-01", "GigabitEthernet0/1", "access", "10", "100", "", "", "yes", "yes", "yes", "User Port"],
            ["Switch-01", "GigabitEthernet0/2", "trunk", "", "", "1", "all", "no", "no", "no", "Uplink"]
        ]
        filename = "04_port_mapping.xlsx"
    else:
        return {"error": "Invalid template type"}
        
    df = pd.DataFrame(sample_data, columns=headers)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/upload", response_class=HTMLResponse)
async def upload_file(
    request: Request, 
    global_file: UploadFile = File(...),
    port_file: UploadFile = File(...),
    vlan_file: UploadFile = File(None),
    etherchannel_file: UploadFile = File(None)
):
    form_data = await request.form()
    device_type = form_data.get("device_type")
    
    global_content = await global_file.read()
    port_content = await port_file.read()
    
    vlan_content = await vlan_file.read() if vlan_file and vlan_file.filename else None
    etherchannel_content = await etherchannel_file.read() if etherchannel_file and etherchannel_file.filename else None
    
    try:
        global_result = await DataProcessor.process_file(global_content, global_file.filename)
        port_result = await DataProcessor.process_file(port_content, port_file.filename)
        
        vlan_result = await DataProcessor.process_file(vlan_content, vlan_file.filename) if vlan_content else {"data": [], "columns": []}
        ether_result = await DataProcessor.process_file(etherchannel_content, etherchannel_file.filename) if etherchannel_content else {"data": [], "columns": []}
        
        # Merge logic: Group data by hostname
        from collections import defaultdict
        ports_by_hostname = defaultdict(list)
        for row in port_result["data"]:
            hn = str(row.get("hostname", "")).strip()
            if hn: ports_by_hostname[hn].append(row)
            
        vlans_by_hostname = defaultdict(list)
        for row in vlan_result["data"]:
            hn = str(row.get("hostname", "")).strip()
            if hn: vlans_by_hostname[hn].append(row)
            
        ether_by_hostname = defaultdict(list)
        for row in ether_result["data"]:
            hn = str(row.get("hostname", "")).strip()
            if hn: ether_by_hostname[hn].append(row)
        
        # Attach nested data to global devices
        merged_data = []
        for device in global_result["data"]:
            hn = str(device.get("hostname", "")).strip()
            device["interfaces"] = ports_by_hostname.get(hn, [])
            device["vlans"] = vlans_by_hostname.get(hn, [])
            device["etherchannels"] = ether_by_hostname.get(hn, [])
            merged_data.append(device)
            
        # Store for mapping step
        LAST_UPLOADED_DATA["global_columns"] = global_result["columns"]
        LAST_UPLOADED_DATA["port_columns"] = port_result["columns"]
        LAST_UPLOADED_DATA["vlan_columns"] = vlan_result["columns"]
        LAST_UPLOADED_DATA["ether_columns"] = ether_result["columns"]
        
        # Consolidated columns list for mapping
        all_cols = global_result["columns"] + port_result["columns"] + vlan_result["columns"] + ether_result["columns"]
        LAST_UPLOADED_DATA["columns"] = list(dict.fromkeys(all_cols))
        
        LAST_UPLOADED_DATA["data"] = merged_data
        LAST_UPLOADED_DATA["validation"] = global_result["validation"]
        LAST_UPLOADED_DATA["device_type"] = device_type
        
        filenames = [global_file.filename, port_file.filename]
        if vlan_file and vlan_file.filename: filenames.append(vlan_file.filename)
        if etherchannel_file and etherchannel_file.filename: filenames.append(etherchannel_file.filename)

        return templates.TemplateResponse(
            request,
            "components/data_preview.html", 
            {
                "columns": global_result["columns"], 
                "data": merged_data, 
                "validation": global_result["validation"],
                "filename": " + ".join(filenames),
                "row_count": len(merged_data),
                "device_type": device_type
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f'<div class="p-4 bg-red-100 text-red-700 rounded-xl border border-red-200">Error processing files: {str(e)}</div>'

@router.post("/mapping", response_class=HTMLResponse)
async def get_mapping_ui(request: Request):
    form_data = await request.form()
    template_name = form_data.get("template") # This is the base name, e.g., 'cisco_ios'
    
    if not template_name:
        return '<div class="p-4 bg-amber-100 text-amber-700 rounded-xl">Please select a template first.</div>'
    
    # Handle 'complete' templates (which contain everything in one file)
    if template_name.endswith("_complete"):
        complete_tpl = f"{template_name}.j2"
        all_vars = []
        try: all_vars = template_engine_service.get_template_variables(complete_tpl)
        except: pass
        
        # Categorize variables
        COLLECTIONS = ["vlans", "etherchannels", "interfaces"]
        global_vars = [v for v in all_vars if v not in COLLECTIONS and not any(v.startswith(p) for p in ["vlan.", "portchannel.", "port."])]
        vlan_vars = [v for v in all_vars if v.startswith("vlan.")]
        ether_vars = [v for v in all_vars if v.startswith("portchannel.")]
        interface_vars = [v for v in all_vars if v.startswith("port.")]
        
        return templates.TemplateResponse(
            request,
            "components/mapping_ui.html",
            {
                "template_name": template_name,
                "global_vars": global_vars,
                "vlan_vars": vlan_vars,
                "ether_vars": ether_vars,
                "interface_vars": interface_vars,
                "global_columns": LAST_UPLOADED_DATA.get("global_columns", []),
                "vlan_columns": LAST_UPLOADED_DATA.get("vlan_columns", []),
                "ether_columns": LAST_UPLOADED_DATA.get("ether_columns", []),
                "port_columns": LAST_UPLOADED_DATA.get("port_columns", []),
                "columns": LAST_UPLOADED_DATA.get("columns", [])
            }
        )

    # Fallback to split templates (Legacy)
    global_tpl = f"{template_name}_global.j2"
    interface_tpl = f"{template_name}_interface.j2"
    
    global_vars = []
    try: global_vars = template_engine_service.get_template_variables(global_tpl)
    except: pass
        
    interface_vars = []
    try: interface_vars = template_engine_service.get_template_variables(interface_tpl)
    except: pass

    return templates.TemplateResponse(
        request,
        "components/mapping_ui.html",
        {
            "template_name": template_name,
            "global_vars": global_vars,
            "interface_vars": interface_vars,
            "columns": LAST_UPLOADED_DATA.get("columns", []),
            "global_columns": LAST_UPLOADED_DATA.get("global_columns", []),
            "port_columns": LAST_UPLOADED_DATA.get("port_columns", [])
        }
    )

@router.post("/ai/suggest-mapping", response_class=HTMLResponse)
async def ai_suggest_mapping(request: Request):
    form_data = await request.form()
    template_name = form_data.get("template")
    
    if not template_name:
        return "Select template first."
        
    all_vars = []
    vlan_vars = []
    ether_vars = []
    interface_vars = []
    global_vars = []
    
    if template_name.endswith("_complete"):
        tpl_path = f"{template_name}.j2"
        try: all_vars = template_engine_service.get_template_variables(tpl_path)
        except: pass
        COLLECTIONS = ["vlans", "etherchannels", "interfaces"]
        global_vars = [v for v in all_vars if v not in COLLECTIONS and not any(v.startswith(p) for p in ["vlan.", "portchannel.", "port."])]
        vlan_vars = [v for v in all_vars if v.startswith("vlan.")]
        ether_vars = [v for v in all_vars if v.startswith("portchannel.")]
        interface_vars = [v for v in all_vars if v.startswith("port.")]
    else:
        global_tpl = f"{template_name}_global.j2"
        interface_tpl = f"{template_name}_interface.j2"
        try: global_vars = template_engine_service.get_template_variables(global_tpl)
        except: pass
        try: interface_vars = template_engine_service.get_template_variables(interface_tpl)
        except: pass
        all_vars = global_vars + interface_vars

    columns = LAST_UPLOADED_DATA.get("columns", [])
    
    # Call AI with merged variables for suggestions
    suggestions = await ai.suggest_mappings(columns, all_vars)
    
    return templates.TemplateResponse(
        request,
        "components/mapping_form.html",
        {
            "template_name": template_name,
            "global_vars": global_vars,
            "vlan_vars": vlan_vars,
            "ether_vars": ether_vars,
            "interface_vars": interface_vars,
            "columns": columns,
            "global_columns": LAST_UPLOADED_DATA.get("global_columns", []),
            "vlan_columns": LAST_UPLOADED_DATA.get("vlan_columns", []),
            "ether_columns": LAST_UPLOADED_DATA.get("ether_columns", []),
            "port_columns": LAST_UPLOADED_DATA.get("port_columns", []),
            "suggestions": suggestions
        }
    )

@router.post("/preview-configs", response_class=HTMLResponse)
async def preview_configs(request: Request):
    form_data = await request.form()
    template_name = form_data.get("template") # Base name
    
    if not template_name:
        return "No template selected."

    mappings = {k.replace("map_", ""): v for k, v in form_data.items() if k.startswith("map_")}
    results = []
    
    from app.services.validator import ConfigValidator

    # Logic for Complete Templates
    if template_name.endswith("_complete"):
        tpl_path = f"{template_name}.j2"
        all_vars = template_engine_service.get_template_variables(tpl_path)
        
        for i, device in enumerate(LAST_UPLOADED_DATA["data"]):
            context = {}
            # 1. Map Global Vars
            for var in all_vars:
                if not any(var.startswith(p) for p in ["vlan.", "portchannel.", "port."]):
                    col = mappings.get(var)
                    if col: context[var] = clean_val(device.get(col, ""))

            # 2. Map VLANs
            context["vlans"] = []
            for vlan_row in device.get("vlans", []):
                v_ctx = {}
                for var in all_vars:
                    if var.startswith("vlan."):
                        _, attr = var.split(".", 1)
                        col = mappings.get(var)
                        if col: v_ctx[attr] = clean_val(vlan_row.get(col, ""))
                if v_ctx: context["vlans"].append(v_ctx)

            # 3. Map Etherchannels
            context["etherchannels"] = []
            for eth_row in device.get("etherchannels", []):
                e_ctx = {}
                for var in all_vars:
                    if var.startswith("portchannel."):
                        _, attr = var.split(".", 1)
                        col = mappings.get(var)
                        if col: e_ctx[attr] = clean_val(eth_row.get(col, ""))
                if e_ctx: context["etherchannels"].append(e_ctx)

            # 4. Map Interfaces
            context["interfaces"] = []
            for port_row in device.get("interfaces", []):
                p_ctx = {}
                for var in all_vars:
                    if var.startswith("port."):
                        _, attr = var.split(".", 1)
                        col = mappings.get(var)
                        if col: p_ctx[attr] = clean_val(port_row.get(col, ""))
                if p_ctx: context["interfaces"].append(p_ctx)

            # 5. Validate with Pydantic
            validation = ConfigValidator.validate(context)
            v_errors = ""
            if not validation["is_valid"]:
                v_errors = "! Validation Errors:\n" + "\n".join([f"! - {k}: {v}" for k, v in validation["errors"].items()]) + "\n"

            # 6. Render
            try:
                config = template_engine_service.render(tpl_path, context)
                if v_errors:
                    config = v_errors + config
            except Exception as e:
                config = f"! Error rendering: {str(e)}\n"
            
            name = context.get("hostname", f"config_{i+1}")
            results.append({"name": name, "content": config})
            
    else:
        # Legacy split logic
        global_tpl = f"{template_name}_global.j2"
        interface_tpl = f"{template_name}_interface.j2"
        # ... (rest of legacy logic remains as is)
        for i, device in enumerate(LAST_UPLOADED_DATA["data"]):
            # (Simplified for brevity, I'll keep the original logic here but wrapped in else)
            # ... (I'll actually just provide the full replacement for the legacy part too to be safe)
            global_vars = []
            try: global_vars = template_engine_service.get_template_variables(global_tpl)
            except: pass
            interface_vars = []
            try: interface_vars = template_engine_service.get_template_variables(interface_tpl)
            except: pass

            global_context = {}
            for var in global_vars:
                col = mappings.get(var)
                if col: global_context[var] = clean_val(device.get(col, ""))
            
            try: global_config = template_engine_service.render(global_tpl, global_context)
            except Exception as e: global_config = f"! Error: {str(e)}\n"

            interface_configs = []
            for port in device.get("interfaces", []):
                port_context = {}
                for var in interface_vars:
                    col = mappings.get(var)
                    if col:
                        if "." in var: _, attr = var.split(".", 1); port_context[attr] = clean_val(port.get(col, ""))
                        else: port_context[var] = clean_val(port.get(col, ""))
                try: interface_configs.append(template_engine_service.render(interface_tpl, port_context))
                except: pass
            
            final_content = global_config.strip() + "\n" + "\n".join([ic.strip() for ic in interface_configs])
            name = global_context.get("hostname", f"config_{i+1}")
            results.append({"name": name, "content": final_content + "\n"})
    
    LAST_UPLOADED_DATA["preview_results"] = results
    return templates.TemplateResponse(
        request,
        "components/config_preview.html",
        {"results": results, "template_name": template_name}
    )

@router.post("/generate", response_class=HTMLResponse)
async def generate_configs(request: Request):
    form_data = await request.form()
    
    # In this step, we take the EDITED content from the form
    # The form will have fields like 'config_content_0', 'config_name_0', etc.
    
    results = []
    i = 0
    while f"config_content_{i}" in form_data:
        if form_data.get(f"approved_{i}") == "on":
            name = form_data.get(f"config_name_{i}")
            content = form_data.get(f"config_content_{i}")
            results.append({"name": name, "content": content})
            
            # Save to DB
            with Session(engine_db) as session:
                db_config = Configuration(template_id=1, device_name=name, generated_content=content)
                session.add(db_config)
                session.commit()
        i += 1
    
    LAST_UPLOADED_DATA["last_results"] = results

    return templates.TemplateResponse(
        request,
        "components/generation_results.html",
        {"results": results}
    )

@router.get("/download-zip")
async def download_zip():
    import zipfile
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    
    if not LAST_UPLOADED_DATA.get("data"):
        return {"error": "No data available to download"}

    # We need the results again. In a real app, we'd pull from DB or cache results.
    # For now, I'll just assume we want to download what was just generated.
    # Note: This is a simplified version for the prototype.
    
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # For simplicity, we'll re-render or pull from a global cache of the last run.
        # Let's assume we store the results in LAST_UPLOADED_DATA during /generate.
        results = LAST_UPLOADED_DATA.get("last_results", [])
        for item in results:
            zip_file.writestr(f"{item['name']}.txt", item["content"])
    
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": "attachment; filename=loom_configs.zip"}
    )
