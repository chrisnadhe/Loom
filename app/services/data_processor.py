import pandas as pd
from io import BytesIO
import json

class DataProcessor:
    @staticmethod
    async def process_file(file_content: bytes, filename: str):
        if filename.endswith('.csv'):
            df = pd.read_csv(BytesIO(file_content))
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(BytesIO(file_content))
        else:
            raise ValueError("Unsupported file format")
        
        # Convert to list of dictionaries for Jinja2
        data = df.to_dict(orient='records')
        columns = df.columns.tolist()
        
        return {
            "columns": columns,
            "data": data,
            "row_count": len(df)
        }

    @staticmethod
    def get_preview(df_dict: dict, rows: int = 5):
        # Returns first N rows for preview
        return df_dict["data"][:rows]
