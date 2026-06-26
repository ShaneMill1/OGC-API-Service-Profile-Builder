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

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, List, Literal, Optional

from annotated_types import Len
from edr_pydantic.collections import Collection as EDRCollection
from edr_pydantic.extent import Custom, Extent as EDRExtent, Spatial, Vertical
from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# edr-pydantic overrides — null-aware temporal interval
#
# OGC API - EDR allows open-ended temporal intervals where either bound is
# null (e.g. ["2020-01-01T00:00:00Z", null] means "from 2020 to present").
# edr-pydantic 0.7.x types both bounds as AwareDatetime, rejecting null.
# We override Temporal and Extent here so the profile builder accepts the
# spec-compliant form.  The fix should be upstreamed to edr-pydantic.
# ---------------------------------------------------------------------------

from edr_pydantic.base_model import EdrBaseModel  # noqa: E402 — after stdlib imports
from edr_pydantic.parameter import Parameters  # noqa: E402


class TemporalWithNullBounds(EdrBaseModel):
    """Temporal extent that allows null start/end bounds per OGC API - EDR."""

    interval: List[
        Annotated[List[Optional[AwareDatetime]], Len(min_length=2, max_length=2)]
    ]
    values: List[str]
    trs: str


class ExtentWithNullBounds(EDRExtent):
    """Extent that uses TemporalWithNullBounds instead of the upstream Temporal."""

    temporal: Optional[TemporalWithNullBounds] = None


class Classification(BaseModel):
    """Security classification metadata (e.g. for DGIWG / military profiles)."""
    level: str = Field(description="Classification level, e.g. 'NATO RESTRICTED (NR)'")
    system: str | None = Field(default=None, description="Classification system, e.g. 'NATO'")


class ProviderContact(BaseModel):
    """Point-of-contact details for the service provider (OWS/ISO-style)."""
    email: str | None = None
    phone: str | None = None
    hours: str | None = None
    instructions: str | None = None
    address: str | None = None
    postalcode: str | None = None
    city: str | None = None
    country: str | None = None


class Provider(BaseModel):
    """Service provider / responsible party (OWS ServiceProvider-like)."""
    name: str
    url: str | None = None
    contact: ProviderContact | None = None


class Collection(EDRCollection):
    """
    EDR Collection with a null-aware temporal extent and optional parameter_names.

    Differences from edr_pydantic.collections.Collection:

    - extent uses ExtentWithNullBounds so open-ended intervals like
      ["2020-01-01T00:00:00Z", null] are accepted (spec-compliant).

    - parameter_names is Optional (default None). edr-pydantic marks it as
      required, but OGC API - EDR Part 3 allows a profile to define the
      *schema* for parameter objects via parameter_schema without mandating
      any specific parameter names in the profile document itself.

    - post_queries controls whether POST operations are generated for this
      collection's data query endpoints. None means inherit the profile-level
      allow_post_queries default. Set to True or False to override per-collection.
    """

    extent: Optional[ExtentWithNullBounds] = None  # type: ignore[assignment]
    parameter_names: Optional[Parameters] = Field(  # type: ignore[assignment]
        default=None,
        description=(
            "Map of parameter id → Parameter object. "
            "Optional — omit when using parameter_schema to describe the structure "
            "without mandating specific parameter names."
        ),
    )
    post_queries: Optional[bool] = Field(
        default=None,
        description=(
            "Override the profile-level allow_post_queries setting for this collection. "
            "True generates POST alongside GET for all data query endpoints. "
            "False suppresses POST even if allow_post_queries is True at profile level. "
            "Omit (null) to inherit the profile-level default."
        ),
    )
    # Optional per-collection metadata. When set, overrides the profile-level
    # value for this collection. Round-tripped into profile_config.json.
    classification: Optional[Classification] = None
    provider: Optional[Provider] = None
    metadata_date: Optional[str] = None
    resource_service_publish_date: Optional[str] = None
    resource_default_locale: Optional[str] = None


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


