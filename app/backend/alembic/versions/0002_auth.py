"""Stateful token rotation requires one technical session table beyond 44 business tables."""
from alembic import op

revision='0002_auth'
down_revision='0001_baseline'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('''CREATE TABLE auth_sessions (
        id VARCHAR(36) PRIMARY KEY NOT NULL, organization_id VARCHAR(36) NOT NULL,
        user_id VARCHAR(36) NOT NULL, family_id VARCHAR(36) NOT NULL,
        refresh_hash VARCHAR(64) NOT NULL, created_at VARCHAR(32) NOT NULL,
        expires_at VARCHAR(32) NOT NULL, revoked_at VARCHAR(32),
        CONSTRAINT uq_auth_sessions_refresh_hash UNIQUE(refresh_hash),
        FOREIGN KEY (organization_id,user_id) REFERENCES app_users(organization_id,id))''')
    op.execute('CREATE INDEX ix_auth_sessions_family_id ON auth_sessions(family_id)')

def downgrade():
    if op.get_bind().exec_driver_sql('SELECT COUNT(*) FROM auth_sessions').scalar_one():
        raise RuntimeError('Active or historical sessions exist; restore a verified backup for rollback')
    op.execute('DROP TABLE auth_sessions')
