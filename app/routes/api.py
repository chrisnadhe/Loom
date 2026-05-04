import os
from fastapi import APIRouter, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.services.data_processor import DataProcessor

router = APIRouter(prefix="/api")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@router.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    try:
        result = await DataProcessor.process_file(content, file.filename)
        return templates.TemplateResponse(
            request,
            "components/data_preview.html", 
            {
                "columns": result["columns"], 
                "data": result["data"][:5], # Preview first 5 rows
                "filename": file.filename,
                "row_count": result["row_count"]
            }
        )
    except Exception as e:
        return f'<div class="p-4 bg-red-100 text-red-700 rounded-xl">Error: {str(e)}</div>'
