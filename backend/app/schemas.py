from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


class LevelEntry(BaseModel):
    type: Literal["level"] = "level"
    sb: int = Field(gt=0)
    bb: int = Field(gt=0)
    ante: int = Field(default=0, ge=0)
    minutes: int = Field(gt=0)


class BreakEntry(BaseModel):
    type: Literal["break"] = "break"
    minutes: int = Field(gt=0)


Entry = Annotated[Union[LevelEntry, BreakEntry], Field(discriminator="type")]

entry_adapter: TypeAdapter = TypeAdapter(Entry)
