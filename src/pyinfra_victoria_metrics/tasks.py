import shlex
from importlib import resources
from importlib.resources.abc import Traversable
from types import MappingProxyType
from typing import Final

from pyinfra.api import deploy
from pyinfra.context import host
from pyinfra.operations import files, server, systemd

from pyinfra_victoria_metrics.facts import (
    VM_BINARY_PATH,
    VMALERT_BINARY_PATH,
    VictoriaMetricsVersion,
    VMAlertVersion,
)

VM_UNIT_PATH: Final[str] = "/etc/systemd/system/victoria-metrics.service"
VMALERT_UNIT_PATH: Final[str] = "/etc/systemd/system/vmalert.service"
STORAGE_DIR: Final[str] = "/var/lib/victoria-metrics"
DOWNLOAD_DIR: Final[str] = "/tmp/victoria-metrics"

DEFAULT_VERSION: Final[str] = "v1.151.0"
DEFAULT_SYSTEM_USER: Final[str] = "victoria-metrics"
DEFAULT_SYSTEM_GROUP: Final[str] = "victoria-metrics"
DEFAULT_MAX_OPEN_FILES: Final[int] = 2097152
DEFAULT_SERVICE_ARGS = MappingProxyType(
    {
        "storageDataPath": f"{STORAGE_DIR}/",
        "httpListenAddr": "127.0.0.1:8428",
        "selfScrapeInterval": "30s",
        "retentionPeriod": "14d",
    }
)
DEFAULT_VMALERT_SERVICE_ARGS = MappingProxyType(
    {
        "httpListenAddr": "127.0.0.1:8880",
        "datasource.url": "http://127.0.0.1:8428",
        "remoteWrite.url": "http://127.0.0.1:8428",
        "remoteRead.url": "http://127.0.0.1:8428",
        "notifier.url": "http://127.0.0.1:9093",
    }
)

_VM_TEMPLATE: Final[Traversable] = (
    resources.files("pyinfra_victoria_metrics")
    / "templates"
    / "victoria-metrics.service.j2"
)
_VMALERT_TEMPLATE: Final[Traversable] = (
    resources.files("pyinfra_victoria_metrics") / "templates" / "vmalert.service.j2"
)


