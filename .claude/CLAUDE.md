# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`pyinfra-victoria-metrics` is a [pyinfra](https://pyinfra.com) extension package: it exposes
`install()` / `uninstall()` deploy functions that another pyinfra project imports to manage
VictoriaMetrics (single-node) and vmalert on a host, instead of copy-pasting task files. It
follows pyinfra's `pyinfra_*` extension convention — deploy functions wrapped in `@deploy(...)`
from `pyinfra.api`, taking explicit keyword arguments rather than reading `host.data`, so the
caller's inventory model stays decoupled from this library. It's the sibling project to
[pyinfra-node-exporter](https://github.com/techcode-io/pyinfra-node-exporter) — same architecture,
same conventions, extended to two binaries/services instead of one.

## Commands

Managed with `uv`; a `poethepoet` task runner wraps the common commands (`pyproject.toml`
`[tool.poe.tasks]`):

- `uv sync` — install/update the dev environment
- `uv run poe lint` (or `uv run ruff check src`) — lint
- `uv run poe fmt` — fix import order + format (`ruff check --select I --fix` then `ruff format`)
- `uv run poe test` (or `uv run pytest tests`) — run the test suite
- `uv run pytest tests/e2e/test_tasks.py::test_install_then_uninstall -v` — run the single e2e test
- `uv run poe env:configure` — install pre-commit hooks (ruff-check, ruff-format, LF line endings,
  gitlint) for local development

Always invoke tools through `uv run <tool>` (or the `poe` tasks above). Do not call
`.venv/bin/<tool>` directly — `uv run` is what keeps the environment synced with `pyproject.toml`/
`uv.lock` before running, so a stale `.venv` doesn't silently mask dependency changes.

## Architecture

Source lives under `src/pyinfra_victoria_metrics/` (src layout, `uv_build` backend):

- **`tasks.py`** — the public deploy functions: `install()`, `uninstall()`,
  `restart_victoria_metrics()`, and `restart_vmalert()`. `install()` is idempotent and does
  everything in one call: creates the shared system user/group, ensures the storage directory,
  downloads/installs both the `victoria-metrics` and `vmalert` `linux-amd64` binaries (only when
  needed — see below), renders both systemd units from the bundled Jinja templates, and
  enables/starts both services, restarting each only when its binary was upgraded or its rendered
  unit changed. `install()` has no visibility into the scrape/rule *content* the caller's own
  project deploys separately (out of scope by design — see below); the expected flow is `install()`
  once — which also leaves the `victoria-metrics` system group in place for the caller's config
  deploy to `chown` its files to — then deploy that config, then call
  `restart_victoria_metrics(restart=...)` / `restart_vmalert(restart=...)` wired to the `.changed`
  result of that config deploy, so the restart only fires when the config actually changed — see
  README. `uninstall()` reverses all of it *except* the storage directory — data is intentionally
  left behind so an uninstall doesn't destroy metrics. Deliberately *not* split into separate
  install/configure steps otherwise, same reasoning as pyinfra-node-exporter.
- **`facts.py`** — `VictoriaMetricsVersion` and `VMAlertVersion`, pyinfra `FactBase`s that run
  `<binary> --version` and parse the installed version, each gated by `requires_command` so they
  return `None` cleanly when the binary isn't present yet. Also owns `VM_BINARY_PATH` /
  `VMALERT_BINARY_PATH`, the path constants shared with `tasks.py` (imported from there, not the
  other way — `facts.py` has no dependency on `tasks.py`, keep it that way to avoid a circular
  import). `install()` calls both facts and skips the entire download/unarchive/copy block only
  when *both* already match the requested `version` — a single shared `version` parameter drives
  both, matching how VictoriaMetrics tags both binaries from the same release.
- **`templates/victoria-metrics.service.j2`**, **`templates/vmalert.service.j2`** — the systemd
  unit templates, resolved via `importlib.resources.files("pyinfra_victoria_metrics")` (not a
  `__file__`-relative path) so it works both editable and installed as a wheel.
- **`__init__.py`** — re-exports the public surface: `install`, `uninstall`,
  `VictoriaMetricsVersion`, `VMAlertVersion`, and the `DEFAULT_*` constants.

The library only ever downloads `linux-amd64` release binaries (matching the upstream
VictoriaMetrics release layout it was extracted from) — this is intentional, not an oversight; add
arch support only if actually asked for.

**Config content is out of scope on purpose.** This library doesn't manage `-promscrape.config` /
`-rule` file *content* (scrape targets, alerting rules) — only the flags pointing at those paths.
That's a deliberate decision (not an oversight): the caller's own pyinfra project deploys and owns
that config, same as it deploys anything else host-specific. Don't add scrape/rule template
rendering here even if a reference deploy script does it inline — that coupling is exactly what
this package exists to avoid. One consequence: `vmalert` requires a non-empty `-rule` flag to even
start, so `DEFAULT_VMALERT_SERVICE_ARGS` deliberately has no `rule` key — callers must supply one
pointing at a file they manage. The e2e test fixture (`tests/fixtures/tasks_install.py`) writes a
minimal placeholder rule file itself for exactly this reason; don't mistake that for the library
managing rule content. `examples/scrape.yaml` and `examples/rules.yml` are copy-paste starting
points for callers (referenced from the README) — not something the library reads, ships in the
wheel, or deploys itself; they exist purely as documentation.

## Testing

`tests/e2e/` runs the deploy functions against a **real systemd** container via pyinfra's native
`@podman` connector (not `@docker` — podman is what's available/aliased in this environment;
`pyinfra @podman/<container>` works because pyinfra ships a `PodmanConnector`). This is necessary
because the whole point of `install()`/`uninstall()` is systemd unit management, which a bare
Docker container can't exercise.

- `tests/fixtures/systemd/Containerfile` builds a minimal systemd-enabled Debian 12 image.
- `tests/e2e/conftest.py`'s `systemd_container` fixture builds that image, starts a
  `--privileged --cgroupns=host` container with `/sys/fs/cgroup` mounted, polls
  `systemctl is-system-running` until ready, and yields the container name; the whole module
  auto-skips (with a clear reason) if `podman` isn't installed or its machine/socket isn't
  reachable.
- `tests/e2e/test_tasks.py` invokes the real `pyinfra` CLI (via `run_pyinfra()`, a subprocess
  helper) against `@podman/<container>` running `tests/fixtures/tasks_install.py` /
  `tasks_uninstall.py`, then asserts on-disk/systemd state via `podman exec`.

**Architecture caveat baked into the tests:** the downloaded binaries are amd64-only, so on a
non-amd64 host (e.g. Podman-on-Apple-Silicon via emulation) the Go runtime crashes for reasons
unrelated to this library (a `taggedPointerPack` Go runtime issue under QEMU/Rosetta emulation).
Structural assertions (files/user/group/units present, services enabled) run unconditionally; the
assertions that require actually *running* the binaries (services `active`, `/metrics`
responding, and the reinstall-skips-download check, since the version facts themselves exec the
binaries) are gated behind `_IS_NATIVE_AMD64 = platform.machine() in ("x86_64", "amd64")` in
`test_tasks.py`. When debugging a failure on Apple Silicon, don't assume it's a real regression —
check whether it's this known emulation crash first (look for `taggedPointerPack` in the output).

CI (`.github/workflows/ci.yml`) installs `podman` via `apt-get` before the test job for exactly
this reason — skip that step and the e2e test still "passes" by doing nothing.

On macOS, a stopped podman machine (`podman machine start`) looks identical to podman being
absent — `_podman_available()` returns `False` either way and the module just skips.

`subprocess.run` calls where `check=` is supplied dynamically through `**kwargs` (see
`direct_bind()` in `tests/e2e/conftest.py`) need `# noqa: PLW1510` — ruff can't verify it
statically.

## Conventions

- README/`.github/` scaffolding (badges, section layout, issue/PR templates, `dependabot.yml`,
  `labels.yml`, the CI shape) is deliberately copied from sibling `techcode-io` repos
  (`pyinfra-node-exporter`, `ignity`, `temply`) — check those before inventing new structure or
  wording.
- Commit titles must satisfy `.gitlint`: `type: subject` where type is one of
  `build|ci|docs|feat|fix|perf|refactor|test|chore|release`, 5-80 chars total; enforced by the
  commit-msg pre-commit hook.
