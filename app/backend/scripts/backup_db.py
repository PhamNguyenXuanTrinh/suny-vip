import argparse,json
from pathlib import Path
from datetime import datetime,timezone
from backend.app.core.config import ROOT
from backend.scripts.setup_local import load_config
from scripts.backup_database import backup
import os

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default=str(ROOT/'.env.local'));p.add_argument('--output');a=p.parse_args()
    load_config(a.config);source=Path(os.getenv('SUNNY_ERP_DB',ROOT/'runtime/database/sunny.sqlite3'))
    target=Path(a.output) if a.output else source.parent/'backups'/('sunny-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite3')
    print(json.dumps({'backup':str(target),**backup(source,target)}))
