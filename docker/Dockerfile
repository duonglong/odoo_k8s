FROM odoo:19.0

USER root

# Install additional system dependencies if needed
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy custom entrypoint and utilities
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY wait-for-it.sh /usr/local/bin/wait-for-it.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/wait-for-it.sh

# Copy default Odoo config (can be overridden via ConfigMap)
COPY odoo.conf /etc/odoo/odoo.conf

# Install additional Python dependencies if needed
# COPY requirements.txt /tmp/requirements.txt
# RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

USER odoo

EXPOSE 8069 8072

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["odoo"]
