FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

# Fake systemctl so dpkg postinstall scripts don't fail trying to start services
RUN printf '#!/bin/bash\necho "[fake-systemctl] $@"\nexit 0\n' \
    > /usr/local/bin/systemctl && chmod +x /usr/local/bin/systemctl

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release sudo iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Add Wazuh apt repository
RUN curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH \
    | gpg --no-default-keyring \
      --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import \
    && chmod 644 /usr/share/keyrings/wazuh.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] \
       https://packages.wazuh.com/4.x/apt/ stable main" \
    > /etc/apt/sources.list.d/wazuh.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    wazuh-indexer wazuh-manager wazuh-dashboard \
    && rm -rf /var/lib/apt/lists/*

# Generate SSL certs using wazuh-certs-tool — pure openssl, no running services needed
# The tool looks for config.yml in its working directory
COPY config.yml /root/config.yml
RUN cd /root \
    && curl -sO https://packages.wazuh.com/4.14/wazuh-certs-tool.sh \
    && bash ./wazuh-certs-tool.sh -A \
    && rm wazuh-certs-tool.sh

# Distribute certs to each component's config directory
RUN mkdir -p /etc/wazuh-indexer/certs /etc/wazuh-dashboard/certs \
    && cp /root/wazuh-certificates/root-ca.pem          /etc/wazuh-indexer/certs/ \
    && cp /root/wazuh-certificates/wazuh.pem             /etc/wazuh-indexer/certs/indexer.pem \
    && cp /root/wazuh-certificates/wazuh-key.pem        /etc/wazuh-indexer/certs/indexer-key.pem \
    && cp /root/wazuh-certificates/admin.pem            /etc/wazuh-indexer/certs/ \
    && cp /root/wazuh-certificates/admin-key.pem        /etc/wazuh-indexer/certs/ \
    && cp /root/wazuh-certificates/root-ca.pem          /etc/wazuh-dashboard/certs/ \
    && cp /root/wazuh-certificates/wazuh-dashboard.pem      /etc/wazuh-dashboard/certs/ \
    && cp /root/wazuh-certificates/wazuh-dashboard-key.pem  /etc/wazuh-dashboard/certs/ \
    && chown -R wazuh-indexer:wazuh-indexer     /etc/wazuh-indexer/certs \
    && chown -R wazuh-dashboard:wazuh-dashboard /etc/wazuh-dashboard/certs \
    && chmod +x /etc/init.d/wazuh-indexer

COPY opensearch.yml            /etc/wazuh-indexer/opensearch.yml
COPY opensearch_dashboards.yml /etc/wazuh-dashboard/opensearch_dashboards.yml

# Bake in the alerts index template (normally pushed by filebeat in a standard install)
RUN curl -s https://raw.githubusercontent.com/wazuh/wazuh/v4.14.4/extensions/elasticsearch/7.x/wazuh-template.json \
    -o /etc/wazuh-indexer/wazuh-template.json

COPY entrypoint.sh /entrypoint.sh
COPY alerts-indexer.py /usr/local/bin/alerts-indexer.py
RUN chmod +x /entrypoint.sh

# 1514/1515: agent comms, 514/udp: syslog, 55000: REST API, 5601: dashboard
EXPOSE 1514 1515 514/udp 55000 5601
ENTRYPOINT ["/entrypoint.sh"]
