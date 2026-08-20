from pyinfra.operations import server

from pyinfra_victoria_metrics import DEFAULT_VMALERT_SERVICE_ARGS, install

# vmalert requires a non-empty `-rule` flag to start; this library deliberately doesn't manage
# rule/scrape config content (that's left to the caller), so the e2e test supplies a minimal
# placeholder rule file itself.
server.shell(
    name="Write a minimal vmalert rule file for the e2e test",
    commands=["printf 'groups: []\\n' > /etc/vmalert-rules.yml"],
)

install(
    vmalert_service_args={
        **DEFAULT_VMALERT_SERVICE_ARGS,
        "rule": "/etc/vmalert-rules.yml",
    },
)
