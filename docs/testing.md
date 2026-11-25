# Tests

## Actual execution status

Validation is in progress on the development branch. This section will be updated with observed results before delivery. No production installation has been performed.

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

GitHub Actions checks out exact NetBox **4.7.5**, installs its dependencies and this plugin, and uses isolated PostgreSQL 18 and Redis 8. It checks Django configuration, migration drift/application, static collection and `netbox_vertical_pdu.tests`.

Coverage includes tab/URL registration, rendering, links, CRUD, face selection, overlap/rack/type validation, stale placements, anonymous access, rack/device/placement/outlet constraints, denied writes, constrained-edit rollback, CSRF and escaped/localized SVG output.

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

## Manual checks

Docker image build/startup and browser light/dark rendering are separate from unit/Django integration tests. Follow [docker.md](docker.md). Automated test success does not imply those manual checks were performed.
