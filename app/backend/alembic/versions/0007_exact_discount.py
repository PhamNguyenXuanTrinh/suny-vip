"""Exact INTEGER VND HALF_UP rounding; all existing line IDs are retained."""
from alembic import op
revision='0007_exact_discount'
down_revision='0006_production_corrections'
branch_labels=None
depends_on=None
GROSS=('((quantity / 1000000) * unit_price + (quantity % 1000000) * (unit_price / 1000000) + ((quantity % 1000000) * (unit_price % 1000000) + 500000) / 1000000)')
def replace(check):
    with op.batch_alter_table('sales_order_lines',recreate='always') as batch:
        batch.drop_constraint('ck_sales_order_lines_rule_1',type_='check')
        batch.create_check_constraint('ck_sales_order_lines_rule_1',check)
def upgrade():replace(f"typeof({GROSS}) = 'integer' AND discount_amount <= {GROSS}")
def downgrade():
    if op.get_bind().exec_driver_sql('SELECT COUNT(*) FROM sales_order_lines').scalar_one():raise RuntimeError('Nonempty database: rollback by verified SQLite backup')
    replace('discount_amount <= (quantity * unit_price / 1000000.0)')
