"""Phân hệ 01: nền tảng kỹ thuật và kiểm kê API, không sửa giao diện V86."""
from fastapi import APIRouter, Request
from . import security
from .db import connect
router = APIRouter(prefix="/api/system", tags=["01 - Nen tang ERP"])

@router.get("/status")
def system_status(request: Request):
    user=security.current_user(request)
    with connect() as c:
        c.execute("SELECT 1").fetchone()
    return {"status":"ok", "database":"connected", "authenticated_as":user["username"], "module":"foundation", "live_ai_verified":False}

@router.get("/roles")
def system_roles(request: Request):
    user=security.current_user(request)
    security.require(user,"*")
    return {"roles":{k:sorted(v) for k,v in security.ROLES.items()}}

@router.get("/api-catalog")
def api_catalog(request: Request):
    user=security.current_user(request)
    security.require(user,"*")
    from .main import app
    items=[]
    for r in app.routes:
        path=getattr(r,"path","")
        if not path.startswith("/api/") or path in ("/api/openapi.json","/api/docs","/api/docs/oauth2-redirect"):
            continue
        for method in sorted(getattr(r,"methods",set()) or set()):
            if method in ("HEAD","OPTIONS"): continue
            items.append({"method":method,"path":path,"name":getattr(r,"name","")})
    return {"total":len(items),"endpoints":sorted(items,key=lambda x:(x["path"],x["method"])),"note":"Kiểm kê tuyến API; không phải xác nhận nghiệm thu nghiệp vụ"}


@router.get("/ui-contract")
def ui_contract(request: Request):
    """Read-only honest inventory: routes exist != UI connected."""
    user=security.current_user(request)
    security.require(user,"*")
    from pathlib import Path
    import re
    from .main import app
    html=(Path(__file__).resolve().parents[1]/"public/index.html").read_text(encoding="utf-8")
    menus=re.findall(r"\['(kpi|tasks|customers|orders|production|stock|incidents|hr|violations|payroll|costs|dashboard|daily)'\s*,",html)
    routes=[{"method":m,"path":r.path} for r in app.routes for m in sorted(getattr(r,"methods",set()) or set()) if r.path.startswith("/api/") and m not in ("HEAD","OPTIONS")]
    return {"interface":"V86 preserved", "ui_uses_browser_local_storage": "localStorage" in html,
            "ui_calls_backend_fetch":bool(re.search(r"\bfetch\s*\(",html)),
            "ui_uses_authenticated_api":bool(re.search(r"Authorization.*Bearer|Bearer.*Authorization",html)),
            "menus":sorted(set(menus)),"api_method_paths":len(routes),
            "verified_end_to_end_bindings":0,
            "acceptance":"BLOCKED", "reason":"UI V86 remains a local demo; no verified UI-to-API-to-database end-to-end contract"}


@router.get("/readiness")
def readiness(request: Request):
    """Authenticated operational readiness; not a business acceptance certificate."""
    user=security.current_user(request)
    security.require(user,"*")
    from .db import DB
    from pathlib import Path
    import sqlite3
    from .main import app
    with connect() as c:
        integrity=c.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys=c.execute("PRAGMA foreign_key_check").fetchall()
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required={"api_accounts","api_tokens","audit_log","api_idempotency"}
        db_ok=integrity=="ok" and not foreign_keys and required.issubset(tables)
    methods={(m,r.path) for r in app.routes for m in (getattr(r,"methods",None) or []) if r.path.startswith('/api/') and m not in ('HEAD','OPTIONS')}
    html=(Path(__file__).resolve().parents[1]/'public/index.html').read_text(encoding='utf8')
    checks={"database_integrity":db_ok,"database_required_tables":required.issubset(tables),"v86_frontend_present":'FLEX 3D' in html,"api_routes_registered":len(methods)>0}
    return {"checks":checks,"foundation_runtime_ready":all(checks.values()),"business_acceptance":"NOT_VERIFIED", "mobile_hardware_acceptance":"NOT_VERIFIED", "ui_api_binding_acceptance":"NOT_VERIFIED", "api_method_paths":len(methods),"database_path":str(DB),"note":"Readiness chi kiem tra nen tang tai may chu; khong chung minh ERP hoan thanh"}

@router.get("/audit-summary")
def audit_summary(request: Request, limit: int=30):
    user=security.current_user(request)
    security.require(user,"*")
    limit=max(1,min(limit,100))
    with connect() as c:
        rows=[dict(r) for r in c.execute("SELECT actor_id,action,entity_type,entity_id,at FROM audit_log ORDER BY at DESC LIMIT ?",(limit,))]
    return {"items":rows,"limit":limit,"note":"Khong tra ve thong tin bi mat hoac noi dung chung tu"}


@router.get("/acceptance-matrix")
def acceptance_matrix(request: Request):
    """Machine-readable evidence matrix. Never infer acceptance from API count."""
    user=security.current_user(request)
    security.require(user,"*")
    import re
    from pathlib import Path
    from .main import app
    html=(Path(__file__).resolve().parents[1]/"public/v86.html").read_text(encoding="utf-8")
    routes=sorted({(method,route.path) for route in app.routes for method in (getattr(route,"methods",None) or ()) if route.path.startswith("/api/") and method not in ("HEAD","OPTIONS")})
    html_ids=sorted(set(re.findall(r'\bid=["\']([^"\']+)',html)))
    static_buttons=len(re.findall(r'<button\b',html,re.I))
    dynamic_buttons=len(re.findall(r'<button\b',html[html.find('<script'):],re.I))
    fetch_calls=len(re.findall(r'\bfetch\s*\(',html))
    blockers=["Giao diện V86 chưa được đối chiếu từng thao tác với API và Database",
              "Chưa kiểm thử Android và iPhone thật",
              "Chưa nghiệm thu HTTPS, triển khai máy chủ và phục hồi sự cố",
              "Chưa kiểm thử thiết bị QR, cân và camera thật"]
    return {"status":"BLOCKED","api_method_paths":len(routes),"unique_api_paths":len(set(path for _,path in routes)),
            "frontend":{"static_button_tags":static_buttons,"dynamic_button_templates":dynamic_buttons,"unique_element_ids":len(html_ids),"fetch_calls":fetch_calls,"local_storage":'localStorage' in html},
            "criteria":[{"id":"P01-UI","name":"V86 giữ nguyên","verified":True,"evidence":"Kiểm thử đối chiếu SHA256 public/index.html và public/v86.html"},
                        {"id":"P01-E2E","name":"Nút giao diện tới API và Database","verified":False,"evidence":None},
                        {"id":"P01-MOBILE","name":"Android/iPhone thực tế","verified":False,"evidence":None},
                        {"id":"P01-OPS","name":"HTTPS, máy chủ, khôi phục sự cố","verified":False,"evidence":None},
                        {"id":"P01-DEVICE","name":"QR/cân/camera thật","verified":False,"evidence":None}],
            "blockers":blockers,"note":"Chỉ tiêu kiểm kê, không phải giấy chứng nhận nghiệm thu."}
