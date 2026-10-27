import argparse,json
from backend.app.core.config import ROOT,Settings
from backend.scripts.setup_local import load_config
from backend.app.database import verify_database
import uvicorn

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default=str(ROOT/'.env.local'));p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8765);p.add_argument('--check',action='store_true');p.add_argument('--open-browser',action='store_true');a=p.parse_args()
    load_config(a.config);cfg=Settings.from_env()
    if not (ROOT/'frontend/dist/index.html').is_file():raise SystemExit('Thiếu bản build giao diện. Chạy npm ci và npm run build trong frontend.')
    if a.check:print(json.dumps({'configured':True,'database':verify_database(cfg.database_path),'frontend_built':True,'openai_required':False}))
    else:
        print(f'SUNNY ERP: http://{a.host}:{a.port}')
        if a.open_browser:
            import threading,time,urllib.request,webbrowser
            def open_when_ready():
                url=f'http://127.0.0.1:{a.port}'
                for _ in range(120):
                    try:
                        with urllib.request.urlopen(url+'/api/v1/health',timeout=1) as r:
                            if r.status==200:webbrowser.open(url);return
                    except Exception:pass
                    time.sleep(.25)
            threading.Thread(target=open_when_ready,daemon=True).start()
        uvicorn.run('backend.app.main:app',host=a.host,port=a.port,log_level='warning')
