from sqlalchemy import select
from backend.app.db.models import SignRecord,Evidence


def sign_evidence(db,record_id):
    related=select(SignRecord.id).where(SignRecord.id==record_id).cte(name='related_signs',recursive=True)
    related=related.union_all(select(SignRecord.id).join(related,SignRecord.merged_into_id==related.c.id))
    return db.query(Evidence).filter(Evidence.record_id.in_(select(related.c.id))).order_by(Evidence.created_at.desc(),Evidence.id).all()
