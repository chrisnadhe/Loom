"""
AI service: mapping suggestions and config review via LiteLLM.
"""

import json
import os

from dotenv import load_dotenv
from litellm import completion

load_dotenv()


class AIService:

    def __init__(self) -> None:
        self.model: str = os.getenv("AI_MODEL", "gemini/gemini-1.5-flash")

    # ------------------------------------------------------------------
    # Mapping suggestions
    # ------------------------------------------------------------------

    async def suggest_mappings(
        self, columns: list[str], variables: list[str]
    ) -> dict[str, str]:
        """
        Ask the AI to suggest column→variable mappings.
        Returns a dict like {"hostname": "Device Name", ...}.
        Falls back to {} on any error.
        """
        prompt = (
            "You are a network automation assistant.\n"
            f"Data source columns: {columns}\n"
            f"Jinja2 template variables: {variables}\n\n"
            "Suggest a mapping from template variable → data column.\n"
            "Return ONLY a raw JSON object. No markdown, no explanation.\n"
            'Example: {"hostname": "DeviceName", "ip_address": "IP"}'
        )

        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            content: str = response.choices[0].message.content
            content = self._strip_markdown(content)
            return json.loads(content.strip())
        except Exception as exc:
            print(f"[AI] suggest_mappings error: {exc}")
            return {}

    # ------------------------------------------------------------------
    # Config review
    # ------------------------------------------------------------------

    async def review_config(
        self, config_text: str, os_type: str = "cisco_ios"
    ) -> dict:
        """
        Analyse a generated CLI config and return structured feedback.

        Returns:
        {
            "security_score": int (0-100),
            "grade": str ("Excellent" | "Good" | "Fair" | "Poor"),
            "summary": str,
            "issues": [{"severity": "critical"|"warning"|"info", "message": str}],
            "suggestions": [str],
        }
        Falls back to an error-indicator dict on failure.
        """
        prompt = (
            f"You are a senior network security engineer reviewing a {os_type.replace('_', ' ').upper()} CLI configuration.\n\n"
            "Analyze the following configuration for:\n"
            "1. Security vulnerabilities (e.g. Telnet enabled, weak passwords, missing ACLs)\n"
            "2. Best practice violations (e.g. missing domain name, STP not hardened)\n"
            "3. Operational risks (e.g. LLDP enabled on untrusted ports)\n\n"
            "Respond ONLY with a raw JSON object (no markdown) in this exact schema:\n"
            "{\n"
            '  "security_score": <int 0-100>,\n'
            '  "grade": "<Excellent|Good|Fair|Poor>",\n'
            '  "summary": "<one paragraph summary>",\n'
            '  "issues": [\n'
            '    {"severity": "<critical|warning|info>", "message": "<description>"}\n'
            "  ],\n"
            '  "suggestions": ["<actionable recommendation>", ...]\n'
            "}\n\n"
            "Configuration to review:\n"
            "```\n"
            f"{config_text}\n"
            "```"
        )

        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            content = self._strip_markdown(content)
            result = json.loads(content.strip())
            # Ensure required keys exist
            result.setdefault("security_score", 0)
            result.setdefault("grade", "Unknown")
            result.setdefault("summary", "No summary available.")
            result.setdefault("issues", [])
            result.setdefault("suggestions", [])
            return result
        except Exception as exc:
            print(f"[AI] review_config error: {exc}")
            return {
                "security_score": 0,
                "grade": "Error",
                "summary": f"AI review failed: {exc}",
                "issues": [{"severity": "info", "message": "Could not connect to AI service."}],
                "suggestions": [],
            }

    # ------------------------------------------------------------------
    # Template generation (legacy helper)
    # ------------------------------------------------------------------

    async def generate_template(self, config_snippet: str) -> str:
        """Convert a raw config snippet into a Jinja2 template."""
        prompt = (
            "Convert the following network configuration snippet into a Jinja2 template.\n"
            "Replace variable parts with {{ variable_name }} placeholders.\n"
            "Return only the Jinja2 template string.\n\n"
            f"Snippet:\n{config_snippet}"
        )
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except Exception as exc:
            print(f"[AI] generate_template error: {exc}")
            return config_snippet

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove ```json ... ``` fences from AI responses."""
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text
