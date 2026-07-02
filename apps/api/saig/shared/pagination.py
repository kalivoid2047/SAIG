from fastapi import Query
from pydantic import BaseModel


class PageParams(BaseModel):
    page: int
    page_size: int


def page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class PageMeta(BaseModel):
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class Page[T](BaseModel):
    data: list[T]
    meta: PageMeta

    @classmethod
    def build(cls, items: list[T], total: int, params: PageParams) -> "Page[T]":
        pages = (total + params.page_size - 1) // params.page_size if total else 0
        return cls(
            data=items,
            meta=PageMeta(
                page=params.page,
                pageSize=params.page_size,
                totalItems=total,
                totalPages=pages,
            ),
        )
