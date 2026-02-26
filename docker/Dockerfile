# Build from project root: docker build -t odoo-k8s:19.0 -f docker/Dockerfile .
FROM odoo:19.0

USER root

# Install additional Python dependencies
COPY docker/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

# Copy custom addons into the image
COPY addons/ /mnt/extra-addons/

USER odoo