# Tests

## Actual execution status

The 11 framework-independent tests and Python compilation were executed successfully locally on Python 3.12.14. Package construction, packaged assets, the exact Docker image build and NetBox integration are checked by CI; consult the linked run for the tested commit and its actual conclusion:

[Development-branch test runs](https://github.com/Cairo555/netbox-vertical-pdu/actions/workflows/tests.yml?query=branch%3Adev%2Fvertical-pdu) · [Review and validation summary](https://github.com/Cairo555/netbox-vertical-pdu/pull/1)

The automated suite contains 11 unit tests and 19 NetBox integration tests. A configured workflow is not evidence that it passed: use the completed run's conclusion and logs. Full Docker-stack startup and browser visual checks have not been performed. No production installation has been performed.

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

## Manual checks

Docker image build/startup and browser light/dark rendering are separate from unit/Django integration tests. Follow [docker.md](docker.md). Automated test success does not imply those manual checks were performed.
