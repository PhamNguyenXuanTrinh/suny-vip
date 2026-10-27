"""Isolated browser-test server. Never opens the configured production database."""
from pathlib import Path
import argparse,os,secrets
from backend.app.core.config import Settings
from backend.app.database import make_engine
from backend.scripts.migrate_db import migrate
from backend.scripts.create_admin import provision
from backend.app.main import create_app
import uvicorn

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    db=Path(a.database).resolve()
    if db.exists():raise SystemExit('QA requires a new database path; existing databases are never reset')
    migrate(db);engine=make_engine('sqlite:///'+str(db))
    provision(engine,'QA','Môi trường kiểm thử SUNNY','qa_admin',os.getenv('SUNNY_QA_PASSWORD','Browser-QA-password-2026!'),False)
    engine.dispose()
    cfg=Settings(db,secrets.token_urlsafe(48),db.parent/'uploads')
    uvicorn.run(create_app(cfg),host='127.0.0.1',port=a.port,log_level='warning')
