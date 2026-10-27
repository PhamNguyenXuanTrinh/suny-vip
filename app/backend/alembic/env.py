import os
from alembic import context
from backend.app.database import make_engine
from backend.app.models import metadata

config=context.config
target_metadata=metadata
if context.is_offline_mode():
    context.configure(url=os.getenv('DATABASE_URL',config.get_main_option('sqlalchemy.url')),target_metadata=metadata,literal_binds=True)
    with context.begin_transaction():context.run_migrations()
else:
    supplied=config.attributes.get('connection')
    if supplied is not None:
        context.configure(connection=supplied,target_metadata=metadata,render_as_batch=True)
        with context.begin_transaction():context.run_migrations()
    else:
        engine=make_engine(os.getenv('DATABASE_URL',config.get_main_option('sqlalchemy.url')),foreign_keys=False)
        with engine.begin() as connection:
            context.configure(connection=connection,target_metadata=metadata,render_as_batch=True)
            with context.begin_transaction():context.run_migrations()
            if connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall():raise RuntimeError('Invalid migration references; rolled back')
