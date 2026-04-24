FROM debian:12-slim

# Install required tools
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    iproute2 iputils-ping iptables nano procps tcpdump curl \
    python3 python3-flask ulogd2 ulogd2-json && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \ 
    mkdir -p /var/log/flask


RUN apt-get update && apt-get install -y supervisor suricata && \
    mkdir -p /var/log/supervisor



# Enable IP forwarding
RUN echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

# Fake systemctl so wazuh-agent postinstall doesn't fail
RUN printf '#!/bin/bash\necho "[fake-systemctl] $@"\nexit 0\n' \
    > /usr/local/bin/systemctl && chmod +x /usr/local/bin/systemctl

# Install Wazuh agent
RUN apt-get update && apt-get install -y --no-install-recommends gnupg \
    && curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH \
       | gpg --no-default-keyring \
         --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import \
    && chmod 644 /usr/share/keyrings/wazuh.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] \
       https://packages.wazuh.com/4.x/apt/ stable main" \
       > /etc/apt/sources.list.d/wazuh.list \
    && apt-get update \
    && WAZUH_MANAGER=192.168.90.20 WAZUH_AGENT_NAME=router apt-get install -y wazuh-agent \
    && rm -rf /var/lib/apt/lists/*

# Tell the agent to monitor Suricata alerts-only EVE log
RUN sed -i 's|</ossec_config>|<localfile>\n    <log_format>json</log_format>\n    <location>/var/log/suricata/alerts.json</location>\n  </localfile>\n</ossec_config>|' \
    /var/ossec/etc/ossec.conf

COPY entrypoint.sh /entrypoint.sh
COPY app.py /opt/fwui/app.py
COPY index.html /opt/fwui/templates/index.html
COPY login.html /opt/fwui/templates/login.html
COPY firewall.html /opt/fwui/templates/firewall.html
COPY ids.html /opt/fwui/templates/ids.html
COPY base.html /opt/fwui/templates/base.html
COPY router.conf /etc/supervisor/conf.d/router.conf
COPY suricata.yaml /etc/suricata/suricata.yaml
COPY ulogd.conf /etc/ulogd.conf


RUN chmod +x /entrypoint.sh

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]

ENTRYPOINT ["/entrypoint.sh"]
