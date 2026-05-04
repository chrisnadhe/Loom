from pydantic import BaseModel, Field, validator, field_validator
from typing import List, Optional, Literal, Union
import re

class VlanModel(BaseModel):
    id: str = Field(..., pattern=r"^[0-9]+$")
    name: str
    ip_addr: Optional[str] = None
    mask: Optional[str] = None
    desc: Optional[str] = None

class EtherchannelModel(BaseModel):
    id: str = Field(..., pattern=r"^[0-9]+$")
    type: Literal["L2", "l2", "L3", "l3"]
    mode: Optional[str] = None
    access_vlan: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    native_vlan: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    allowed_vlans: Optional[str] = None
    ip_addr: Optional[str] = None
    mask: Optional[str] = None
    desc: Optional[str] = None

class InterfaceModel(BaseModel):
    name: str = Field(..., pattern=r"^[\D+\d+((/\d+)+(\.\d+)?)?]+$")
    mode: str
    access_vlan: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    voice_vlan: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    native_vlan: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    allowed_vlans: Optional[str] = None
    portfast: Optional[Literal["yes", "no"]] = None
    bpduguard: Optional[Literal["yes", "no"]] = None
    portsecurity: Optional[Literal["yes", "no"]] = None
    description: Optional[str] = None

class ConfigModel(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=63, pattern=r"^[A-Za-z0-9_-]+$")
    timezone: str
    domain_name: str = Field(..., pattern=r"^\S+$")
    stp_mode: Literal["pvst", "rapid-pvst", "mst"]
    vtp_domain: Optional[str] = None
    vtp_version: Optional[Literal["1", "2", "3"]] = None
    vtp_mode: Literal["client", "server", "transparent", "off"]
    logging_console: Optional[str] = None
    logging_buffer_size: Optional[str] = None
    http_server: Optional[Literal["yes", "no"]] = None
    errdisable: Optional[Literal["yes", "no"]] = None
    errdisable_recovery_interval: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    lldp: Optional[Literal["yes", "no"]] = None
    username: str
    algorithm_type: Literal["scrypt", "sha256"]
    password: str
    enable_password: Optional[str] = None
    ssh_key_size: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    ssh_version: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    vty_lines: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    login_local: Optional[Literal["yes", "no"]] = None
    timeout: Optional[str] = Field(None, pattern=r"^[0-9]*$")
    transport_input: Optional[Literal["ssh", "telnet", "all"]] = None
    transport_output: Optional[Literal["ssh", "telnet", "all"]] = None
    
    vlans: List[VlanModel] = []
    etherchannels: List[EtherchannelModel] = []
    interfaces: List[InterfaceModel] = []

class ConfigValidator:
    @staticmethod
    def validate(data: dict) -> dict:
        try:
            model = ConfigModel(**data)
            return {"is_valid": True, "errors": {}}
        except Exception as e:
            # Format Pydantic errors for easier reading
            errors = {}
            if hasattr(e, "errors"):
                for err in e.errors():
                    loc = " -> ".join([str(x) for x in err["loc"]])
                    errors[loc] = err["msg"]
            else:
                errors["general"] = str(e)
            return {"is_valid": False, "errors": errors}
