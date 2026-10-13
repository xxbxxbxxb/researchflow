from typing import Any


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None) -> None:
        self.status,self.code,self.message,self.details = status,code,message,details
