"""Current ERP application. Legacy entry point remains available only for regression checks."""
from contextlib import asynccontextmanager
import logging, uuid
import os, time
from pathlib import Path
from collections import defaultdict, deque
import sqlalchemy as sa
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import Settings
from backend.app.database import make_engine
from backend.scripts.migrate_db import migrate
from backend.app.services.auth import router as auth_router

log = logging.getLogger('sunny.erp')

def create_app(settings=None):
    @asynccontextmanager
    async def lifespan(app):
        cfg = settings or Settings.from_env()
        
        # --- SỬA ĐỔI QUAN TRỌNG: TỰ ĐỘNG NHẬN DIỆN POSTGRESQL ---
        db_url = cfg.database_path if cfg.database_path.startswith('postgresql://') else 'sqlite:///' + str(Path(cfg.database_path).resolve())
        migrate(db_url)
        app.state.settings = cfg
        app.state.engine = make_engine(db_url)
        # --------------------------------------------------------

        import asyncio, os
        async def alert_loop():
            from backend.app.services.jobs import evaluate_all
            while True:
                await asyncio.sleep(max(30, int(os.getenv('SUNNY_ALERT_INTERVAL_SECONDS', '300'))))
                try: 
                    await asyncio.to_thread(evaluate_all, app.state.engine)
                except Exception as exc: 
                    log.error('Alert job failed: %s', type(exc).__name__)
        task = asyncio.create_task(alert_loop())
        try: 
            yield
        finally:
            task.cancel()
            try: 
                await task
            except asyncio.CancelledError: 
                pass
            app.state.engine.dispose()
            
    from backend.app.schemas.common import ErrorEnvelope
    app = FastAPI(title='SUNNY AI FLEX 3D ERP', version='2.2.0', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url='/api/openapi.json', responses={code: {'model': ErrorEnvelope, 'description': description} for code, description in {401: 'Cần đăng nhập', 403: 'Không có quyền', 404: 'Không tìm thấy trong phạm vi được phép', 409: 'Xung đột trạng thái hoặc số dư', 422: 'Dữ liệu không hợp lệ', 429: 'Vượt giới hạn tốc độ'}.items()})
    
    origins = list(settings.origins) if settings else [x for x in os.getenv('SUNNY_ALLOWED_ORIGINS', 'http://127.0.0.1:8765').split(',') if x]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET', 'POST', 'PATCH'], allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'])
    
    buckets = defaultdict(deque)
    @app.middleware('http')
    async def request_context(request, call_next):
        request.state.request_id = str(uuid.uuid4())
        sensitive = {'/api/v1/auth/login': 20, '/api/v1/auth/refresh': 60, '/api/v1/ai/chat': 20, '/api/v1/documents/upload': 20}
        rate_path = '/api/v1/documents/upload' if request.url.path == '/api/v1/documents' else request.url.path
        if request.method == 'POST' and rate_path in sensitive:
            key = (request.client.host if request.client else 'unknown', rate_path)
            bucket = buckets[key]
            now = time.monotonic()
            while bucket and bucket[0] < now - 60: 
                bucket.popleft()
            if len(bucket) >= sensitive[rate_path]: 
                return JSONResponse(status_code=429, content={'error': {'code': 'RATE_LIMIT', 'message': 'Thao tác quá nhanh, vui lòng thử lại sau một phút', 'request_id': request.state.request_id}}, headers={'Retry-After': '60'})
            bucket.append(now)
        response = await call_next(request)
        response.headers.update({'X-Request-ID': request.state.request_id, 'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store'})
        if not request.url.path.startswith('/api/docs'):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response
        
    def error(request, code, message, status):
        return JSONResponse(status_code=status, content={'error': {'code': code, 'message': message, 'request_id': getattr(request.state, 'request_id', None)}})
        
    @app.exception_handler(HTTPException)
    async def http_error(request, exc): 
        return error(request, 'HTTP_' + str(exc.status_code), str(exc.detail), exc.status_code)
        
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        def message(e):
            ctx = e.get('ctx', {})
            kind = e['type']
            if kind == 'greater_than': return 'Giá trị phải lớn hơn ' + str(ctx.get('gt'))
            if kind == 'greater_than_equal': return 'Giá trị tối thiểu là ' + str(ctx.get('ge'))
            if kind == 'less_than_equal': return 'Giá trị tối đa là ' + str(ctx.get('le'))
            if kind == 'string_too_short': return 'Cần ít nhất ' + str(ctx.get('min_length')) + ' ký tự'
            if kind == 'string_too_long': return 'Tối đa ' + str(ctx.get('max_length')) + ' ký tự'
            return {'missing': 'Không được bỏ trống', 'int_type': 'Phải nhập số nguyên', 'int_parsing': 'Phải nhập số nguyên', 'uuid_parsing': 'Mã liên kết không hợp lệ', 'extra_forbidden': 'Trường này không được phép nhập', 'literal_error': 'Giá trị không thuộc danh mục cho phép', 'decimal_max_places': 'Số lượng chỉ có tối đa 6 chữ số thập phân', 'decimal_max_digits': 'Số lượng vượt giới hạn 18 chữ số', 'datetime_parsing': 'Ngày giờ không hợp lệ', 'date_from_datetime_parsing': 'Ngày không hợp lệ'}.get(kind, 'Dữ liệu không đúng định dạng hoặc ngoài giới hạn cho phép')
        fields = [{'field': '.'.join(str(v) for v in e['loc'][1:]), 'message': message(e)} for e in exc.errors()]
        result = error(request, 'VALIDATION', 'Dữ liệu nhập chưa hợp lệ', 422)
        import json
        body = json.loads(result.body)
        body['error']['fields'] = fields
        return JSONResponse(status_code=422, content=body)
        
    @app.exception_handler(sa.exc.IntegrityError)
    async def integrity_error(request, exc): 
        return error(request, 'CONFLICT', 'Dữ liệu trùng hoặc vi phạm ràng buộc nghiệp vụ', 409)
        
    @app.exception_handler(sa.exc.StatementError)
    async def statement_error(request, exc): 
        return error(request, 'VALIDATION', 'Dữ liệu không đúng định dạng', 422)
        
    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        log.error('Unhandled request %s class %s', getattr(request.state, 'request_id', ''), type(exc).__name__)
        return error(request, 'INTERNAL', 'Không xử lý được yêu cầu', 500)
        
    @app.get('/api/v1/health')
    def health(request: Request):
        with request.app.state.engine.begin() as c: 
            c.exec_driver_sql('SELECT 1')
        from backend.app.core.clock import business_today, business_zone
        return {'status': 'ok', 'version': '2.2.0', 'live_ai_verified': False, 'instance_id': os.getenv('SUNNY_INSTANCE_ID'), 'business_date': business_today().isoformat(), 'business_timezone': business_zone().key}
        
    app.include_router(auth_router)
    from backend.app.services.data import router as data_router
    app.include_router(data_router)
    from backend.app.services.workflows import router as workflow_router
    app.include_router(workflow_router)
    from backend.app.services.inventory import router as inventory_router
    app.include_router(inventory_router)
    from backend.app.services.production import router as production_router
    app.include_router(production_router)
    from backend.app.services.tasks import router as task_router
    app.include_router(task_router)
    from backend.app.services.finance import router as finance_router
    app.include_router(finance_router)
    from backend.app.services.reports import router as report_router
    app.include_router(report_router)
    from backend.app.services.jobs import router as job_router
    from backend.app.services.documents import router as document_router
    app.include_router(job_router)
    app.include_router(document_router)
    from backend.app.services.ai import router as ai_router
    app.include_router(ai_router)
    
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from fastapi.openapi.docs import get_swagger_ui_html
    from fastapi.openapi.utils import get_openapi
    
    swagger = Path(__file__).resolve().parents[1] / 'static/swagger'
    if swagger.is_dir(): 
        app.mount('/api/_docs', StaticFiles(directory=swagger), name='api-documentation-assets')
        
    @app.get('/api/docs', include_in_schema=False)
    def api_documentation():
        import re, base64, hashlib
        response = get_swagger_ui_html(openapi_url='/api/openapi.json', title='SUNNY ERP API', swagger_js_url='/api/_docs/swagger-ui-bundle.js', swagger_css_url='/api/_docs/swagger-ui.css', swagger_favicon_url='/api/_docs/favicon-32x32.png', swagger_ui_parameters={'displayRequestDuration': True, 'persistAuthorization': False})
        scripts = re.findall(r'<script>(.*?)</script>', response.body.decode(), re.S)
        hashes = ' '.join("'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'" for s in scripts)
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' " + hashes + "; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        return response
        
    dist = Path(__file__).resolve().parents[2] / 'frontend/dist'
    if (dist / 'assets').is_dir(): 
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')
        
    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path.startswith('api/') or not (dist / 'index.html').is_file(): 
            raise HTTPException(404, 'Không tìm thấy trang')
        return FileResponse(dist / 'index.html', media_type='text/html')
        
    def openapi_contract():
        if app.openapi_schema is not None: 
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema.setdefault('components', {}).setdefault('securitySchemes', {})['BearerAuth'] = {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT', 'description': 'Access token nhận từ /api/v1/auth/login; API key OpenAI không dùng để đăng nhập ERP.'}
        public = {'/api/v1/auth/login', '/api/v1/auth/refresh', '/api/v1/health'}
        for path, operations in schema.get('paths', {}).items():
            if path.startswith('/api/v1/') and path not in public:
                for method, operation in operations.items():
                    if method in ('get', 'post', 'patch', 'delete', 'put'): 
                        operation['security'] = [{'BearerAuth': []}]
        app.openapi_schema = schema
        return schema
    app.openapi = openapi_contract
    return app

app = create_app()