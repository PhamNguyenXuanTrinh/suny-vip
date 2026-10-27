"""44-table contract dated 25 October 2026. Existing incompatible data is never reset."""
import json
from pathlib import Path
import sqlalchemy as sa
from alembic import op

revision='0001_baseline'
down_revision=None
branch_labels=None
depends_on=None

def snapshot():
    return json.loads(Path(__file__).with_name('0001_ddl.json').read_text())

def upgrade():
    bind=op.get_bind()
    names=set(sa.inspect(bind).get_table_names())-{'alembic_version'}
    if names:
        raise RuntimeError('Existing database requires a reviewed legacy import; no tables or data have been changed. Use the backup and preflight scripts first.')
    for ddl in snapshot()['statements']:
        op.execute(ddl)
    for name in ('inventory_movements','audit_log','production_reports','task_updates','customer_payment_allocations'):
        for verb in ('UPDATE','DELETE'):
            op.execute(f"CREATE TRIGGER immutable_{name}_{verb.lower()} BEFORE {verb} ON {name} BEGIN SELECT RAISE(ABORT,'append-only ledger'); END")
    op.execute("""CREATE TRIGGER department_cycle_insert BEFORE INSERT ON departments WHEN NEW.parent_department_id IS NOT NULL BEGIN
      SELECT RAISE(ABORT,'department cycle') WHERE NEW.parent_department_id = NEW.id;
    END""")
    op.execute("""CREATE TRIGGER department_cycle_update BEFORE UPDATE OF parent_department_id ON departments WHEN NEW.parent_department_id IS NOT NULL BEGIN
      SELECT RAISE(ABORT,'department cycle') WHERE NEW.id IN (
        WITH RECURSIVE ancestors(id) AS (SELECT NEW.parent_department_id UNION SELECT d.parent_department_id FROM departments d JOIN ancestors a ON d.id=a.id WHERE d.parent_department_id IS NOT NULL) SELECT id FROM ancestors);
    END""")

def downgrade():
    bind=op.get_bind();tables=snapshot()['tables']
    for name in tables:
        if bind.exec_driver_sql('SELECT COUNT(*) FROM '+name).scalar_one():
            raise RuntimeError('Nonempty database: rollback by verified SQLite backup, never drop user data')
    for name in ('inventory_movements','audit_log','production_reports','task_updates','customer_payment_allocations'):
        for verb in ('update','delete'):op.execute(f'DROP TRIGGER IF EXISTS immutable_{name}_{verb}')
    op.execute('DROP TRIGGER IF EXISTS department_cycle_insert')
    op.execute('DROP TRIGGER IF EXISTS department_cycle_update')
    for name in reversed(tables):
        op.execute('DROP TABLE '+name)
