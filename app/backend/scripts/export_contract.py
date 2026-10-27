"""Export the actual OpenAPI, migrated SQLite DDL and the 44-table relationship diagram."""
import argparse,json,sqlite3,tempfile
from pathlib import Path
from backend.app.main import create_app
from backend.app.models import metadata,schema
from backend.scripts.migrate_db import migrate

def export(destination):
    out=Path(destination).resolve();out.mkdir(parents=True,exist_ok=True)
    api=create_app().openapi()
    (out/'openapi.json').write_text(json.dumps(api,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with tempfile.TemporaryDirectory() as temp:
        db=Path(temp)/'schema.sqlite3';migrate(db)
        with sqlite3.connect(db) as c:
            ddl=[r[0] for r in c.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END,name")]
        (out/'schema.sql').write_text('-- Generated from a fresh, migrated database. Quantity columns use exact integer millionths.\n\n'+';\n\n'.join(ddl)+';\n',encoding='utf-8')
    lines=['erDiagram','    direction TB']
    for name,spec in schema.items():
        lines.append('    '+name+' {')
        for field,s in spec['columns'].items():
            typ={'integer':'bigint','quantity':'decimal18_6','uuid':'uuid','boolean':'boolean','datetime':'datetimeUTC','date':'date','string':'string'}[s['type']]
            flag=' PK' if field=='id' else ' FK' if 'references' in s else ' UK' if [field] in spec.get('unique',[]) else ''
            lines.append('        '+typ+' '+field+flag)
        lines.append('    }')
    for name,spec in schema.items():
        for field,s in spec['columns'].items():
            if 'references' in s:
                parent=s['references'].split('.')[0]
                lines.append('    '+parent+(' |o--o{ ' if s['nullable'] else ' ||--o{ ')+name+' : "'+field+'"')
    (out/'ERD_44_TABLES.mmd').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    inventory=[]
    for path,methods in api['paths'].items():
        for method,operation in methods.items():
            if method in ('get','post','patch','put','delete'):
                inventory.append({'method':method.upper(),'path':path,'authenticated':bool(operation.get('security')),'summary':operation.get('summary'),'request_body':operation.get('requestBody'),'responses':operation.get('responses')})
    (out/'api_inventory.json').write_text(json.dumps({'api_method_paths':len(inventory),'business_tables':len(schema),'total_domain_and_support_tables':len(metadata.tables),'endpoints':inventory},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'business_tables':len(schema),'total_tables':len(metadata.tables),'api_method_paths':len(inventory)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='docs/current');a=p.parse_args();print(json.dumps(export(a.output)))
