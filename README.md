<h1 align="center">Pyinfra VictoriaMetrics</h1>

<p align="center">
  <i align="center">Install and uninstall VictoriaMetrics (single-node) and vmalert with pyinfra.</i>
</p>

<h4 align="center">
  <a href="https://github.com/techcode-io/pyinfra-victoria-metrics/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/techcode-io/pyinfra-victoria-metrics/ci.yml?branch=main&label=ci&style=flat-square" alt="continuous integration" style="height: 20px;">
  </a>
  <a href="https://github.com/techcode-io/pyinfra-victoria-metrics/graphs/contributors">
    <img src="https://img.shields.io/github/contributors-anon/techcode-io/pyinfra-victoria-metrics?color=yellow&style=flat-square" alt="contributors" style="height: 20px;">
  </a>
  <a href="https://opensource.org/licenses/Apache-2.0">
    <img src="https://img.shields.io/badge/apache%202.0-blue.svg?style=flat-square&label=license" alt="license" style="height: 20px;">
  </a>
  <br>
</h4>

- [Source](https://github.com/techcode-io/pyinfra-victoria-metrics)
- [Issues](https://github.com/techcode-io/pyinfra-victoria-metrics/issues)
- [Contact](mailto:adrien.mannocci@gmail.com)
- [Maintained by techcode.io](https://techcode.io)

## :package: Prerequisites

- [uv](https://docs.astral.sh/uv/) for development.
- [Podman](https://podman.io/docs) to run the end-to-end tests.

## :sparkles: Features

- Idempotent `install()`: system user/group, storage directory, VictoriaMetrics + vmalert binaries, systemd units and
  running services in one call.
- Skips re-downloading the binaries when the installed versions already match, using pyinfra facts.
- `uninstall()` reverses everything: services, unit files, binaries, user and group (the storage directory is left in
  place, so data survives an uninstall).
- Deploy functions only, no CLI: import it into any [pyinfra](https://pyinfra.com) project.
- Doesn't manage `-promscrape.config` / `-rule` file *content* (scrape targets, alerting rules) — that stays in the
  caller's own pyinfra project, same as any other config it deploys. This library only wires up the binaries, the
  systemd units and the flags pointing at those files.

## :dart: Motivation

- We needed to manage VictoriaMetrics and vmalert the same way across every server we operate.
- The solution should be reusable across pyinfra projects instead of copy-pasted between deploy scripts.
- The solution should be idempotent and skip work that has already been done.

## :hammer: Workflow

### Setup

The following steps will ensure your project is cloned properly.

1. Clone repository:
   ```shell
   git clone https://github.com/techcode-io/pyinfra-victoria-metrics
   cd pyinfra-victoria-metrics
   ```
2. Install dependencies and setup environment:
   ```shell
   uv sync
   uv run poe env:configure
   ```

### Lint

- To lint you have to use the workflow.

```bash
uv run poe lint
```

### Format

- To format you have to use the workflow.

```bash
uv run poe fmt
```

- It will format the project code using `ruff`.

### Test

- To test you have to use the workflow.
- Tests are based on `pytest` and run the deploy functions against a real systemd container via Podman.

```bash
uv run poe test
```

## 📖 Usage

### How it works

- `install()` and `uninstall()` are [pyinfra](https://pyinfra.com) deploy functions, wrapped with `@deploy(...)`.
- They take explicit keyword arguments instead of reading `host.data`, so any inventory can use them.
- `install()` creates a shared system user/group and the VictoriaMetrics storage directory, downloads the
  VictoriaMetrics and vmalert release binaries, renders both systemd units from bundled templates, then enables and
  starts both services.
- Before downloading, it checks the currently installed versions using pyinfra facts and skips the download entirely if
  they already match.
- `uninstall()` stops and disables both services, then removes both unit files, both binaries, the user and the group.
  The storage directory (and any scrape/rule config you deployed yourself) is left untouched.

### How to install VictoriaMetrics and vmalert

- This project isn't published to PyPI yet, so add it as a git dependency pinned to a commit.
- Find the commit you want to pin to on
  the [commit history](https://github.com/techcode-io/pyinfra-victoria-metrics/commits/main), then add it to your
  pyinfra project.

```bash
uv add git+https://github.com/techcode-io/pyinfra-victoria-metrics --rev <commit-sha>
# or
pip install git+https://github.com/techcode-io/pyinfra-victoria-metrics@<commit-sha>
```

- This adds the following to your `pyproject.toml`, which you can also edit directly.

```toml
[project]
dependencies = ["pyinfra-victoria-metrics"]

[tool.uv.sources]
pyinfra-victoria-metrics = { git = "https://github.com/techcode-io/pyinfra-victoria-metrics", rev = "<commit-sha>" }
```

- Then call `install()` from a deploy script.

```python
from pyinfra_victoria_metrics import install

install()
```

### How to uninstall VictoriaMetrics and vmalert

- Call `uninstall()` from a deploy script.

```python
from pyinfra_victoria_metrics import uninstall

uninstall()
```

### How to customize the install

- All functions accept keyword arguments; defaults match the upstream VictoriaMetrics release layout for `linux-amd64`.
- `vmalert` requires a non-empty `-rule` flag to start, so you must override `vmalert_service_args` with a `rule` path
  pointing at a file your own project deploys (this library deliberately doesn't manage that content).

```python
from pyinfra_victoria_metrics import (
    DEFAULT_SERVICE_ARGS,
    DEFAULT_VMALERT_SERVICE_ARGS,
    install,
)

install(
    version="v1.150.0",
    system_user="victoria-metrics",
    service_args={
        **DEFAULT_SERVICE_ARGS,
        "promscrape.config": "/etc/victoria-metrics/scrape.yaml",
    },
    vmalert_service_args={
        **DEFAULT_VMALERT_SERVICE_ARGS,
        "rule": "/etc/victoria-metrics/rules.yml",
    },
)
```

| Function                   | Parameter              | Default                        | Description                                           |
|----------------------------|------------------------|--------------------------------|-------------------------------------------------------|
| `install`, `uninstall`     | `system_user`          | `victoria-metrics`             | System user running both services                     |
| `install`, `uninstall`     | `system_group`         | `victoria-metrics`             | System group running both services                    |
| `install`                  | `version`              | `v1.150.0`                     | VictoriaMetrics/vmalert release version to download   |
| `install`                  | `max_open_files`       | `2097152`                      | `LimitNOFILE` set on the VictoriaMetrics systemd unit |
| `install`                  | `service_args`         | `DEFAULT_SERVICE_ARGS`         | Dict of `-flag: value` passed to `victoria-metrics`   |
| `install`                  | `vmalert_service_args` | `DEFAULT_VMALERT_SERVICE_ARGS` | Dict of `-flag: value` passed to `vmalert`            |
| `restart_victoria_metrics` | `restart`              | `True`                         | Restart `victoria-metrics` when truthy                |
| `restart_vmalert`          | `restart`              | `True`                         | Restart `vmalert` when truthy                         |

### Restarting on scrape/rule config changes

`install()` restarts a service on its own when the binary was upgraded or its systemd unit changed, but it has no
visibility into the scrape/rule *content* your own project deploys (see below) — the usual flow is `install()` once,
then deploy your config, then call the matching restart shortcut.
`restart_victoria_metrics()` / `restart_vmalert()` just restart their service; pass `restart=` wired to the `.changed`
result of whatever operation writes the config file so the restart only fires when that file actually changed:

```python
from pyinfra.operations import files
from pyinfra_victoria_metrics import (
    DEFAULT_SYSTEM_GROUP,
    install,
    restart_victoria_metrics,
    restart_vmalert,
)

install(
    service_args={"promscrape.config": "/etc/victoria-metrics/scrape.yaml"},
    vmalert_service_args={"rule": "/etc/victoria-metrics/rules.yml"},
)

# scrape.yaml can carry scrape credentials (bearer tokens, basic auth), so restrict it to the
# service group install() just created.
scrape_config = files.put(
    name="Deploy VictoriaMetrics scrape config",
    src="scrape.yaml",
    dest="/etc/victoria-metrics/scrape.yaml",
    group=DEFAULT_SYSTEM_GROUP,
    mode="640",
)
rules_config = files.put(
    name="Deploy vmalert rules",
    src="rules.yml",
    dest="/etc/victoria-metrics/rules.yml",
    group=DEFAULT_SYSTEM_GROUP,
    mode="640",
)

restart_victoria_metrics(restart=scrape_config.changed)
restart_vmalert(restart=rules_config.changed)
```

### Examples of scrape/rule config

Since this library doesn't manage `-promscrape.config` / `-rule` file content (see above), the
[`examples/`](examples) directory has a starting point you can copy into your own pyinfra project and deploy however you
deploy the rest of your host config (`files.put()`, `files.template()`, etc.):

- [`examples/scrape.yaml`](examples/scrape.yaml) — a VictoriaMetrics scrape config for
  `node_exporter`, `vmalert` and `alertmanager` targets, for `service_args["promscrape.config"]`.
- [`examples/rules.yml`](examples/rules.yml) — a vmalert rule file with common
  [node_exporter](https://github.com/techcode-io/pyinfra-node-exporter) host alerts (memory, disk, CPU, network, clock,
  systemd, RAID, …), for `vmalert_service_args["rule"]`.

## :heart: Contributing

If you find this project useful here's how you can help, please click the :eye: **Watch** button to avoid missing
notifications about new versions, and give it a :star2: **GitHub Star**!

You can also contribute by:

- Sending a [Pull Request](https://github.com/techcode-io/pyinfra-victoria-metrics/pulls) with your awesome new features
  and bug fixed.
- Be part of the community and help resolve [Issues](https://github.com/techcode-io/pyinfra-victoria-metrics/issues).

## 🧾 License

The `pyinfra-victoria-metrics` project is free and open-source software licensed under the Apache-2.0 license.
