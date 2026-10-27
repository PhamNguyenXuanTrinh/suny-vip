"""Read-only ledger/cache reconciliation; does not silently repair data."""
from pathlib import Path
import argparse,json,sqlite3

def check(path):
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as c:
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0];fks=c.execute('PRAGMA foreign_key_check').fetchall()
        stock=c.execute('''SELECT u.id,u.remaining_quantity,COALESCE(SUM(m.quantity_delta),0) FROM inventory_units u LEFT JOIN inventory_movements m ON m.inventory_unit_id=u.id GROUP BY u.id HAVING u.remaining_quantity != COALESCE(SUM(m.quantity_delta),0)''').fetchall()
        customer=c.execute('''SELECT a.id,a.amount,COALESCE(SUM(e.amount),0) FROM customer_payment_allocations a LEFT JOIN payment_allocation_events e ON e.customer_allocation_id=a.id GROUP BY a.id HAVING a.amount!=COALESCE(SUM(e.amount),0)''').fetchall()
        supplier=c.execute('''SELECT a.id,a.amount,COALESCE(SUM(e.amount),0) FROM supplier_payment_allocations a LEFT JOIN payment_allocation_events e ON e.supplier_allocation_id=a.id GROUP BY a.id HAVING a.amount!=COALESCE(SUM(e.amount),0)''').fetchall()
        debt=c.execute('''SELECT c.id,c.current_debt_amount,COALESCE((SELECT SUM(i.total_amount-COALESCE((SELECT SUM(a.amount) FROM customer_payment_allocations a WHERE a.invoice_id=i.id),0)) FROM customer_invoices i WHERE i.customer_id=c.id AND i.status IN ('issued','partially_paid','paid','overdue')),0) FROM customers c''').fetchall()
        debt=[r for r in debt if r[1]!=r[2]]
        production=[]
        for oid,released,header_good,header_scrap,status in c.execute('SELECT id,released_quantity,good_quantity,scrap_quantity,status FROM production_orders').fetchall():
            capacity=released;final_good=total_scrap=0
            operations=c.execute('SELECT id,status FROM production_order_operations WHERE production_order_id=? ORDER BY sequence_no',(oid,)).fetchall()
            for op_id,op_status in operations:
                good,scrap=c.execute('SELECT COALESCE(SUM(good_quantity),0),COALESCE(SUM(scrap_quantity),0) FROM production_reports WHERE operation_id=?',(op_id,)).fetchone()
                dg,ds=c.execute('SELECT COALESCE(SUM(x.good_delta),0),COALESCE(SUM(x.scrap_delta),0) FROM production_report_corrections x JOIN production_reports r ON r.id=x.report_id WHERE r.operation_id=?',(op_id,)).fetchone()
                good+=dg;scrap+=ds
                if min(good,scrap)<0 or good+scrap>capacity or (op_status=='completed' and good+scrap!=capacity):production.append([oid,op_id,'operation_input_mismatch'])
                capacity=good;final_good=good;total_scrap+=scrap
            if header_good!=final_good or header_scrap!=total_scrap:production.append([oid,'header_report_mismatch'])
            if status=='completed':
                output=c.execute("SELECT COALESCE(SUM(quantity_delta),0) FROM inventory_movements WHERE reference_type='production_order' AND reference_id=? AND movement_type='production_output'",(oid,)).fetchone()[0]
                if header_good+header_scrap!=released or output!=header_good:production.append([oid,'finished_stock_mismatch'])
    return {'integrity':integrity,'foreign_key_errors':fks,'stock_mismatches':stock,'customer_allocation_mismatches':customer,'supplier_allocation_mismatches':supplier,'debt_cache_mismatches':debt,'production_mismatches':production,'passed':integrity=='ok' and not any((fks,stock,customer,supplier,debt,production))}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);a=p.parse_args();result=check(a.database);print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)
