"""Shared validation exception contract; application error handlers belong to member 1."""


class ValidationError(ValueError):
    code = 'VALIDATION_ERROR'
    status_code = 400

    def __init__(self, message='输入参数不合法', fields=None):
        super().__init__(message)
        self.message = message
        self.fields = dict(fields or {})
