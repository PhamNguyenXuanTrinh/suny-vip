"""Append-only corrections preserve original production evidence while fixing mistakes before stock posting."""
from alembic import op
revision='0006_production_corrections'
down_revision='0005_chat'
branch_labels=None
depends_on=None
def upgrade():
    op.execute('''CREATE TABLE production_report_corrections (
      id VARCHAR(36) PRIMARY KEY NOT NULL,organization_id VARCHAR(36) NOT NULL,
      report_id VARCHAR(36) NOT NULL,good_delta BIGINT NOT NULL,scrap_delta BIGINT NOT NULL,
      reason TEXT NOT NULL,actor_user_id VARCHAR(36) NOT NULL,created_at VARCHAR(32) NOT NULL,
      CHECK(typeof(good_delta)='integer' AND typeof(scrap_delta)='integer'),
      CHECK(good_delta!=0 OR scrap_delta!=0),
      FOREIGN KEY(organization_id,report_id) REFERENCES production_reports(organization_id,id),
      FOREIGN KEY(organization_id,actor_user_id) REFERENCES app_users(organization_id,id))''')
    op.execute('CREATE INDEX ix_production_corrections_report ON production_report_corrections(report_id)')
    for verb in ('UPDATE','DELETE'):
        op.execute(f"CREATE TRIGGER immutable_production_corrections_{verb.lower()} BEFORE {verb} ON production_report_corrections BEGIN SELECT RAISE(ABORT,'append-only production corrections'); END")
def downgrade():
    if op.get_bind().exec_driver_sql('SELECT COUNT(*) FROM production_report_corrections').scalar_one():raise RuntimeError('Correction history exists; restore a verified backup')
    op.execute('DROP TABLE production_report_corrections')
