"""Technical idempotency records protect transactions against duplicate mobile submissions."""
from alembic import op
revision='0003_operations'
down_revision='0002_auth'
branch_labels=None
depends_on=None
def upgrade():
    op.execute('''CREATE TABLE operation_keys (
      id VARCHAR(36) PRIMARY KEY NOT NULL,organization_id VARCHAR(36) NOT NULL,
      actor_user_id VARCHAR(36) NOT NULL,key VARCHAR(120) NOT NULL,
      route VARCHAR(250) NOT NULL,payload_hash VARCHAR(64) NOT NULL,result_json TEXT NOT NULL,
      created_at VARCHAR(32) NOT NULL, CONSTRAINT uq_operation_keys_organization_id UNIQUE(organization_id,key),
      FOREIGN KEY(organization_id,actor_user_id) REFERENCES app_users(organization_id,id))''')
def downgrade():
    if op.get_bind().exec_driver_sql('SELECT COUNT(*) FROM operation_keys').scalar_one():raise RuntimeError('Operation history exists; use verified backup for rollback')
    op.execute('DROP TABLE operation_keys')
