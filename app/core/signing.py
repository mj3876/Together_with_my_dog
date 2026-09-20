import hashlib
import hmac
import json


def sign(value, key, scope):
    message = scope + ":" + json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


def valid(value, token, key, scope):
    return bool(token) and hmac.compare_digest(sign(value, key, scope), token)
