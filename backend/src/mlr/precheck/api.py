"""
FastAPI surface for the MLR Precheck POC.

Implements `GET /api/precheck/{asset_id}` (the only endpoint Layer 3
needs end-to-end). Other endpoints from `MLR_PRECHECK_API.md` will be
added by later layers:

  - POST /api/precheck                 (multipart upload — Layer 2)
  - GET  /api/precheck/{id}/history    (history strands)
  - POST /api/vvpm/annotate            (Veeva integration)
  - GET  /api/precheck/library/coverage
  - GET  /api/precheck/patterns/{id}

Auth and Veeva brokering omitted — POC runs unauthenticated locally.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from mlr.fixtures import assets as fixture_assets
from mlr.precheck import abbreviation_check
from mlr.precheck.asset_builder import build_asset
from mlr.precheck.schema import Asset, ErrorBody, ErrorResponse


app = FastAPI(
    title="Atlas MLR Precheck POC",
    version="0.1.0",
    description=(
        "Server-side slice for the Atlas MLR X-Ray POC. Implements the "
        "Layer 3 (abbreviation precheck) end-to-end against an in-memory "
        "fixture store."
    ),
)


def _error(http_status: int, code: str, message: str) -> JSONResponse:
    """Standard error envelope per API contract §0."""
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=http_status, content=body.model_dump())


@app.get(
    "/api/precheck/{asset_id}",
    response_model=Asset,
    responses={
        404: {"model": ErrorResponse, "description": "asset_not_found"},
        422: {"model": ErrorResponse, "description": "profile_required / extraction_failed"},
    },
)
def get_precheck(asset_id: str, force: bool = False) -> Asset:  # noqa: ARG001 (force unused for POC)
    """
    Return the precheck `Asset` for the given asset_id.

    For the POC: asset_id must match a fixture in `mlr.fixtures.assets`.
    Layer 3 (abbreviation precheck) is the only check that runs.
    """
    extracted = fixture_assets.get(asset_id)
    if extracted is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "asset_not_found",
                    "message": (
                        f"No asset with id '{asset_id}'. Known fixture ids: "
                        f"{', '.join(fixture_assets.all_ids())}"
                    ),
                }
            },
        )

    abbreviation_verdicts = abbreviation_check.run(extracted)

    # Future: claim_check + document_check + cascade_adapter all append
    # into the verdict list before build_asset.
    verdicts = list(abbreviation_verdicts)

    return build_asset(
        extracted=extracted,
        verdicts=verdicts,
        profile_selected_by="metadata",
        library_sample_size=0,  # no live library in this slice
        pdf_url=f"/api/preview/{asset_id}.pdf",
        page_count=1,
    )


@app.get("/api/health")
def health() -> dict:
    """Liveness probe."""
    return {"ok": True, "fixtures": fixture_assets.all_ids()}
