import argparse,json
from scripts.backup_database import restore

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--backup',required=True);p.add_argument('--target',required=True);a=p.parse_args()
    print(json.dumps({'restored_database':a.target,**restore(a.backup,a.target)}))
