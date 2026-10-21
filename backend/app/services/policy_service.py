from backend.app.db.models import AppPolicy


def initialize_policy(session_factory,days):
    with session_factory() as db:
        if db.get(AppPolicy,1) is None:
            db.add(AppPolicy(id=1,confirmation_days=days,revision=0))
            db.commit()


def confirmation_days(db,fallback=30):
    policy=db.get(AppPolicy,1)
    return policy.confirmation_days if policy is not None else fallback
