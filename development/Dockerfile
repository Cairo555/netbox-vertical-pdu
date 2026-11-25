ARG NETBOX_IMAGE=docker.io/netboxcommunity/netbox:v4.7.5-5.1.2
FROM ${NETBOX_IMAGE}
COPY . /opt/netbox-vertical-pdu
RUN /usr/local/bin/uv pip install --python /opt/netbox/venv/bin/python --no-deps /opt/netbox-vertical-pdu
# Make the plugin discoverable while collecting its packaged static assets.
RUN printf '\nPLUGINS = ["netbox_vertical_pdu"]\n' > /etc/netbox/config/plugins.py \
    && DEBUG=true SECRET_KEY=build-only-not-a-deployment-secret-012345678901234567890123456789 \
       /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py collectstatic --no-input
