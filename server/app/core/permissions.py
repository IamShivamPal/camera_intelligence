"""
Role-based access control (RBAC) hierarchy and capability definitions
for Camera Intelligence.
"""

from enum import Enum


class SystemRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    LOCATION_ADMIN = "location_admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# Hierarchy numeric levels: higher value means higher authority
ROLE_HIERARCHY: dict[str, int] = {
    SystemRole.SUPER_ADMIN.value: 40,
    SystemRole.LOCATION_ADMIN.value: 30,
    SystemRole.OPERATOR.value: 20,
    SystemRole.VIEWER.value: 10,
}

# Explicit functional capabilities granted to each role
ROLE_CAPABILITIES: dict[str, set[str]] = {
    SystemRole.SUPER_ADMIN.value: {
        "global_admin",
        "manage_users",
        "manage_system_settings",
        "manage_locations",
        "manage_cameras",
        "manage_zones",
        "manage_schedules",
        "manage_employees",
        "manage_embeddings",
        "triage_alerts",
        "view_telemetry",
        "view_reports",
    },
    SystemRole.LOCATION_ADMIN.value: {
        "manage_assigned_locations",
        "manage_cameras",
        "manage_zones",
        "manage_employees",
        "manage_embeddings",
        "triage_alerts",
        "view_telemetry",
        "view_reports",
    },
    SystemRole.OPERATOR.value: {
        "triage_alerts",
        "acknowledge_alerts",
        "resolve_alerts",
        "view_telemetry",
        "view_reports",
    },
    SystemRole.VIEWER.value: {
        "view_telemetry",
        "view_reports",
    },
}


def has_minimum_role(user_role: str, minimum_role: str) -> bool:
    """
    Check if user_role meets or exceeds minimum_role in the defined hierarchy:
    super_admin (40) >= location_admin (30) >= operator (20) >= viewer (10)
    """
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)
    return user_level >= min_level


def has_exact_role(user_role: str, allowed_roles: set[str] | list[str]) -> bool:
    """Check if user_role matches any role in allowed_roles exactly."""
    return user_role in allowed_roles


def has_capability(user_role: str, capability: str) -> bool:
    """Check if user_role explicitly has the named functional capability."""
    return capability in ROLE_CAPABILITIES.get(user_role, set())

