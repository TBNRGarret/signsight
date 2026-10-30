"""Check that restoring configuration cannot orphan persisted catalog references."""
from sqlalchemy import select

from backend.app.db.models import ImageDetection, Observation, SignRecord, SignReport,SignCatalogEntry


def require_database_catalog(session_factory, catalog):
    unknown = set()
    with session_factory() as db:
        for column in (ImageDetection.predicted_class, Observation.proposed_class,
                       SignRecord.predicted_class, SignReport.proposed_class):
            stored = db.scalars(select(column).where(column.is_not(None)).distinct())
            unknown.update(value for value in stored if value not in catalog.by_id)
        registered=db.scalars(select(SignCatalogEntry)).all()
        for entry in registered:
            item=catalog.by_id.get(entry.id)
            if item is None or item['qcvn_code']!=entry.qcvn_code or item['name_vi']!=entry.name_vi:
                raise RuntimeError(f'Configured catalog reassigns or removes stored ID {entry.id}; restore the previous catalog')
        if not unknown:
            # Remember every published catalog identity, including classes without observations yet.
            from sqlalchemy.dialects.sqlite import insert
            for item in catalog.items:
                db.execute(insert(SignCatalogEntry).values(id=item['new_id'],qcvn_code=item['qcvn_code'],name_vi=item['name_vi'])
                           .on_conflict_do_nothing())
            # A second worker may have registered a different configuration concurrently.
            db.expire_all()
            for entry in db.scalars(select(SignCatalogEntry)):
                item=catalog.by_id.get(entry.id)
                if item is None or item['qcvn_code']!=entry.qcvn_code or item['name_vi']!=entry.name_vi:
                    raise RuntimeError('Conflicting catalog configurations; restore the registered catalog')
            db.commit()
    if unknown:
        raise RuntimeError(
            'Database references missing catalog IDs: '
            + ', '.join(map(str, sorted(unknown)))
            + '. Restore the configured SIGNSIGHT_CATALOG_PATH before starting the API.'
        )
