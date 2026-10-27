"""Initialize configuration and an administrator without any OpenAI credential."""
import argparse,getpass,json,os,re,secrets
from pathlib import Path
import sqlalchemy as sa
from backend.app.core.config import ROOT
from backend.app.database import make_engine
from backend.scripts.migrate_db import migrate
from backend.scripts.create_admin import provision

def load_config(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Chưa có cấu hình. Chạy bước thiết lập trước.')
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        key,sep,value=line.partition('=');key=key.strip()
        if sep and re.fullmatch(r'[A-Z][A-Z0-9_]*',key):
            value=value.strip()
            if len(value)>=2 and value[0]==value[-1] and value[0] in ('"',"'"):value=value[1:-1]
            os.environ.setdefault(key,value)

def setup(config,data_dir,create_admin=True):
    config=Path(config).resolve();data_dir=Path(data_dir).resolve()
    if not config.exists():
        config.parent.mkdir(parents=True,exist_ok=True)
        values={'SUNNY_JWT_SECRET':secrets.token_urlsafe(48),'SUNNY_ERP_DB':str(data_dir/'database/sunny.sqlite3'),'SUNNY_UPLOAD_DIR':str(data_dir/'uploads'),'SUNNY_ALLOWED_ORIGINS':'http://127.0.0.1:8765','SUNNY_OPENAI_MODEL':'gpt-4o','SUNNY_ALERT_INTERVAL_SECONDS':'300','OPENAI_API_KEY':''}
        fd=os.open(config,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write('\n'.join(k+'='+v for k,v in values.items())+'\n')
    load_config(config)
    from backend.app.core.config import Settings
    cfg=Settings.from_env();result=migrate(cfg.database_path)
    engine=make_engine('sqlite:///'+str(cfg.database_path.resolve()))
    try:
        from backend.app.models import metadata as md
        with engine.begin() as c:count=c.execute(sa.select(sa.func.count()).select_from(md.tables['app_users'])).scalar_one()
        if count==0 and create_admin:
            username=input('Tên đăng nhập quản trị [admin]: ').strip() or 'admin'
            password=getpass.getpass('Mật khẩu quản trị, tối thiểu 12 ký tự: ')
            if password!=getpass.getpass('Nhập lại mật khẩu: '):raise ValueError('Mật khẩu không trùng nhau')
            provision(engine,'SUNNY','SUNNY GROUP',username,password,True)
            result['administrator_created']=True
        else:result['administrator_created']=False
    finally:engine.dispose()
    return {'config_file':str(config),'database':str(cfg.database_path),'integrity':result['integrity'],'administrator_created':result['administrator_created'],'openai_required':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default=str(ROOT/'.env.local'));p.add_argument('--data-dir',default=str(ROOT/'runtime'));p.add_argument('--no-admin',action='store_true');a=p.parse_args()
    print(json.dumps(setup(a.config,a.data_dir,not a.no_admin),ensure_ascii=False))
