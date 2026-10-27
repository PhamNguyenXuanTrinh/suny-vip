"""Supplier allocations and append-only allocation events fill the documented AP/history gaps."""
from alembic import op
revision='0004_finance'
down_revision='0003_operations'
branch_labels=None
depends_on=None
def upgrade():
    op.execute('''CREATE TABLE supplier_payment_allocations (
      id VARCHAR(36) PRIMARY KEY NOT NULL, organization_id VARCHAR(36) NOT NULL,
      payment_id VARCHAR(36) NOT NULL,bill_id VARCHAR(36) NOT NULL,
      amount BIGINT NOT NULL CHECK(typeof(amount)='integer' AND amount>0),
      created_at VARCHAR(32) NOT NULL,created_by VARCHAR(36) NOT NULL,
      CONSTRAINT uq_supplier_payment_allocations_payment_id UNIQUE(payment_id,bill_id),
      CONSTRAINT uq_supplier_payment_allocations_organization_id UNIQUE(organization_id,id),
      FOREIGN KEY(organization_id,payment_id) REFERENCES supplier_payments(organization_id,id),
      FOREIGN KEY(organization_id,bill_id) REFERENCES supplier_bills(organization_id,id),
      FOREIGN KEY(organization_id,created_by) REFERENCES app_users(organization_id,id))''')
    op.execute('''CREATE TABLE payment_allocation_events (
      id VARCHAR(36) PRIMARY KEY NOT NULL, organization_id VARCHAR(36) NOT NULL,
      customer_allocation_id VARCHAR(36),supplier_allocation_id VARCHAR(36),
      amount BIGINT NOT NULL CHECK(typeof(amount)='integer' AND amount>0),
      occurred_at VARCHAR(32) NOT NULL,actor_user_id VARCHAR(36) NOT NULL,
      CHECK((customer_allocation_id IS NOT NULL) != (supplier_allocation_id IS NOT NULL)),
      FOREIGN KEY(organization_id,customer_allocation_id) REFERENCES customer_payment_allocations(organization_id,id),
      FOREIGN KEY(organization_id,supplier_allocation_id) REFERENCES supplier_payment_allocations(organization_id,id),
      FOREIGN KEY(organization_id,actor_user_id) REFERENCES app_users(organization_id,id))''')
    op.execute('CREATE INDEX ix_payment_events_tenant_time ON payment_allocation_events(organization_id,occurred_at)')
    op.execute('''INSERT INTO payment_allocation_events(id,organization_id,customer_allocation_id,amount,occurred_at,actor_user_id)
      SELECT id,organization_id,id,amount,created_at,created_by FROM customer_payment_allocations''')
    op.execute('DROP TRIGGER immutable_customer_payment_allocations_update')
    for verb in ('UPDATE','DELETE'):
        op.execute(f"CREATE TRIGGER immutable_payment_events_{verb.lower()} BEFORE {verb} ON payment_allocation_events BEGIN SELECT RAISE(ABORT,'append-only allocation history'); END")
def downgrade():
    for name in ('payment_allocation_events','supplier_payment_allocations'):
        if op.get_bind().exec_driver_sql('SELECT COUNT(*) FROM '+name).scalar_one():raise RuntimeError('Financial history exists; restore verified backup for rollback')
    op.execute('DROP TABLE payment_allocation_events');op.execute('DROP TABLE supplier_payment_allocations')
    op.execute("CREATE TRIGGER immutable_customer_payment_allocations_update BEFORE UPDATE ON customer_payment_allocations BEGIN SELECT RAISE(ABORT,'append-only ledger'); END")
