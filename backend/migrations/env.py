from alembic import context

from backend.app.db.models import Base


connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use python -m backend.manage migrate to supply a database connection")

context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
with context.begin_transaction():
    context.run_migrations()
