#!/usr/bin/env python3
"""Tails /var/ossec/logs/alerts/alerts.json and bulk-indexes into OpenSearch."""
import json
import ssl
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

OPENSEARCH = "https://localhost:9200"
ALERTS_FILE = "/var/ossec/logs/alerts/alerts.json"
STATE_FILE = "/var/lib/wazuh-indexer/.alerts_offset"
BATCH = 50

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

import base64
creds = base64.b64encode(b"admin:admin").decode()
HEADERS = {"Content-Type": "application/json", "Authorization": f"Basic {creds}"}


def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(OPENSEARCH + path, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def get_offset():
    try:
        return int(open(STATE_FILE).read().strip())
    except Exception:
        return 0


def save_offset(offset):
    with open(STATE_FILE, "w") as f:
        f.write(str(offset))


def index_batch(alerts):
    today = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    index = f"wazuh-alerts-4.x-{today}"
    bulk = ""
    for a in alerts:
        bulk += json.dumps({"index": {"_index": index}}) + "\n"
        bulk += json.dumps(a) + "\n"
    data = bulk.encode()
    req = urllib.request.Request(
        OPENSEARCH + "/_bulk", data=data,
        headers={**HEADERS, "Content-Type": "application/x-ndjson"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            return r.status in (200, 201)
    except Exception:
        return False


def wait_for_opensearch():
    while True:
        try:
            req = urllib.request.Request(OPENSEARCH + "/_cluster/health", headers=HEADERS)
            with urllib.request.urlopen(req, context=ctx, timeout=5):
                print("[alerts-indexer] OpenSearch ready", flush=True)
                return
        except Exception:
            time.sleep(5)


wait_for_opensearch()
offset = get_offset()
print(f"[alerts-indexer] Starting at offset {offset}", flush=True)

while True:
    try:
        with open(ALERTS_FILE) as f:
            f.seek(offset)
            batch = []
            while True:
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    alert = json.loads(line)
                    batch.append(alert)
                    if len(batch) >= BATCH:
                        if index_batch(batch):
                            offset = f.tell()
                            save_offset(offset)
                        batch = []
                except json.JSONDecodeError:
                    pass
            if batch:
                if index_batch(batch):
                    offset = f.tell()
                    save_offset(offset)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[alerts-indexer] error: {e}", flush=True)
    time.sleep(5)
