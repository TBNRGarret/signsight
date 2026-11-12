"""Receipts participate in the resource transaction; never cache authorization."""
import hashlib
import json

from fastapi import Header, HTTPException
from sqlalchemy.exc import IntegrityError

from backend.app.db.models import WriteReceipt

request_key_header = Header(default=None, alias="Idempotency-Key", min_length=8,
                            max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


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


def begin_review(db, owner, operation, key, payload, result_id):
    """Return a replay or reserve this key in the caller's decision transaction."""
    identity = fingerprint(payload)
    prior = lookup(db, owner, operation, key, identity)
    db.rollback()  # Release lookup/auth snapshots before acquiring a write lock.
    if prior is not None:
        return prior
    try:
        claim(db, owner, operation, key, identity, [result_id])
    except IntegrityError:
        db.rollback()
        prior = lookup(db, owner, operation, key, identity)
        if prior is None:
            raise
        return prior
    return None
