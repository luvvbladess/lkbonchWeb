class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def not_found(message: str = "Запись не найдена") -> ApiError:
    return ApiError(404, "not_found", message)


def forbidden(message: str = "Недостаточно прав") -> ApiError:
    return ApiError(403, "forbidden", message)


def invalid(code: str, message: str) -> ApiError:
    return ApiError(422, code, message)
