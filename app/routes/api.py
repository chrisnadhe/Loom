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

@router.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    try:
        result = await DataProcessor.process_file(content, file.filename)
        available_templates = template_engine_service.list_available_templates()
        
        # Store for mapping step
        LAST_UPLOADED_DATA["columns"] = result["columns"]
        LAST_UPLOADED_DATA["data"] = result["data"]
        
        return templates.TemplateResponse(
            request,
            "components/data_preview.html", 
            {
                "columns": result["columns"], 
                "data": result["data"][:5], 
                "filename": file.filename,
                "row_count": result["row_count"],
                "templates": available_templates
            }
        )
    except Exception as e:
        return f'<div class="p-4 bg-red-100 text-red-700 rounded-xl">Error: {str(e)}</div>'

@router.post("/mapping", response_class=HTMLResponse)
async def get_mapping_ui(request: Request):
    form_data = await request.form()
    template_name = form_data.get("template")
    
    if not template_name:
        return '<div class="p-4 bg-amber-100 text-amber-700 rounded-xl">Please select a template first.</div>'
    
    variables = engine.get_template_variables(template_name)
    columns = LAST_UPLOADED_DATA.get("columns", [])
    
    return templates.TemplateResponse(
        request,
        "components/mapping_ui.html",
        {
            "template_name": template_name,
            "variables": variables,
            "columns": columns
        }
    )

@router.post("/ai/suggest-mapping", response_class=HTMLResponse)
async def ai_suggest_mapping(request: Request):
    form_data = await request.form()
    template_name = form_data.get("template")
    
    if not template_name:
        return "Select template first."
        
    variables = template_engine_service.get_template_variables(template_name)
    columns = LAST_UPLOADED_DATA.get("columns", [])
    
    # Call AI
    suggestions = await ai.suggest_mappings(columns, variables)
    
    return templates.TemplateResponse(
        request,
        "components/mapping_form.html",
        {
            "template_name": template_name,
            "variables": variables,
            "columns": columns,
            "suggestions": suggestions
        }
    )

@router.post("/generate", response_class=HTMLResponse)
async def generate_configs(request: Request):
    form_data = await request.form()
    template_name = form_data.get("template")
    
    if not template_name or not LAST_UPLOADED_DATA.get("data"):
        return '<div class="p-4 bg-red-100 text-red-700 rounded-xl">Missing data or template selection.</div>'

    # Build mapping dict
    mappings = {k.replace("map_", ""): v for k, v in form_data.items() if k.startswith("map_")}
    
    results = []
    with Session(engine_db) as session:
        for i, row in enumerate(LAST_UPLOADED_DATA["data"]):
            context = {}
            for var, col in mappings.items():
                if col and col in row:
                    context[var] = row[col]
                else:
                    context[var] = f"MISSING_{var.upper()}"
            
            try:
                content = template_engine_service.render(template_name, context)
                name = context.get("hostname", f"config_{i+1}")
                
                # Save to DB
                db_config = Configuration(
                    template_id=1, 
                    device_name=name,
                    generated_content=content
                )
                session.add(db_config)
                results.append({"name": name, "content": content})
            except Exception as e:
                results.append({"name": f"Error_{i+1}", "content": f"Rendering Error: {str(e)}"})
        
        session.commit()
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