class CrsConstraint(BaseModel):
    """An enum or regex constraint on a CRS/TRS/VRS value or list.

    Exactly one of `allowed` or `pattern` must be set.
    """
    allowed: list[str] | None = Field(
        default=None,
        description="Enumerated list of accepted values",
    )
    pattern: str | None = Field(
        default=None,
        description="Regular expression that accepted values must match",
    )

    @model_validator(mode="after")
    def exactly_one(self) -> CrsConstraint:
        if self.allowed is None and self.pattern is None:
            raise ValueError("Either 'allowed' or 'pattern' must be specified")
        if self.allowed is not None and self.pattern is not None:
            raise ValueError("Only one of 'allowed' or 'pattern' may be specified, not both")
        return self


class ExtentRequirements(BaseModel):
    """Profile-level extent restrictions per OGC API - EDR Part 3.

    CRS/TRS/VRS constraints are split into two distinct concerns:

    - ``extent_crs`` / ``extent_trs`` / ``extent_vrs`` — constrain the single
      CRS/TRS/VRS value used to *express* the extent (``extent.spatial.crs``,
      ``extent.temporal.trs``, ``extent.vertical.vrs``).  Typically this is
      just CRS84 / Gregorian.

    - ``supported_crs`` / ``supported_trs`` / ``supported_vrs`` — constrain
      the list of CRS/TRS/VRS values the service *supports* for queries
      (the top-level ``crs`` array and ``data_queries.*.variables.crs_details``).
      This is usually broader than the extent CRS.
    """
    minimum_bbox: list[float] = Field(
        min_length=4, max_length=4,
        description="Minimum spatial bounds [minLon, minLat, maxLon, maxLat]",
    )

    # --- Extent CRS/TRS/VRS (single value on extent object) ---
    extent_crs: CrsConstraint | None = Field(
        default=None,
        description="Constraint on extent.spatial.crs — the CRS the extent is expressed in",
    )
    extent_trs: CrsConstraint | None = Field(
        default=None,
        description="Constraint on extent.temporal.trs — the TRS the temporal extent is expressed in",
    )
    extent_vrs: CrsConstraint | None = Field(
        default=None,
        description="Constraint on extent.vertical.vrs — the VRS the vertical extent is expressed in",
    )

    # --- Supported CRS/TRS/VRS (lists — what the service supports for queries) ---
    supported_crs: CrsConstraint | None = Field(
        default=None,
        description=(
            "Constraint on the top-level crs array and crs_details — "
            "the CRS values the service supports for data queries. "
            "Typically broader than extent_crs."
        ),
    )
    supported_trs: CrsConstraint | None = Field(
        default=None,
        description="Constraint on supported TRS values for data queries",
    )
    supported_vrs: CrsConstraint | None = Field(
        default=None,
        description="Constraint on supported VRS values for data queries",
    )

    @model_validator(mode="after")
    def validate_crs_specification(self) -> ExtentRequirements:
        if self.extent_crs is None and self.supported_crs is None:
            raise ValueError(
                "At least one of 'extent_crs' or 'supported_crs' must be specified"
            )
        return self


class OutputFormat(BaseModel):
    """Output format with schema reference per OGC API - EDR Part 3."""
    name: str = Field(description="Format name (e.g., GeoJSON, CoverageJSON)")
    media_type: str = Field(description="MIME type (e.g., application/geo+json)")
    schema_ref: str | None = Field(default=None, description="URL to schema definition")


class Submitter(BaseModel):
    """A single entry in the document's submitters table (page iv).

    Allows each submitter to carry their own affiliation, rather than sharing
    a single organisation across every editor.
    """
    name: str
    affiliation: str | None = None
    role: str | None = Field(
        default=None,
        description="Role annotation shown next to the name, e.g. 'editor' or 'contributor'",
    )


class NormativeReference(BaseModel):
    """An additional normative/bibliographic reference for the References section.

    Rendered as a Metanorma bibliography entry of the form
    ``* [[[<anchor>,<citation>]]], <title>``.
    """
    anchor: Annotated[str, Field(pattern=r"^[A-Za-z0-9_\-]+$")] = Field(
        description="Cross-reference anchor (letters, digits, dash, underscore), e.g. DGIWG-250",
    )
    citation: str = Field(description="Short citation label, e.g. 'DGIWG 250' or 'OGC 19-086r6'")
    title: str = Field(description="Full reference title")


