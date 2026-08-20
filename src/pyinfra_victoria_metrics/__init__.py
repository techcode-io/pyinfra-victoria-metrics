from pyinfra_victoria_metrics.facts import VictoriaMetricsVersion, VMAlertVersion
from pyinfra_victoria_metrics.tasks import (
    DEFAULT_MAX_OPEN_FILES,
    DEFAULT_SERVICE_ARGS,
    DEFAULT_SYSTEM_GROUP,
    DEFAULT_SYSTEM_USER,
    DEFAULT_VERSION,
    DEFAULT_VMALERT_SERVICE_ARGS,
    install,
    uninstall,
)

__all__ = [
    "DEFAULT_MAX_OPEN_FILES",
    "DEFAULT_SERVICE_ARGS",
    "DEFAULT_SYSTEM_GROUP",
    "DEFAULT_SYSTEM_USER",
    "DEFAULT_VERSION",
    "DEFAULT_VMALERT_SERVICE_ARGS",
    "VMAlertVersion",
    "VictoriaMetricsVersion",
    "install",
    "uninstall",
]
