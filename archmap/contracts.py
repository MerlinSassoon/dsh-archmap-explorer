"""Compatibility shim for the pre-P2.3 contract model module."""

from .config.contract_config import (
    API_EXPOSING_ROLES,
    CAPABILITY_KINDS,
    EXPOSURE_SOURCES,
    EXPOSURE_VALUES,
    PROTOCOL_CAPABILITY_KINDS,
    PROVIDER_ROLE_ORDER,
    PROVIDER_ROLE_SOURCES,
    PROVIDER_ROLES,
)
from .model.contract_model import ApiCapability, ClassUsage, ContractModel, ProviderRoleInfo

__all__ = [
    "API_EXPOSING_ROLES",
    "ApiCapability",
    "CAPABILITY_KINDS",
    "ClassUsage",
    "ContractModel",
    "EXPOSURE_SOURCES",
    "EXPOSURE_VALUES",
    "PROTOCOL_CAPABILITY_KINDS",
    "PROVIDER_ROLE_ORDER",
    "PROVIDER_ROLE_SOURCES",
    "PROVIDER_ROLES",
    "ProviderRoleInfo",
]
