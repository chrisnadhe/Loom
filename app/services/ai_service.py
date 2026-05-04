import os
from litellm import completion
from dotenv import load_dotenv
import json

load_dotenv()

class AIService:
    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "google_gemini")
        self.model = os.getenv("AI_MODEL", "gemini/gemini-1.5-flash")
        
    async def suggest_mappings(self, columns: list, variables: list):
        prompt = f"""
        You are a network automation assistant. 
        I have a data source with these columns: {columns}
        And a Jinja2 template with these variables: {variables}
        
        Please suggest a mapping from template variables to data columns.
        Return ONLY a raw JSON object. No markdown, no explanations.
        
        Example: {{"hostname": "DeviceName", "ip_address": "IP"}}
        """
        
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content
            # Clean up potential markdown formatting
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except Exception as e:
            print(f"AI Mapping Error: {e}")
            return {}

    async def generate_template(self, config_snippet: str):
        prompt = f"""
        Convert the following network configuration snippet into a Jinja2 template.
        Identify the parts that should be variables and use double curly braces.
        
        Snippet:
        {config_snippet}
        
        Return only the Jinja2 template string.
        """
        
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"AI Template Error: {e}")
            return config_snippet
