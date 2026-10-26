"""Optional Redis cache. A miss/failure never changes the clinical result path."""
import hashlib
import json
import logging
import os
import time

log = logging.getLogger(__name__)
VERSION = "validated-results-v2"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class ResultCache:
    def __init__(self, client=None, ttl=None):
        self.client = client
        self.ttl = max(1, min(int(ttl or os.getenv("REDIS_TTL_SECONDS", "300")), 86400))

    def connection(self):
        if self.client is None:
            url = os.getenv("REDIS_URL")
            if not url: return None
            from redis import Redis
            self.client = Redis.from_url(url, socket_connect_timeout=.5, socket_timeout=.5, decode_responses=True)
        return self.client

    def key(self, context):
        if not context.get("dataset_versions") or not all(context["dataset_versions"].values()):
            return None
        return "clinical:" + VERSION + ":" + hashlib.sha256(canonical(context).encode()).hexdigest()

    def get(self, context):
        try:
            key = self.key(context)
            client = self.connection() if key else None
            if client is None: return None, "bypassed"
            raw = client.get(key)
            if raw is None: return None, "miss"
            entry = json.loads(raw)
            payload = entry["payload"]
            if (entry["version"] != VERSION or entry["context"] != context or entry["expires"] <= time.time()
                or entry["digest"] != hashlib.sha256(canonical(payload).encode()).hexdigest()):
                client.delete(key)
                return None, "invalid"
            return payload, "hit"
        except Exception:
            log.warning("CACHE_READ_FAILED")
            return None, "unavailable"

    def put(self, context, payload):
        try:
            key = self.key(context)
            client = self.connection() if key else None
            if client is None: return "bypassed"
            entry = {"version": VERSION, "context": context, "expires": time.time()+self.ttl,
                     "payload": payload, "digest": hashlib.sha256(canonical(payload).encode()).hexdigest()}
            client.setex(key, self.ttl, canonical(entry))
            return "stored"
        except Exception:
            log.warning("CACHE_WRITE_FAILED")
            return "unavailable"

    def invalidate(self, context):
        try:
            key = self.key(context)
            if key and self.connection() is not None: self.client.delete(key)
        except Exception:
            log.warning("CACHE_INVALIDATE_FAILED")