@deploy("Install VictoriaMetrics and vmalert")
def install(
    version: str = DEFAULT_VERSION,
    system_user: str = DEFAULT_SYSTEM_USER,
    system_group: str = DEFAULT_SYSTEM_GROUP,
    max_open_files: int = DEFAULT_MAX_OPEN_FILES,
    service_args: dict | None = None,
    vmalert_service_args: dict | None = None,
):
    server.group(
        name="Create VictoriaMetrics system group",
        group=system_group,
    )

    server.user(
        name="Create VictoriaMetrics system user",
        user=system_user,
        group=system_group,
        system=True,
        create_home=False,
        shell="/usr/sbin/nologin",
    )

    files.directory(
        name="Ensure existence of VictoriaMetrics storage directory",
        path=STORAGE_DIR,
        user=system_user,
        group=system_group,
        mode=755,
        present=True,
    )

    binaries_changed = (
        host.get_fact(VictoriaMetricsVersion) != version
        or host.get_fact(VMAlertVersion) != version
    )
    if binaries_changed:
        files.directory(
            name="Prepare local download path",
            path=DOWNLOAD_DIR,
            mode=755,
            present=True,
        )

        vm_archive = f"victoria-metrics-linux-amd64-{version}.tar.gz"
        vmutils_archive = f"vmutils-linux-amd64-{version}.tar.gz"

        files.download(
            name="Download VictoriaMetrics release binary",
            src=f"https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/{version}/{vm_archive}",
            dest=f"{DOWNLOAD_DIR}/{vm_archive}",
        )

        files.download(
            name="Download vmalert release binary",
            src=f"https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/{version}/{vmutils_archive}",
            dest=f"{DOWNLOAD_DIR}/{vmutils_archive}",
        )

        # files.unarchive/files.move hard-fail if their src/dest doesn't already
        # exist per a fact check, and that check runs when pyinfra builds its
        # change-detection preview (i.e. before any operation's commands have
        # actually executed) unless the deploy is run with `-y`. That makes them
        # unsafe here: the archives/binaries are created earlier in this very run.
        # server.shell has no such pre-check, so use raw commands instead.
        server.shell(
            name="Unarchive VictoriaMetrics and vmalert release binaries",
            commands=[
                f"tar -xvf {shlex.quote(f'{DOWNLOAD_DIR}/{vm_archive}')} -C {shlex.quote(DOWNLOAD_DIR)}",
                f"tar -xvf {shlex.quote(f'{DOWNLOAD_DIR}/{vmutils_archive}')} -C {shlex.quote(DOWNLOAD_DIR)}",
            ],
        )

        def move_binary(src_name: str, dest: str) -> str:
            return f"mv {shlex.quote(f'{DOWNLOAD_DIR}/{src_name}')} {shlex.quote(dest)}"

        server.shell(
            name="Copy VictoriaMetrics and vmalert binaries",
            commands=[
                move_binary("victoria-metrics-prod", VM_BINARY_PATH),
                move_binary("vmalert-prod", VMALERT_BINARY_PATH),
            ],
        )

        files.directory(name="Clear download path", path=DOWNLOAD_DIR, present=False)

    vm_unit = files.template(
        name="Copy VictoriaMetrics systemd unit file",
        src=str(_VM_TEMPLATE),
        dest=VM_UNIT_PATH,
        victoria_metrics_system_user=system_user,
        victoria_metrics_system_group=system_group,
        victoria_metrics_max_open_files=max_open_files,
        victoria_metrics_service_args=service_args
        if service_args is not None
        else DEFAULT_SERVICE_ARGS,
    )

    vmalert_unit = files.template(
        name="Copy vmalert systemd unit file",
        src=str(_VMALERT_TEMPLATE),
        dest=VMALERT_UNIT_PATH,
        vmalert_system_user=system_user,
        vmalert_system_group=system_group,
        vmalert_service_args=vmalert_service_args
        if vmalert_service_args is not None
        else DEFAULT_VMALERT_SERVICE_ARGS,
    )

    systemd.daemon_reload(name="Reload systemd daemon")

    systemd.service(
        name="Restart and enable the victoria-metrics service",
        service="victoria-metrics.service",
        running=True,
        restarted=binaries_changed or vm_unit.changed,
        enabled=True,
    )

    systemd.service(
        name="Restart and enable the vmalert service",
        service="vmalert.service",
        running=True,
        restarted=binaries_changed or vmalert_unit.changed,
        enabled=True,
    )


@deploy("Restart the VictoriaMetrics service")
def restart_victoria_metrics(restart: bool = True):
    systemd.service(
        name="Restart the victoria-metrics service",
        service="victoria-metrics.service",
        restarted=restart,
    )


@deploy("Restart the vmalert service")
def restart_vmalert(restart: bool = True):
    systemd.service(
        name="Restart the vmalert service",
        service="vmalert.service",
        restarted=restart,
    )


@deploy("Uninstall VictoriaMetrics and vmalert")
def uninstall(
    system_user: str = DEFAULT_SYSTEM_USER,
    system_group: str = DEFAULT_SYSTEM_GROUP,
):
    for service in ("victoria-metrics", "vmalert"):
        systemd.service(
            name=f"Stop and disable the {service} service",
            service=f"{service}.service",
            running=False,
            enabled=False,
        )

    files.file(
        name="Remove VictoriaMetrics systemd unit file",
        path=VM_UNIT_PATH,
        present=False,
    )

    files.file(
        name="Remove vmalert systemd unit file",
        path=VMALERT_UNIT_PATH,
        present=False,
    )

    systemd.daemon_reload(name="Reload systemd daemon")

    files.file(
        name="Remove VictoriaMetrics binary",
        path=VM_BINARY_PATH,
        present=False,
    )

    files.file(
        name="Remove vmalert binary",
        path=VMALERT_BINARY_PATH,
        present=False,
    )

    server.user(
        name="Remove VictoriaMetrics system user",
        user=system_user,
        present=False,
    )

    server.group(
        name="Remove VictoriaMetrics system group",
        group=system_group,
        present=False,
    )
