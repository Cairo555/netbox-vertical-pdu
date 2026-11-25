# Tests

## Actual execution status

The 11 framework-independent tests and Python compilation were executed successfully locally on Python 3.12.14. Package construction, packaged assets, the exact Docker image build and NetBox integration are checked by CI; consult the linked run for the tested commit and its actual conclusion:

[Development-branch test runs](https://github.com/Cairo555/netbox-vertical-pdu/actions/workflows/tests.yml?query=branch%3Adev%2Fvertical-pdu) · [Review and validation summary](https://github.com/Cairo555/netbox-vertical-pdu/pull/1)

The automated suite contains 11 unit tests and 19 NetBox integration tests, plus a real Docker/Chromium smoke job. A configured workflow is not evidence that it passed: use the completed run's conclusion and logs. Browser screenshots are retained as `docker-browser-evidence` for 14 days for visual review. No production installation is performed.

## Local unit tests

```sh
python -m unittest discover -s tests -v
python -m compileall -q netbox_vertical_pdu
python -m pip install build
python -m build
python scripts/check_wheel.py
```

These cover dimensions, bounds, touching/overlapping intervals, multiple lanes, ascending/descending and non-default numbering, short-device outlet clipping, and cabled/marked/free occupancy. They alone do not establish NetBox compatibility.

## NetBox integration tests

GitHub Actions checks out exact NetBox **4.7.5**, installs its dependencies and this plugin, and uses isolated PostgreSQL 18 and Redis 8. It checks Django configuration, migration drift/application, static collection and `netbox_vertical_pdu.tests`. The test configuration clones the already-migrated disposable `netbox` database to avoid replaying the core migration history twice; migrate the base database first as shown below.

Coverage includes tab/URL registration, rendering, links, CRUD, event serialization, face selection, overlap/rack/type validation, stale placements, anonymous access, independent rack/device/placement/outlet constraints, denied writes, constrained-add/edit rollback, CSRF and escaped/localized SVG output.

Reproduce in a disposable NetBox 4.7.5 checkout with its test database and Redis configured:

```sh
pip install /path/to/netbox-vertical-pdu
cp /path/to/netbox-vertical-pdu/development/configuration_vpdu_testing.py netbox/netbox/
export NETBOX_CONFIGURATION=netbox.configuration_vpdu_testing
python netbox/manage.py check
python netbox/manage.py makemigrations netbox_vertical_pdu --check --dry-run
python netbox/manage.py migrate --no-input
python netbox/manage.py collectstatic --no-input
python netbox/manage.py test netbox_vertical_pdu.tests --no-input --verbosity 2
```

Never use a production database. The supplied configuration is test-only.

## Docker startup and browser checks

The Docker job starts the exact 4.7.5/5.1.2 image using the real entrypoint and web server, plus a worker, PostgreSQL and separate Redis task/cache services. It waits for health checks, seeds an empty test database, then runs Chromium against the live web service. The stack is removed afterward; it has no production credentials or external volumes and its port is bound only to loopback.

The browser checks cover native tab/static assets, four side lanes, proportional heights, half-U devices, real cabled/marked/free outlets, the native light/dark toggle, clickable PDUs, front/rear switching, placement CRUD and validation, a narrow mobile viewport, descending numbering, restricted user visibility and JavaScript errors. Five screenshots and a JSON report are saved for review. Automated assertions do not substitute for inspecting those images.

To reproduce on a machine with Docker Compose and Python:

```sh
docker build -f development/Dockerfile -t netbox-vertical-pdu:test .
docker compose -p vpdu-smoke -f development/compose.smoke.yml up -d --wait --wait-timeout 900
mkdir -p test-results
docker compose -p vpdu-smoke -f development/compose.smoke.yml exec -T netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py shell --no-startup --no-imports < development/smoke_seed.py
docker compose -p vpdu-smoke -f development/compose.smoke.yml cp netbox:/tmp/vpdu-smoke.json test-results/fixture.json
python -m pip install playwright==1.64.1
python -m playwright install --with-deps chromium
python development/browser_smoke.py
docker compose -p vpdu-smoke -f development/compose.smoke.yml down --volumes
```

Run the cleanup command even after a failed test. The seed explicitly refuses a database that already contains a Site. Fixed example credentials in these files are solely for this disposable, loopback-only test stack. For a persistent staging installation, follow [docker.md](docker.md) and configure your own credentials.
