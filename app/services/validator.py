"""
Pydantic-based validator for generated device configuration contexts.

Validation is intentionally lenient — all fields except hostname are optional.
This ensures validation never blocks config generation; it only surfaces warnings.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class VlanModel(BaseModel):
    id: str = Field(..., pattern=r"^[0-9]+$")
    name: Optional[str] = None
    ip_addr: Optional[str] = None
    mask: Optional[str] = None
    desc: Optional[str] = None


class EtherchannelModel(BaseModel):
    id: str = Field(..., pattern=r"^[0-9]+$")
    type: Optional[Literal["L2", "l2", "L3", "l3"]] = None
    mode: Optional[str] = None
    access_vlan: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    native_vlan: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    allowed_vlans: Optional[str] = None
    ip_addr: Optional[str] = None
    mask: Optional[str] = None
    desc: Optional[str] = None


class InterfaceModel(BaseModel):
    name: Optional[str] = None
    mode: Optional[str] = None
    access_vlan: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    voice_vlan: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    native_vlan: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    allowed_vlans: Optional[str] = None
    portfast: Optional[Literal["yes", "no"]] = None
    bpduguard: Optional[Literal["yes", "no"]] = None
    portsecurity: Optional[Literal["yes", "no"]] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Top-level config model
# ---------------------------------------------------------------------------

class ConfigModel(BaseModel):
    # Only hostname is mandatory
    hostname: str = Field(..., min_length=1, max_length=63)

    # Global settings — all optional to support multiple OS types
    timezone: Optional[str] = None
    domain_name: Optional[str] = None
    stp_mode: Optional[Literal["pvst", "rapid-pvst", "mst"]] = None
    vtp_domain: Optional[str] = None
    vtp_version: Optional[Literal["1", "2", "3"]] = None
    vtp_mode: Optional[Literal["client", "server", "transparent", "off"]] = None
    logging_console: Optional[str] = None
    logging_buffer_size: Optional[str] = None
    http_server: Optional[Literal["yes", "no"]] = None
    errdisable: Optional[Literal["yes", "no"]] = None
    errdisable_recovery_interval: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    lldp: Optional[Literal["yes", "no"]] = None
    username: Optional[str] = None
    algorithm_type: Optional[Literal["scrypt", "sha256"]] = None
    password: Optional[str] = None
    enable_password: Optional[str] = None
    ssh_key_size: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    ssh_version: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    vty_lines: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    login_local: Optional[Literal["yes", "no"]] = None
    timeout: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    transport_input: Optional[Literal["ssh", "telnet", "all"]] = None
    transport_output: Optional[Literal["ssh", "telnet", "all"]] = None

    # Nested lists
    vlans: List[VlanModel] = []
    etherchannels: List[EtherchannelModel] = []
    interfaces: List[InterfaceModel] = []


# ---------------------------------------------------------------------------
# Validator class
# ---------------------------------------------------------------------------

class ConfigValidator:

    @staticmethod
    def validate(data: dict) -> dict:
        """
        Validate a config context dict against ConfigModel.

        Returns:
            {"is_valid": bool, "errors": dict[str, str]}
        """
        try:
            ConfigModel(**data)
            return {"is_valid": True, "errors": {}}
        except Exception as exc:
            errors: dict[str, str] = {}
            if hasattr(exc, "errors"):
                for err in exc.errors():
                    loc = " → ".join(str(x) for x in err["loc"])
                    errors[loc] = err["msg"]
            else:
                errors["general"] = str(exc)
            return {"is_valid": False, "errors": errors}
