from dataclasses import dataclass


@dataclass(frozen=True)
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def normalize_pagination(page: int = 1, page_size: int = 20) -> Pagination:
    return Pagination(page=max(page, 1), page_size=min(max(page_size, 1), 100))
