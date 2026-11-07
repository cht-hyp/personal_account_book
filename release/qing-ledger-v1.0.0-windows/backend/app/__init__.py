"""Application factory and assembly (member 1).

``create_app`` wires configuration, storage, blueprints, error handlers and
static file serving. Business modules (3/4/5) and storage (2) may not all be
merged yet; the factory keeps the app runnable and registers them as they
arrive, without creating placeholder files owned by other members.
"""

import importlib
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

from .config import Config
from .errors import ApiError, StorageError

# Blueprints owned by members 3/4/5, registered when their routes module exists.
_OPTIONAL_BLUEPRINTS = (
    ('record_write', 'record_write_bp'),
    ('record_query', 'record_query_bp'),
    ('statistics', 'statistics_bp'),
)


class _MissingStore:
    """Placeholder installed until member 2 merges ``storage.py``.

    Health and categories work without storage; any route that actually reads
    or writes records fails loudly instead of returning a fake result.
    """

    def initialize(self):
        """No-op: there is nothing to initialize before the real store lands."""

    def list_records(self):
        raise StorageError('存储模块尚未接入（storage.py 未合并）')

    def append_record(self, record):
        raise StorageError('存储模块尚未接入（storage.py 未合并）')


def _load_store(app):
    """Create the storage instance and put it in ``app.extensions['record_store']``."""
    try:
        from .storage import JsonRecordStore
    except ImportError:
        app.logger.warning(
            'storage.py（2 号）尚未合并，record_store 使用占位实现；'
            '记账/查询/统计接口暂不可用'
        )
        return _MissingStore()
    return JsonRecordStore(app.config['DATA_FILE'])


def _register_blueprints(app):
    from .routes.categories import categories_bp
    from .routes.health import health_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(categories_bp)

    for module_name, bp_name in _OPTIONAL_BLUEPRINTS:
        try:
            module = importlib.import_module(f'.routes.{module_name}', package=__package__)
        except ImportError:
            app.logger.warning('Blueprint %s 尚未就绪，跳过注册', bp_name)
            continue
        app.register_blueprint(getattr(module, bp_name))


def _register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        if error.status_code >= 500:
            app.logger.error('请求处理失败 code=%s: %s', error.code, error.message)
        return jsonify(error={
            'code': error.code,
            'message': error.message,
            'fields': error.fields,
        }), error.status_code

    @app.errorhandler(404)
    def handle_not_found(error):
        if request.path.startswith('/api/'):
            return jsonify(error={
                'code': 'NOT_FOUND',
                'message': '接口不存在',
                'fields': {},
            }), 404
        return 'Not Found', 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        if request.path.startswith('/api/'):
            return jsonify(error={
                'code': 'METHOD_NOT_ALLOWED',
                'message': '方法不支持',
                'fields': {},
            }), 405
        return 'Method Not Allowed', 405

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        app.logger.exception('未处理异常')
        if request.path.startswith('/api/'):
            return jsonify(error={
                'code': 'INTERNAL_ERROR',
                'message': '服务器内部错误',
                'fields': {},
            }), 500
        return 'Internal Server Error', 500


def _register_static(app):
    web_dir = Path(app.config['WEB_DIST_DIR'])
    index_file = web_dir / 'index.html'
    if not index_file.is_file():
        app.logger.warning('未找到 %s，静态页面未启用（仅提供 API）', index_file)
        return

    @app.route('/')
    def index():
        return send_from_directory(web_dir, 'index.html')

    @app.route('/<path:filename>')
    def static_files(filename):
        # Never let the catch-all shadow unknown /api routes: those must stay
        # JSON 404 (README 8.1). Registered /api blueprints are more specific
        # and still win; only truly unknown /api paths reach here.
        if filename == 'api' or filename.startswith('api/'):
            abort(404)
        return send_from_directory(web_dir, filename)


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    # 中文类别、备注以 UTF-8 原样返回，不转成 \uXXXX（3 号交接建议）。
    app.json.ensure_ascii = False

    app.extensions['record_store'] = _load_store(app)
    # 首次运行自动初始化；真实存储由 2 号实现，占位实现为无害空操作。
    app.extensions['record_store'].initialize()

    _register_blueprints(app)
    _register_error_handlers(app)
    _register_static(app)

    return app
