"""
统一异常体系。

所有业务异常继承 BaseAppException，包含：
- type:        错误类型标识（validation_error / block / warning）
- code:        业务错误码（INVALID_NPI / DUPLICATE_ORDER_SAME_DAY / ...）
- message:     人类可读的描述
- detail:      可选的附加信息（dict / list / None）
- http_status: HTTP 状态码

View 层只需 raise，exception_handler 统一捕获并格式化响应。
"""


class BaseAppException(Exception):
    """所有业务异常的基类。"""

    type = 'error'
    code = 'UNKNOWN_ERROR'
    http_status = 500

    def __init__(self, message, code=None, detail=None, http_status=None):
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.detail = detail
        super().__init__(message)


class ValidationError(BaseAppException):
    """输入验证失败。serializer 层抛出，400。"""

    type = 'validation_error'
    code = 'VALIDATION_ERROR'
    http_status = 400


class BlockError(BaseAppException):
    """业务规则阻止操作。service 层抛出，409。"""

    type = 'block'
    code = 'BUSINESS_BLOCK'
    http_status = 409


class WarningError(BaseAppException):
    """
    业务警告，需要用户确认后继续。

    与其他异常不同，WarningError 不代表"失败"，而是"暂停"。
    前端收到后展示 warnings，用户确认后带 confirm=true 重新提交。
    HTTP 409 — 表示当前状态下有冲突，需要客户端介入。
    """

    type = 'warning'
    code = 'CONFIRMATION_REQUIRED'
    http_status = 409
