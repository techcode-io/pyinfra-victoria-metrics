import platform
from typing import Final

from tests.e2e.conftest import podman_exec, run_pyinfra

# VictoriaMetrics/vmalert binaries are only downloaded for linux-amd64 (matching upstream
# releases), so the services can only actually run to completion on an amd64 host; under
# emulation on other architectures (e.g. Podman on Apple Silicon) the Go runtime crashes for
# reasons unrelated to this library. Structural checks (files, user/group, systemd wiring) still
# run everywhere.
_IS_NATIVE_AMD64: Final[bool] = platform.machine() in ("x86_64", "amd64")


def assert_podman_exec(container: str, command: str, expected: int = 0) -> None:
    assert podman_exec(container, command).returncode == expected


def test_install_then_uninstall(systemd_container: str) -> None:
    install_result = run_pyinfra(systemd_container, "tasks_install.py")
    assert install_result.returncode == 0, install_result.stdout + install_result.stderr

    assert_podman_exec(systemd_container, "test -f /usr/local/bin/victoria-metrics")
    assert_podman_exec(systemd_container, "test -f /usr/local/bin/vmalert")
    assert_podman_exec(
        systemd_container, "test -f /etc/systemd/system/victoria-metrics.service"
    )
    assert_podman_exec(systemd_container, "test -f /etc/systemd/system/vmalert.service")
    assert_podman_exec(systemd_container, "id victoria-metrics")

    for service in ("victoria-metrics", "vmalert"):
        assert (
            podman_exec(
                systemd_container, f"systemctl is-enabled {service}"
            ).stdout.strip()
            == "enabled"
        )

    if _IS_NATIVE_AMD64:
        for service in ("victoria-metrics", "vmalert"):
            assert (
                podman_exec(
                    systemd_container, f"systemctl is-active {service}"
                ).stdout.strip()
                == "active"
            )

        metrics = podman_exec(systemd_container, "curl -sf 127.0.0.1:8428/metrics")
        assert metrics.returncode == 0
        assert "vm_app_version" in metrics.stdout

        vmalert_metrics = podman_exec(
            systemd_container, "curl -sf 127.0.0.1:8880/metrics"
        )
        assert vmalert_metrics.returncode == 0
        assert "vmalert_" in vmalert_metrics.stdout

        # Reinstalling the same version should skip the download entirely: the version facts
        # detect the binaries already match, so the download operations are never even added to
        # the operation graph. This only runs natively (see _IS_NATIVE_AMD64 above): the version
        # facts themselves run the (amd64-only) binaries, which also crash under emulation.
        reinstall_result = run_pyinfra(systemd_container, "tasks_install.py")
        assert reinstall_result.returncode == 0, (
            reinstall_result.stdout + reinstall_result.stderr
        )
        assert "Download VictoriaMetrics release binary" not in reinstall_result.stdout
        assert "Download vmalert release binary" not in reinstall_result.stdout

    uninstall_result = run_pyinfra(systemd_container, "tasks_uninstall.py")
    assert uninstall_result.returncode == 0, (
        uninstall_result.stdout + uninstall_result.stderr
    )

    assert_podman_exec(
        systemd_container, "test -f /usr/local/bin/victoria-metrics", expected=1
    )
    assert_podman_exec(systemd_container, "test -f /usr/local/bin/vmalert", expected=1)
    assert_podman_exec(
        systemd_container,
        "test -f /etc/systemd/system/victoria-metrics.service",
        expected=1,
    )
    assert_podman_exec(
        systemd_container,
        "test -f /etc/systemd/system/vmalert.service",
        expected=1,
    )
    assert_podman_exec(systemd_container, "id victoria-metrics", expected=1)