# Metanorma OGC document stages (`:status:` / `:docstage:`). See
# https://www.metanorma.org/author/ogc/ref/document-attributes/
DocStatus = Literal[
    "draft",
    "work-item-draft",
    "swg-draft",
    "oab-review",
    "public-rfc",
    "tc-vote",
    "approved",
    "published",
    "deprecated",
    "rescinded",
    "retired",
    "legacy",
]

# Loose ISO 8601 date (YYYY-MM-DD) check for document dates.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DocumentMetadata(BaseModel):
    """Metanorma/OGC document header metadata for PDF compilation."""
    doc_number: str
    doc_type: str = Field(
        default="draft-standard",
        description=(
            "Metanorma OGC :doctype: value (e.g. 'draft-standard', 'standard', "
            "'best-practice', 'engineering-report'). Drives the cover-page document type."
        ),
    )
    doc_subtype: Literal["implementation", "best-practice", "engineering-report", "profile"] = "implementation"
    status: DocStatus | None = Field(
        default=None,
        description=(
            "Metanorma OGC :status:/:docstage: value (e.g. 'swg-draft', 'approved'). "
            "Combined with doc_type/doc_subtype this produces the cover-page sub-title."
        ),
    )
    editors: list[str] = Field(default_factory=list)
    submitting_orgs: list[str] = Field(default_factory=list)
    submitters: list[Submitter] = Field(
        default_factory=list,
        description=(
            "Structured submitters table (name + affiliation + role) for page iv. "
            "When provided, takes precedence over the editors/submitting_orgs fallback."
        ),
    )
    keywords: list[str] = Field(default_factory=list)
    copyright_year: int = Field(default=2026)
    # Title-page dates. Map to Metanorma attributes:
    #   submission_date  -> :received-date:  (:submissionDate:)
    #   approval_date    -> :issued-date:    (:approvalDate:)
    #   publication_date -> :published-date: (:publicationDate:)
    # Format: YYYY-MM-DD. When omitted, falls back to {copyright_year}-01-01.
    submission_date: str | None = Field(default=None, description="Submission date (YYYY-MM-DD)")
    approval_date: str | None = Field(default=None, description="Approval date (YYYY-MM-DD)")
    publication_date: str | None = Field(default=None, description="Publication date (YYYY-MM-DD)")
    notice: str | None = Field(
        default=None,
        description=(
            "Custom notice text rendered in the document front matter. Note: the OGC "
            "cover-page legal notice itself is generated by Metanorma from doc_type/status; "
            "this field adds a notice paragraph in the preface."
        ),
    )
    normative_references: list[NormativeReference] = Field(
        default_factory=list,
        description="Additional normative references appended to the References section.",
    )
    external_id: str | None = None

    @field_validator("submission_date", "approval_date", "publication_date")
    @classmethod
    def _valid_date(cls, v: str | None) -> str | None:
        if v is not None and not _DATE_RE.match(v):
            raise ValueError("date must be in YYYY-MM-DD format")
        return v


class PubSubServer(BaseModel):
    """A single pub/sub server endpoint."""
    name: str
    description: str = ""
    host: str
    port: int | None = None
    protocol: Literal["amqp", "mqtt", "kafka", "ws", "wss"] = "amqp"
    pathname: str | None = None


class CollectionPubSub(BaseModel):
    """Per-collection pub/sub filter overrides."""
    filters: list[SubscriptionFilter] = Field(default_factory=list)


