import re

from pyinfra.api import FactBase

VM_BINARY_PATH = "/usr/local/bin/victoria-metrics"
VMALERT_BINARY_PATH = "/usr/local/bin/vmalert"

_VERSION_MATCHER = re.compile(r"tags-(?P<version>v\d+\.\d+\.\d+)")


class VictoriaMetricsVersion(FactBase):
    """
    Returns the currently installed VictoriaMetrics version (eg ``v1.133.0``), or ``None`` if
    VictoriaMetrics is not installed.
    """

    def command(self) -> str:
        return f"{VM_BINARY_PATH} --version 2>&1"

    def requires_command(self) -> str:
        return VM_BINARY_PATH

    def process(self, output) -> str | None:
        match = _VERSION_MATCHER.search("\n".join(output))
        return match.group("version") if match else None


class VMAlertVersion(FactBase):
    """
    Returns the currently installed vmalert version (eg ``v1.133.0``), or ``None`` if vmalert is
    not installed.
    """

    def command(self) -> str:
        return f"{VMALERT_BINARY_PATH} --version 2>&1"

    def requires_command(self) -> str:
        return VMALERT_BINARY_PATH

    def process(self, output) -> str | None:
        match = _VERSION_MATCHER.search("\n".join(output))
        return match.group("version") if match else None
