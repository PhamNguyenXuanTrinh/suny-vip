"""Private chat history is separate from audit_log, as required by decision 11."""
from alembic import op
revision='0005_chat'
down_revision='0004_finance'
branch_labels=None
depends_on=None
def upgrade():
    op.execute('''CREATE TABLE ai_conversations (
      id VARCHAR(36) PRIMARY KEY NOT NULL, organization_id VARCHAR(36) NOT NULL,
      user_id VARCHAR(36) NOT NULL,title VARCHAR(200) NOT NULL,created_at VARCHAR(32) NOT NULL,
      CONSTRAINT uq_ai_conversations_organization_id UNIQUE(organization_id,id), FOREIGN KEY(organization_id,user_id) REFERENCES app_users(organization_id,id))''')
    op.execute('''CREATE TABLE ai_messages (
      id VARCHAR(36) PRIMARY KEY NOT NULL, organization_id VARCHAR(36) NOT NULL,
      conversation_id VARCHAR(36) NOT NULL,role VARCHAR(20) NOT NULL CHECK(role IN ('user','assistant')),
      content TEXT NOT NULL,sources_json TEXT,usage_json TEXT,status VARCHAR(20) NOT NULL,
      created_at VARCHAR(32) NOT NULL, FOREIGN KEY(organization_id,conversation_id) REFERENCES ai_conversations(organization_id,id))''')
    op.execute('CREATE INDEX ix_ai_messages_conversation ON ai_messages(conversation_id,created_at)')
def downgrade():
    if op.get_bind().exec_driver_sql('SELECT COUNT(*) FROM ai_conversations').scalar_one():raise RuntimeError('Private chat history exists; restore verified backup')
    op.execute('DROP TABLE ai_messages');op.execute('DROP TABLE ai_conversations')
