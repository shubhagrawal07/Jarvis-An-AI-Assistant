from pydantic import BaseModel, Field


class CommandTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class CommandResultOut(BaseModel):
    action: str
    message: str
    task_ids: list[str] = []
    detail: dict = {}
