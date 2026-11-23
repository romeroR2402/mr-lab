class RpcError(Exception):
    """Error controlado que se devuelve al frontend con un código estable."""

    def __init__(self, code: str, message: str, data: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}


class NotImplementedOperation(RpcError):
    def __init__(self, operation: str, stage: str):
        super().__init__(
            "not_implemented",
            f"La operación '{operation}' todavía no está implementada (planificada para {stage}).",
            {"operation": operation, "stage": stage},
        )
