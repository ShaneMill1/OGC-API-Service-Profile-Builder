# =================================================================
#
# Authors: Shane Mill <shane.mill@noaa.gov>
#
# Copyright (c) 2026 Shane Mill
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================
"""
OGC API - EDR Part 3: Service Profile — Authoritative Pydantic Models

These models ARE the schema. Instantiating a ServiceProfile validates the
entire profile structure before any files are written.

Collections are modelled using edr-pydantic (https://github.com/KNMI/edr-pydantic)
so that EDR data model types are authoritative and shared with the broader ecosystem.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from edr_pydantic.collections import Collection as EDRCollection
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations (profile-specific; EDR data model enums live in edr-pydantic)
# ---------------------------------------------------------------------------

class FilterType(str, Enum):
    string = "string"
    number = "number"
    array = "array"
    boolean = "boolean"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class Requirement(BaseModel):
    id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9\-]*$")]
    statement: str
    parts: list[str] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def no_trailing_dash(cls, v: str) -> str:
        if v.endswith("-"):
            raise ValueError("requirement id must not end with a dash")
        return v


class AbstractTest(BaseModel):
    id: str  # mirrors the requirement id it tests
    requirement_id: str
    steps: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def ids_must_match(self) -> AbstractTest:
        if self.id != self.requirement_id:
            raise ValueError("AbstractTest.id must equal requirement_id")
        return self


class SubscriptionFilter(BaseModel):
    name: str
    description: str
    type: FilterType = FilterType.string


# Collection IS the edr-pydantic Collection — no wrapper needed.
# edr_pydantic.collections.Collection models id, extent, data_queries,
# output_formats, parameter_names, links — all authoritative EDR fields.
Collection = EDRCollection


class PubSubConfig(BaseModel):
    """Optional OGC API - EDR Part 2 (PubSub) configuration."""
    broker_host: str = "localhost"
    broker_port: int = Field(default=5672, ge=1, le=65535)
    protocol: Literal["amqp", "mqtt", "kafka"] = "amqp"
    filters: list[SubscriptionFilter] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Root model — the authoritative profile definition
# ---------------------------------------------------------------------------

class ServiceProfile(BaseModel):
    """
    OGC API - EDR Part 3 Service Profile.

    Instantiating this model validates the entire profile. Export to dict/JSON
    for downstream serialization (OpenAPI, AsyncAPI, AsciiDoc, YAML config).
    """

    name: Annotated[str, Field(pattern=r"^[a-z0-9_]+$")]
    title: str
    version: str = "1.0"
    server_url: str | None = None
    collections: list[Collection] = Field(min_length=1)
    collection_examples: dict[str, dict] = Field(default_factory=dict)
    requirements: list[Requirement] = Field(default_factory=list)
    abstract_tests: list[AbstractTest] = Field(default_factory=list)
    pubsub: PubSubConfig | None = None
    processes: list[dict] = Field(default_factory=list)

    # OGC identifiers derived from name — not user-supplied
    @property
    def req_uri(self) -> str:
        return f"http://www.opengis.net/spec/ogcapi-edr-3/1.0/req/{self.name}"

    @property
    def conf_uri(self) -> str:
        return f"http://www.opengis.net/spec/ogcapi-edr-3/1.0/conf/{self.name}"

    @model_validator(mode="after")
    def tests_reference_valid_requirements(self) -> ServiceProfile:
        req_ids = {r.id for r in self.requirements}
        for test in self.abstract_tests:
            if test.requirement_id not in req_ids:
                raise ValueError(
                    f"AbstractTest '{test.id}' references unknown requirement '{test.requirement_id}'"
                )
        return self

    @model_validator(mode="after")
    def no_duplicate_collection_ids(self) -> ServiceProfile:
        ids = [c.id for c in self.collections]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate collection ids in profile")
        return self
