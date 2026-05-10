"""
Data processing utilities: file parsing, data cleaning, and device merging.
"""

import io
from collections import defaultdict
from typing import Any

import pandas as pd


def clean_val(val: Any) -> str:
    """
    Convert any value to a clean string suitable for Jinja2 template rendering.

    - None / NaN → empty string ""
    - Float that is mathematically an integer (e.g. 10.0) → "10"
    - Everything else → str(val).strip()
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()


class DataProcessor:

    @staticmethod
    async def process_file(content: bytes, filename: str) -> dict:
        """
        Parse an uploaded Excel or CSV file.

        Returns a dict with keys:
            columns  : list[str]   — column names in original order
            data     : list[dict]  — rows as list of dicts
            row_count: int
            validation: list[dict] — per-row error dicts (may be empty)
        """
        file_io = io.BytesIO(content)

        if filename.endswith(".csv"):
            df = pd.read_csv(file_io, sep=None, engine="python")
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_io)
        else:
            raise ValueError(f"Unsupported file format: {filename!r}")

        # Normalise column names
        df.columns = [str(c).strip() for c in df.columns]

        data: list[dict] = df.to_dict(orient="records")
        columns: list[str] = df.columns.tolist()
        validation = DataProcessor._validate_hostnames(data)

        return {
            "columns": columns,
            "data": data,
            "row_count": len(df),
            "validation": validation,
        }

    @staticmethod
    def _validate_hostnames(data: list[dict]) -> list[dict]:
        """
        Light validation: only check that hostname is present and unique.
        Returning per-row error dicts (empty dict = no errors for that row).
        """
        results: list[dict] = []
        seen: set[str] = set()

        for row in data:
            errors: dict[str, str] = {}
            hostname = str(row.get("hostname", "")).strip()

            if not hostname:
                errors["hostname"] = "Hostname is required"
            elif hostname in seen:
                errors["hostname"] = f"Duplicate hostname: {hostname}"
            seen.add(hostname)

            results.append(errors)

        return results

    @staticmethod
    def merge_device_data(
        global_data: list[dict],
        port_data: list[dict],
        vlan_data: list[dict],
        ether_data: list[dict],
    ) -> list[dict]:
        """
        Group port / VLAN / etherchannel rows by hostname and attach them
        as nested lists (interfaces / vlans / etherchannels) to each device
        from the global data list.
        """

        def _group_by_hostname(rows: list[dict]) -> dict[str, list[dict]]:
            grouped: dict[str, list[dict]] = defaultdict(list)
            for row in rows:
                hn = str(row.get("hostname", "")).strip()
                if hn:
                    grouped[hn].append(row)
            return grouped

        ports_map = _group_by_hostname(port_data)
        vlans_map = _group_by_hostname(vlan_data)
        ether_map = _group_by_hostname(ether_data)

        merged: list[dict] = []
        for device in global_data:
            hn = str(device.get("hostname", "")).strip()
            device["interfaces"] = ports_map.get(hn, [])
            device["vlans"] = vlans_map.get(hn, [])
            device["etherchannels"] = ether_map.get(hn, [])
            merged.append(device)

        return merged
