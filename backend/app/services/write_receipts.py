"""Receipts participate in the resource transaction; never cache authorization."""
import hashlib
import json

from fastapi import HTTPException

from backend.app.db.models import WriteReceipt


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def lookup(db, owner, operation, key, identity):
    if key is None:
        return None
    receipt = db.get(WriteReceipt, (owner, operation, key))
    if receipt is None:
        return None
    if receipt.fingerprint != identity:
        raise HTTPException(409, "Request key was already used with different content")
    return json.loads(receipt.result_ids)


def claim(db, owner, operation, key, identity, result_ids):
    if key is not None:
        db.add(WriteReceipt(owner_id=owner, operation=operation, request_key=key,
                            fingerprint=identity, result_ids=json.dumps(result_ids)))
        # Unique-key contenders wait for the winner's transaction, then replay.
        # Flush before saving files so a losing upload creates no orphan image.
        db.flush()
