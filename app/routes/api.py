import os
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

@router.get("/download-template/{file_type}")
async def download_template(file_type: str):
    import pandas as pd
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    
    if file_type.lower() == "global":
        headers = ["hostname", "admin_user", "admin_password", "dns_domain", "default_gateway"]
        sample_data = [
            ["Switch-A", "admin", "cisco123", "loom.local", "192.168.1.254"],
            ["Switch-B", "admin", "cisco123", "loom.local", "192.168.2.254"]
        ]
        filename = "loom_global_template.xlsx"
    else:
        headers = ["hostname", "interface", "description", "vlan_mode", "vlan", "ip_address", "subnet_mask"]
        sample_data = [
            ["Switch-A", "GigabitEthernet0/1", "Uplink", "trunk", "10,20", "", ""],
            ["Switch-A", "GigabitEthernet0/2", "User", "access", "10", "192.168.10.1", "255.255.255.0"],
            ["Switch-B", "GigabitEthernet0/1", "Uplink", "trunk", "10,20", "", ""]
        ]
        filename = "loom_port_template.xlsx"
        
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
    port_file: UploadFile = File(...)
):
    form_data = await request.form()
    device_type = form_data.get("device_type")
    
    global_content = await global_file.read()
    port_content = await port_file.read()
    
    try:
        global_result = await DataProcessor.process_file(global_content, global_file.filename)
        port_result = await DataProcessor.process_file(port_content, port_file.filename)
        
        # Merge logic: Group port data by hostname
        from collections import defaultdict
        ports_by_hostname = defaultdict(list)
        for row in port_result["data"]:
            hn = str(row.get("hostname", "")).strip()
            if hn:
                ports_by_hostname[hn].append(row)
        
        # Attach ports to global devices
        merged_data = []
        for device in global_result["data"]:
            hn = str(device.get("hostname", "")).strip()
            device["interfaces"] = ports_by_hostname.get(hn, [])
            merged_data.append(device)
            
        # Store for mapping step
        LAST_UPLOADED_DATA["global_columns"] = global_result["columns"]
        LAST_UPLOADED_DATA["port_columns"] = port_result["columns"]
        LAST_UPLOADED_DATA["columns"] = list(dict.fromkeys(global_result["columns"] + port_result["columns"]))
        LAST_UPLOADED_DATA["data"] = merged_data
        LAST_UPLOADED_DATA["validation"] = global_result["validation"]
        LAST_UPLOADED_DATA["device_type"] = device_type
        
        return templates.TemplateResponse(
            request,
            "components/data_preview.html", 
            {
                "columns": global_result["columns"], 
                "data": merged_data, 
                "validation": global_result["validation"],
                "filename": f"{global_file.filename} + {port_file.filename}",
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
    
    global_tpl = f"{template_name}_global.j2"
    interface_tpl = f"{template_name}_interface.j2"
    
    global_vars = []
    try: global_vars = template_engine_service.get_template_variables(global_tpl)
    except: pass
        
    interface_vars = []
    try: interface_vars = template_engine_service.get_template_variables(interface_tpl)
    except: pass

    columns = LAST_UPLOADED_DATA.get("columns", [])
    global_columns = LAST_UPLOADED_DATA.get("global_columns", [])
    port_columns = LAST_UPLOADED_DATA.get("port_columns", [])
    
    return templates.TemplateResponse(
        request,
        "components/mapping_ui.html",
        {
            "template_name": template_name,
            "global_vars": global_vars,
            "interface_vars": interface_vars,
            "columns": columns,
            "global_columns": global_columns,
            "port_columns": port_columns
        }
    )

@router.post("/ai/suggest-mapping", response_class=HTMLResponse)
async def ai_suggest_mapping(request: Request):
    form_data = await request.form()
    template_name = form_data.get("template")
    
    if not template_name:
        return "Select template first."
        
    global_tpl = f"{template_name}_global.j2"
    interface_tpl = f"{template_name}_interface.j2"
    
    global_vars = []
    try: global_vars = template_engine_service.get_template_variables(global_tpl)
    except: pass
    
    interface_vars = []
    try: interface_vars = template_engine_service.get_template_variables(interface_tpl)
    except: pass

    columns = LAST_UPLOADED_DATA.get("columns", [])
    global_columns = LAST_UPLOADED_DATA.get("global_columns", [])
    port_columns = LAST_UPLOADED_DATA.get("port_columns", [])
    
    # Call AI with merged variables for suggestions
    suggestions = await ai.suggest_mappings(columns, global_vars + interface_vars)
    
    return templates.TemplateResponse(
        request,
        "components/mapping_form.html",
        {
            "template_name": template_name,
            "global_vars": global_vars,
            "interface_vars": interface_vars,
            "columns": columns,
            "global_columns": global_columns,
            "port_columns": port_columns,
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
    
    global_tpl = f"{template_name}_global.j2"
    interface_tpl = f"{template_name}_interface.j2"
    
    # Identify which variables belong to which template
    try:
        global_vars = template_engine_service.get_template_variables(global_tpl)
    except:
        global_vars = []
        
    try:
        interface_vars = template_engine_service.get_template_variables(interface_tpl)
    except:
        interface_vars = []
    
    for i, device in enumerate(LAST_UPLOADED_DATA["data"]):
        # 1. Generate Global Part
        global_context = {}
        for var in global_vars:
            col = mappings.get(var)
            if col:
                global_context[var] = device.get(col, "")
        
        try:
            global_config = template_engine_service.render(global_tpl, global_context)
        except Exception as e:
            global_config = f"! Error rendering global config: {str(e)}\n"

        # 2. Generate Interfaces Part
        interface_configs = []
        for port in device.get("interfaces", []):
            port_context = {}
            for var in interface_vars:
                col = mappings.get(var)
                if col:
                    # For attributes like intf.Interface, our extractor returns 'intf.Interface'
                    # but the template snippet is just {{ Interface }}.
                    # We need to handle both cases.
                    if "." in var:
                        _, attr = var.split(".", 1)
                        port_context[attr] = port.get(col, "")
                    elif "[" in var:
                        import re
                        match = re.search(r"\[['\"](.+?)['\"]\]", var)
                        if match:
                            attr = match.group(1)
                            port_context[attr] = port.get(col, "")
                    else:
                        port_context[var] = port.get(col, "")
            
            try:
                interface_configs.append(template_engine_service.render(interface_tpl, port_context))
            except Exception as e:
                interface_configs.append(f"! Error rendering interface: {str(e)}\n")
        
        # 3. Combine
        # Strip trailing newlines to avoid double spacing
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
