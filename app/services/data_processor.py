import pandas as pd
from io import BytesIO
import json

class DataProcessor:
    @staticmethod
    async def process_file(content: bytes, filename: str) -> dict:
        import io
        import pandas as pd
        
        file_io = io.BytesIO(content)
        if filename.endswith('.csv'):
            # Smart delimiter detection
            df = pd.read_csv(file_io, sep=None, engine='python')
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_io)
        else:
            raise ValueError("Unsupported file format")
        
        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]
        
        # Convert to list of dictionaries for Jinja2
        data = df.to_dict(orient='records')
        columns = df.columns.tolist()
        
        # Validate data
        validation_results = DataProcessor.validate_data(data)
        
        return {
            "columns": columns,
            "data": data,
            "row_count": len(df),
            "validation": validation_results
        }

    @staticmethod
    def validate_data(data: list) -> list:
        import ipaddress
        results = []
        hostnames = set()
        
        for i, row in enumerate(data):
            errors = {}
            # Required fields (can be customized or based on mapping later)
            # For initial validation, we look for common network fields
            
            hostname = str(row.get('hostname', '')).strip()
            if not hostname:
                errors['hostname'] = "Hostname is required"
            elif hostname in hostnames:
                errors['hostname'] = f"Duplicate hostname: {hostname}"
            hostnames.add(hostname)

            ip = str(row.get('ip', '')).strip()
            if ip:
                try:
                    if '/' in ip:
                        ipaddress.IPv4Interface(ip)
                    else:
                        ipaddress.IPv4Address(ip)
                except ValueError:
                    errors['ip'] = "Invalid IPv4 format"
            
            vlan = row.get('vlan')
            if vlan is not None:
                try:
                    vlan_id = int(float(vlan))
                    if not (1 <= vlan_id <= 4094):
                        errors['vlan'] = "VLAN ID must be 1-4094"
                except (ValueError, TypeError):
                    errors['vlan'] = "VLAN must be a number"

            results.append(errors)
        return results

    @staticmethod
    def get_preview(df_dict: dict, rows: int = 5):
        # Returns first N rows for preview
        return df_dict["data"][:rows]
