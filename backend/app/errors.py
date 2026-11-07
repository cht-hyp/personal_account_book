"""Shared exception contract; the app-level handlers live in ``create_app``.

All exceptions mapped to a JSON response share ``code`` / ``message`` /
``fields`` / ``status_code``. The single ``ApiError`` handler reads those
attributes instead of branching on type, so member 3's ``ValidationError``
subclasses (415 ``UNSUPPORTED_MEDIA_TYPE``, 400 ``INVALID_JSON``) are covered
without extra registration.
"""


class ApiError(Exception):
    """Base error with a stable (code, status_code) and a human-readable message."""

    code = 'INTERNAL_ERROR'
    status_code = 500

    def __init__(self, message='服务器内部错误', fields=None):
        super().__init__(message)
        self.message = message
        self.fields = dict(fields or {})


class ValidationError(ApiError):
    """Invalid request input; ``fields`` maps field name to its message."""

    code = 'VALIDATION_ERROR'
    status_code = 400

    def __init__(self, message='输入参数不合法', fields=None):
        super().__init__(message, fields)


class StorageError(ApiError):
    """Data file could not be read or written; mapped to 500 STORAGE_ERROR."""

    code = 'STORAGE_ERROR'
    status_code = 500

    def __init__(self, message='数据存储失败，请稍后重试', fields=None):
        super().__init__(message, fields)
