"""Member 1: app factory, unified errors, data path and static serving.

Run from the project root:

    .\\.venv\\Scripts\\python.exe -m pytest tests/backend -v

Storage (member 2) and the write/query/statistics routes (members 3/4/5) are not
merged yet, so these tests cover only the pieces owned by member 1 and the
already-merged categories endpoint.
"""

from backend.app import create_app
from backend.app.errors import StorageError, ValidationError


def make_app(tmp_path, **overrides):
    """Build a test app with an isolated data file and (absent) web dir."""
    config = {
        'TESTING': True,
        'DATA_FILE': str(tmp_path / 'data' / 'records.json'),
        'WEB_DIST_DIR': str(tmp_path / 'web'),
        **overrides,
    }
    return create_app(config)


def test_health_ok(tmp_path):
    resp = make_app(tmp_path).test_client().get('/api/health')
    assert resp.status_code == 200
    assert resp.get_json() == {'data': {'status': 'ok'}}


def test_categories_ok(tmp_path):
    resp = make_app(tmp_path).test_client().get('/api/categories')
    assert resp.status_code == 200
    assert set(resp.get_json()['data']) == {'income', 'expense'}


def test_unknown_api_is_json_404(tmp_path):
    resp = make_app(tmp_path).test_client().get('/api/does-not-exist')
    assert resp.status_code == 404
    assert resp.get_json()['error']['code'] == 'NOT_FOUND'


def test_method_not_allowed_is_json_405(tmp_path):
    resp = make_app(tmp_path).test_client().post('/api/health')
    assert resp.status_code == 405
    assert resp.get_json()['error']['code'] == 'METHOD_NOT_ALLOWED'


def test_validation_error_response_shape(tmp_path):
    app = make_app(tmp_path)

    @app.route('/api/boom')
    def boom():
        raise ValidationError('金额错误', {'amount': '必须为字符串'})

    resp = app.test_client().get('/api/boom')
    assert resp.status_code == 400
    assert resp.get_json() == {
        'error': {
            'code': 'VALIDATION_ERROR',
            'message': '金额错误',
            'fields': {'amount': '必须为字符串'},
        }
    }


def test_storage_error_maps_to_500(tmp_path):
    app = make_app(tmp_path)

    @app.route('/api/boom-storage')
    def boom_storage():
        raise StorageError()

    resp = app.test_client().get('/api/boom-storage')
    assert resp.status_code == 500
    assert resp.get_json()['error']['code'] == 'STORAGE_ERROR'


def test_unexpected_error_maps_to_500_internal(tmp_path):
    app = make_app(tmp_path)

    @app.route('/api/boom-internal')
    def boom_internal():
        raise RuntimeError('boom')

    resp = app.test_client().get('/api/boom-internal')
    assert resp.status_code == 500
    assert resp.get_json()['error']['code'] == 'INTERNAL_ERROR'


def test_data_file_config_override(tmp_path):
    """Tests pass a temp data path via test_config, never the real ledger."""
    target = tmp_path / 'custom' / 'records.json'
    app = make_app(tmp_path, DATA_FILE=str(target))
    assert app.config['DATA_FILE'] == str(target)


def test_static_index_served(tmp_path):
    web = tmp_path / 'web'
    web.mkdir()
    (web / 'index.html').write_text('<html>hello</html>', encoding='utf-8')
    app = make_app(tmp_path, WEB_DIST_DIR=str(web))
    resp = app.test_client().get('/')
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == '<html>hello</html>'


def test_api_not_shadowed_by_static_catchall(tmp_path):
    web = tmp_path / 'web'
    web.mkdir()
    (web / 'index.html').write_text('<html>hello</html>', encoding='utf-8')
    app = make_app(tmp_path, WEB_DIST_DIR=str(web))
    client = app.test_client()
    assert client.get('/api/health').status_code == 200
    resp = client.get('/api/not-there')
    assert resp.status_code == 404
    assert resp.get_json()['error']['code'] == 'NOT_FOUND'


def test_real_write_query_statistics_survive_restart(tmp_path):
    config = {'TESTING': True, 'DATA_FILE': str(tmp_path / 'ledger.json'), 'WEB_DIST_DIR': str(tmp_path / 'web')}
    client = create_app(config).test_client()
    for kind, amount, category in [('income', '1000.00', '工资'), ('expense', '20.00', '餐饮'), ('expense', '5.00', '交通')]:
        response = client.post('/api/records', json={'date': '2026-11-07', 'type': kind, 'amount': amount, 'category': category, 'note': ''})
        assert response.status_code == 201
    reopened = create_app(config).test_client()
    assert reopened.get('/api/records?limit=10&offset=0').get_json()['data']['total'] == 3
    filtered = reopened.get('/api/records?type=expense&category=餐饮').get_json()['data']
    assert filtered['total'] == 1
    stats = reopened.get('/api/statistics').get_json()['data']
    assert (stats['income_cents'], stats['expense_cents'], stats['balance_cents']) == (100000, 2500, 97500)


def test_internal_import_error_is_not_hidden(tmp_path, monkeypatch):
    import builtins
    import pytest
    original = builtins.__import__

    def broken(name, *args, **kwargs):
        if name == 'routes.record_query':
            raise ImportError('internal dependency failure')
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', broken)
    with pytest.raises(ImportError, match='internal dependency failure'):
        make_app(tmp_path)
