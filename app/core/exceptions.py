from fastapi import HTTPException, status


class AppHTTPException(HTTPException):
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


def unauthorized(detail: str = "Not authenticated") -> AppHTTPException:
    return AppHTTPException(status.HTTP_401_UNAUTHORIZED, detail)


def forbidden(detail: str = "Permission denied") -> AppHTTPException:
    return AppHTTPException(status.HTTP_403_FORBIDDEN, detail)


def not_found(detail: str = "Resource not found") -> AppHTTPException:
    return AppHTTPException(status.HTTP_404_NOT_FOUND, detail)


def bad_request(detail: str) -> AppHTTPException:
    return AppHTTPException(status.HTTP_400_BAD_REQUEST, detail)
