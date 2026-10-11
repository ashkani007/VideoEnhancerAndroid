from fastapi import HTTPException


class AppError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, extra: dict | None = None):
        super().__init__(status_code=status_code, detail={"code": code, "message": message, **(extra or {})})
        self.code = code


def not_found(what: str = "Resource") -> AppError:
    return AppError(404, "not_found", f"{what} not found")


def forbidden(message: str = "Not allowed") -> AppError:
    return AppError(403, "forbidden", message)


def conflict(code: str, message: str) -> AppError:
    return AppError(409, code, message)


def bad_request(code: str, message: str) -> AppError:
    return AppError(400, code, message)