class PubSubConfig(BaseModel):
    """Optional OGC API - EDR Part 2 (PubSub) configuration."""
    broker_host: str = "localhost"
    broker_port: int = Field(default=5672, ge=1, le=65535)
    protocol: Literal["amqp", "mqtt", "kafka"] = "amqp"
    collections: list[str] = Field(default_factory=list, description="Collection IDs that support PubSub")
    filters: list[SubscriptionFilter] = Field(default_factory=list)
    servers: list[PubSubServer] = Field(default_factory=list, description="Additional server endpoints (ws, wss)")
    collection_filters: dict[str, CollectionPubSub] = Field(default_factory=dict, description="Per-collection filter overrides")


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
    description: str | None = Field(
        default=None,
        description=(
            "Human-readable description of the service profile. Surfaces in the "
            "OpenAPI info block and the landing page response."
        ),
    )
    keywords: list[str] = Field(
        default_factory=list,
        description=(
            "Service-level keywords describing what this profile provides. "
            "Surfaces in the OpenAPI info block (as x-keywords) and the landing "
            "page response. Distinct from document_metadata.keywords, which are "
            "for the OGC PDF header."
        ),
    )
    server_url: str | None = Field(default=None, description="Base URL for implementation (not used in profile OpenAPI per standard)")
    provider: Provider | None = Field(
        default=None,
        description=(
            "Service provider / responsible party. Surfaces in the OpenAPI info.contact "
            "block (name/url/email plus x- extensions for phone, address, etc.) and as the "
            "document point of contact."
        ),
    )
    classification: Classification | None = Field(
        default=None,
        description=(
            "Security classification of the service/profile (e.g. NATO RESTRICTED). "
            "Surfaces as a banner in the generated document and as info.x-classification "
            "in the OpenAPI."
        ),
    )
    metadata_date: str | None = Field(
        default=None,
        description="Date the metadata was last updated (ISO 8601 string). Surfaces as info.x-metadata-date.",
    )
    resource_service_publish_date: str | None = Field(
        default=None,
        description="Date the resource/service was published (ISO 8601 string). Surfaces as info.x-resource-publish-date.",
    )
    resource_default_locale: str | None = Field(
        default=None,
        description="Default locale of the resource (e.g. 'eng'). Surfaces as info.x-default-locale.",
    )
    collections: list[Collection] = Field(min_length=1)
    collection_examples: dict[str, dict] = Field(default_factory=dict)
    requirements: list[Requirement] = Field(default_factory=list)
    abstract_tests: list[AbstractTest] = Field(default_factory=list)
    pubsub: PubSubConfig | None = None
    processes: list[dict] = Field(default_factory=list)
    document_metadata: DocumentMetadata | None = None
    
    # OGC API - EDR Part 3 specific fields
    required_conformance_classes: list[str] = Field(
        default_factory=lambda: [
            "http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core"
        ],
        description="Conformance classes that implementations must declare"
    )
    extent_requirements: ExtentRequirements | None = Field(
        default=None,
        description="Profile-level extent restrictions"
    )
    output_formats: list[OutputFormat] = Field(
        default_factory=list,
        description="Profile-level output format definitions with schema references"
    )
    allow_post_queries: bool = Field(
        default=False,
        description=(
            "When True, generate POST operations alongside GET for all EDR data query "
            "endpoints (position, area, radius, cube, trajectory, corridor, items, locations). "
            "The POST body mirrors the GET query parameters as a JSON object, allowing clients "
            "to submit large geometries that would exceed URL length limits. "
            "Can be overridden per-collection via the collection's post_queries field."
        ),
    )
    collection_id_pattern: str | None = Field(
        default=None,
        description="Regex pattern for valid collection IDs"
    )
    spec_uri_base: str = Field(
        default="http://www.opengis.net/spec/ogcapi-edr-3/1.0",
        description=(
            "Base URI for the requirements class and conformance class identifiers. "
            "Defaults to the OGC API - EDR Part 3 namespace. Override this to publish "
            "under a different SDO namespace (e.g. a DGIWG location). Used to derive "
            "req_uri and conf_uri, which appear in the OpenAPI x-ogc-profile link, the "
            "requirements/conformance AsciiDoc identifiers, and the conformance section."
        ),
    )
    parameter_name_pattern: str | None = Field(
        default=None,
        description="Regex pattern that all parameter_names keys must match"
    )
    parameter_schema: dict | None = Field(
        default=None,
        description=(
            "JSON Schema fragment used as the additionalProperties definition for "
            "parameter_names in the generated OpenAPI. Replaces the default parameter "
            "schema, allowing full control over required fields, patterns, and custom "
            "extension properties (e.g. metocean:standard_name). Must be a valid JSON "
            "Schema object."
        ),
    )

    # OGC identifiers derived from name and spec_uri_base — not user-supplied directly
    @property
    def req_uri(self) -> str:
        return f"{self.spec_uri_base.rstrip('/')}/req/{self.name}"

    @property
    def conf_uri(self) -> str:
        return f"{self.spec_uri_base.rstrip('/')}/conf/{self.name}"

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

    @model_validator(mode="after")
    def validate_parameter_completeness(self) -> ServiceProfile:
        """Validate parameter_names completeness per OGC API - EDR Part 3 REQ_parameter-names."""
        for coll in self.collections:
            if not coll.parameter_names:
                continue
            for param_name, param in coll.parameter_names.root.items():
                if not hasattr(param, 'unit') or param.unit is None:
                    raise ValueError(
                        f"Parameter '{param_name}' in collection '{coll.id}' must specify unit "
                        f"(required by OGC API - EDR Part 3 REQ_parameter-names)"
                    )
                if not hasattr(param, 'observedProperty') or param.observedProperty is None:
                    raise ValueError(
                        f"Parameter '{param_name}' in collection '{coll.id}' must specify observedProperty"
                    )
        return self

    @model_validator(mode="after")
    def validate_pubsub_conformance(self) -> ServiceProfile:
        """Ensure pub/sub requirements include Part 2 conformance per REQ_pubsub."""
        if self.pubsub:
            # Check if there's a requirement for Part 2 conformance
            has_part2_req = any(
                "part 2" in req.statement.lower() or "part-2" in req.statement.lower() or "pubsub" in req.statement.lower()
                for req in self.requirements
            )
            if not has_part2_req:
                # Auto-add the requirement
                self.requirements.append(
                    Requirement(
                        id="pubsub-part2-conformance",
                        statement="The service SHALL conform to OGC API - EDR Part 2: Publish-Subscribe",
                        parts=[
                            "The service SHALL implement the channels defined in the AsyncAPI document",
                            "The service SHALL support the message payloads defined for each channel"
                        ]
                    )
                )
        return self

    @model_validator(mode="after")
    def validate_collection_id_pattern(self) -> ServiceProfile:
        """Validate collection IDs against collection_id_pattern if specified."""
        if not self.collection_id_pattern:
            return self
        try:
            pat = re.compile(self.collection_id_pattern)
        except re.error as exc:
            raise ValueError(f"Invalid collection_id_pattern regex: {exc}") from exc
        for coll in self.collections:
            if not pat.fullmatch(coll.id):
                raise ValueError(
                    f"Collection id '{coll.id}' does not match "
                    f"collection_id_pattern '{self.collection_id_pattern}'"
                )
        return self

    @model_validator(mode="after")
    def validate_collection_extent_patterns(self) -> ServiceProfile:
        """Validate collection CRS/TRS/VRS values against extent_requirements constraints."""
        if not self.extent_requirements:
            return self
        er = self.extent_requirements

        # Helper: check a single value against a CrsConstraint
        def _check(label: str, value: str, constraint: "CrsConstraint | None") -> None:
            if constraint is None:
                return
            if constraint.allowed is not None and value not in constraint.allowed:
                raise ValueError(
                    f"{label} '{value}' is not in allowed list {constraint.allowed}"
                )
            if constraint.pattern is not None:
                pat = _compile_optional_pattern(label, constraint.pattern)
                if pat and not pat.fullmatch(value):
                    raise ValueError(
                        f"{label} '{value}' does not match pattern '{constraint.pattern}'"
                    )

        for coll in self.collections:
            # --- extent.spatial.crs → extent_crs ---
            crs = coll.extent.spatial.crs if coll.extent and coll.extent.spatial else None
            if crs:
                _check(f"Collection '{coll.id}' extent.spatial.crs", crs, er.extent_crs)

            # --- extent.temporal.trs → extent_trs ---
            trs = coll.extent.temporal.trs if coll.extent and coll.extent.temporal else None
            if trs:
                _check(f"Collection '{coll.id}' extent.temporal.trs", trs, er.extent_trs)

            # --- extent.vertical.vrs → extent_vrs ---
            vrs = coll.extent.vertical.vrs if coll.extent and coll.extent.vertical else None
            if vrs:
                _check(f"Collection '{coll.id}' extent.vertical.vrs", vrs, er.extent_vrs)

            # --- top-level crs array → supported_crs ---
            if coll.crs and er.supported_crs:
                for crs_val in coll.crs:
                    _check(f"Collection '{coll.id}' crs[]", crs_val, er.supported_crs)

            # --- crs_details / crs shorthand in data_queries → supported_crs ---
            if coll.data_queries and er.supported_crs:
                for qt_name, qt_val in coll.data_queries:
                    if qt_val is None:
                        continue
                    extra = (
                        qt_val.link.variables.model_extra
                        if hasattr(qt_val.link.variables, "model_extra")
                        else {}
                    ) or {}
                    crs_details = extra.get("crs_details", []) or []
                    for entry in crs_details:
                        dq_crs = entry.get("crs") if isinstance(entry, dict) else None
                        if dq_crs:
                            _check(
                                f"Collection '{coll.id}' data_queries.{qt_name}.crs_details",
                                dq_crs,
                                er.supported_crs,
                            )
                    # `crs` is an accepted shorthand: a plain list of CRS URIs at
                    # the query level, equivalent to crs_details: [{crs: ...}].
                    for dq_crs in (extra.get("crs", []) or []):
                        if isinstance(dq_crs, str):
                            _check(
                                f"Collection '{coll.id}' data_queries.{qt_name}.crs",
                                dq_crs,
                                er.supported_crs,
                            )
        return self

    @model_validator(mode="after")
    def validate_default_output_format(self) -> ServiceProfile:
        """Ensure a query's default_output_format is one of its output_formats."""
        for coll in self.collections:
            if not coll.data_queries:
                continue
            for qt_name, qt_val in coll.data_queries:
                if qt_val is None:
                    continue
                extra = (
                    qt_val.link.variables.model_extra
                    if hasattr(qt_val.link.variables, "model_extra")
                    else {}
                ) or {}
                variables = qt_val.link.variables
                default = getattr(variables, "default_output_format", None) or extra.get("default_output_format")
                if default is None:
                    continue
                formats = getattr(variables, "output_formats", None) or extra.get("output_formats") or []
                if formats and default not in formats:
                    raise ValueError(
                        f"Collection '{coll.id}' data_queries.{qt_name}: "
                        f"default_output_format '{default}' is not in output_formats {formats}"
                    )
        return self

    @model_validator(mode="after")
    def validate_parameter_name_patterns(self) -> ServiceProfile:
        """Validate parameter_names keys against parameter_name_pattern if specified."""
        if not self.parameter_name_pattern:
            return self
        try:
            pat = re.compile(self.parameter_name_pattern)
        except re.error as exc:
            raise ValueError(f"Invalid parameter_name_pattern regex: {exc}") from exc
        for coll in self.collections:
            if not coll.parameter_names:
                continue
            for name in coll.parameter_names.root:
                if not pat.fullmatch(name):
                    raise ValueError(
                        f"Parameter name '{name}' in collection '{coll.id}' "
                        f"does not match parameter_name_pattern "
                        f"'{self.parameter_name_pattern}'"
                    )
        return self

    @model_validator(mode="after")
    def validate_parameter_schema(self) -> ServiceProfile:
        """Validate that parameter_schema is a dict (JSON Schema object) if specified."""
        if self.parameter_schema is not None:
            if not isinstance(self.parameter_schema, dict):
                raise ValueError("parameter_schema must be a JSON Schema object (dict)")
            # Must have at least 'type' or 'properties' or '$ref' to be meaningful
            if not any(k in self.parameter_schema for k in ("type", "properties", "$ref", "allOf", "anyOf", "oneOf")):
                raise ValueError(
                    "parameter_schema must contain at least one of: "
                    "type, properties, $ref, allOf, anyOf, oneOf"
                )
        return self


def _compile_optional_pattern(label: str, pattern: str | None) -> re.Pattern | None:
    """Compile a regex pattern string, raising ValueError on invalid syntax."""
    if pattern is None:
        return None
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid {label} regex '{pattern}': {exc}") from exc
