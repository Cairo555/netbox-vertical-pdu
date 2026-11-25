# NetBox Docker 5.1.2 / NetBox 4.7.5

Use a **separate development/staging stack** with independent database, Redis and media volumes. No production deployment is performed by this repository. Back up staging data you intend to retain before migration.

## Build an immutable plugin image

```sh
git clone --branch dev/vertical-pdu https://github.com/Cairo555/netbox-vertical-pdu.git
cd netbox-vertical-pdu
git rev-parse HEAD
docker build -f development/Dockerfile \
  --build-arg NETBOX_IMAGE=docker.io/netboxcommunity/netbox:v4.7.5-5.1.2 \
  -t netbox-vertical-pdu:0.1.0-dev .
```

Record the commit SHA and built image digest. The Dockerfile installs into `/opt/netbox/venv`, enables the plugin temporarily for static collection, and does not migrate or connect to your database. When extending an existing custom image with other plugins, keep those plugins in the build-time plugin list too.

Alternatively, in a custom build using `plugin_requirements.txt`, pin a reviewed commit:

```text
netbox-vertical-pdu @ https://github.com/Cairo555/netbox-vertical-pdu/archive/REPLACE_WITH_COMMIT_SHA.zip
```

Replace the placeholder with a real commit. Install via `uv pip install --python /opt/netbox/venv/bin/python -r /opt/netbox/plugin_requirements.txt`, enable the plugin and collect static assets during that build. A requirements file alone does not install or activate a plugin.

## Configure a separate netbox-docker checkout

Use upstream **5.1.2** and its normal environment setup. In mounted `configuration/plugins.py`, append to your existing plugins:

```python
PLUGINS = [
    # Keep existing plugins here.
    "netbox_vertical_pdu",
]
```

Merge this `docker-compose.override.yml` into that staging checkout:

```yaml
services:
  netbox:
    image: netbox-vertical-pdu:0.1.0-dev
    pull_policy: never
    ports:
      - "127.0.0.1:8000:8080"
  netbox-worker:
    image: netbox-vertical-pdu:0.1.0-dev
    pull_policy: never
```

Web and worker need identical plugin versions/configuration. Apply the image to any additional NetBox services in your own stack. Runtime configuration is bind-mounted: **build-time configuration does not replace runtime `plugins.py`**.

```sh
docker compose -p vpdu-dev config
docker compose -p vpdu-dev up -d
docker compose -p vpdu-dev logs --tail=100 netbox
docker compose -p vpdu-dev exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py check
docker compose -p vpdu-dev exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py showmigrations netbox_vertical_pdu
```

The Docker entrypoint applies pending migrations. Verify `0001_initial` is marked `[X]`. Create a development administrator using the normal NetBox Docker procedure, open `http://localhost:8000` and exercise the rack tab. Assets are collected in the image; if you mount a separate static directory, collect assets into it too.

Verify four PDUs across two lanes per side, front/rear, a cabled outlet, marked-connected and free outlets, a restricted user, both color themes, half-U equipment, and descending/custom rack numbering.

## Rollback / removal

For a code rollback, use the previous compatible image and retain the database. To remove from disposable staging, first export/record placement data, then while the plugin remains installed:

```sh
docker compose -p vpdu-dev exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate netbox_vertical_pdu zero
```

This deletes plugin placement data. Then remove the plugin from runtime configuration and recreate web/worker with the original image. Core devices/outlets/cables are retained. Do not drop the whole database or delete shared volumes.

References checked against exact upstream sources: [NetBox 4.7.5](https://github.com/netbox-community/netbox/tree/v4.7.5), [Docker 5.1.2](https://github.com/netbox-community/netbox-docker/tree/5.1.2), [plugin documentation](https://netbox.readthedocs.io/en/stable/plugins/development/).
