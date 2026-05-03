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

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from mlr.api_views.document_xray import to_document_xray
from mlr.fixtures import assets as fixture_assets
from mlr.ingest import baseline_bootstrap, library_bootstrap
from mlr.precheck import abbreviation_check, baseline, claim_check, document_check, library, structural_check
from mlr.precheck.asset_builder import build_asset
from mlr.precheck.dependency_rules import load_default_catalog
from mlr.precheck.schema import Asset, ErrorBody, ErrorResponse
from mlr.preview import render as pdf_render


app = FastAPI(
    title="Atlas MLR Precheck POC",
    version="0.3.0",
    description=(
        "Server-side slice for the Atlas MLR X-Ray POC. Implements "
        "Layer 1 (claim drift), Layer 2 (regulatory dependency rules), "
        "and Layer 3 (abbreviation precheck) end-to-end against an "
        "in-memory fixture store."
    ),
)


# POC permits any origin so the static frontend can be opened from
# `file://` or any localhost dev server. Tighten before shipping.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# Catalog loaded once at app boot — we don't need hot-reload for the POC.
_CATALOG = load_default_catalog()


# Bootstrap the approved-claim library from the extractor service's
# eval outputs (option B in DECISIONS.md D5/D25). When the directory
# isn't present (fresh checkout, CI), the hardcoded library stays as
# the fallback.
def _bootstrap_library_at_startup() -> int:
    extractions_dir = fixture_assets._EXTRACTOR_OUTPUTS  # noqa: SLF001 — POC convenience
    if not extractions_dir.is_dir():
        return library.total_size()
    bootstrapped = library_bootstrap.bootstrap_from_dir(extractions_dir)
    if bootstrapped:
        library.set_library(bootstrapped)
    return library.total_size()


_LIBRARY_SIZE_AT_BOOT = _bootstrap_library_at_startup()


# Bootstrap the structural baseline (D29) — curated file wins, falls
# back to walking the same UK extraction directory.
def _bootstrap_baseline_at_startup() -> int:
    extractions_dir = fixture_assets._EXTRACTOR_OUTPUTS  # noqa: SLF001
    exemplars = baseline_bootstrap.load_default_baseline(extractions_dir)
    if exemplars:
        baseline.set_baseline(exemplars)
    return baseline.total_size()


_BASELINE_SIZE_AT_BOOT = _bootstrap_baseline_at_startup()


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

    structural_verdicts = structural_check.run(extracted)
    claim_verdicts = claim_check.run(extracted)
    document_verdicts = document_check.run(extracted, _CATALOG)
    abbreviation_verdicts = abbreviation_check.run(extracted)

    # Future: cascade_adapter appends `layer:cascade` zones here.
    verdicts = [*structural_verdicts, *claim_verdicts, *document_verdicts, *abbreviation_verdicts]

    return build_asset(
        extracted=extracted,
        verdicts=verdicts,
        profile_selected_by="metadata",
        library_sample_size=library.total_size(),
        pdf_url=f"/api/preview/{asset_id}.pdf",
        page_count=1,
    )


@app.get("/api/document-xray/{asset_id}")
def get_document_xray(asset_id: str) -> dict:
    """
    Document X-Ray payload — the new primary view (replaces the
    /api/precheck route as the frontend's data source).

    Runs all 3 precheck layers, then hands the asset + verdicts to the
    Document X-Ray adapter. Returns claims[] + elements[] +
    compliance_findings[] per the design handoff at
    `design_handoff_atlas_extraction/design_handoff_document_xray/`.
    """
    extracted = fixture_assets.get(asset_id)
    if extracted is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "asset_not_found",
                    "message": f"No asset with id '{asset_id}'.",
                }
            },
        )

    verdicts = [
        *structural_check.run(extracted),
        *claim_check.run(extracted),
        *document_check.run(extracted, _CATALOG),
        *abbreviation_check.run(extracted),
    ]
    return to_document_xray(extracted, verdicts)


@app.get("/api/assets")
def list_assets() -> list[dict]:
    """
    Lightweight asset directory for the frontend's switcher panel.

    Returns one entry per fixture with the bare minimum the UI needs to
    render a list (asset_id + brand + market + doc_type + identity-ish
    label). The full Asset payload is only computed when the user
    selects an asset (via GET /api/precheck/{asset_id}).
    """
    out: list[dict] = []
    for a in fixture_assets.all_assets():
        out.append({
            "asset_id": a.asset_id,
            "brand": a.meta.brand,
            "market": a.meta.market,
            "language": a.meta.language,
            "doc_type": a.meta.doc_type,
            "code": a.meta.code,
            "prepared": a.meta.prepared,
            "label": f"{a.meta.brand} · {a.meta.market} · {a.meta.doc_type}",
            "has_pdf": bool(a.pdf_path),
        })
    return out


def _resolve_pdf_path(asset_id: str) -> Path:
    """Common pre-flight for the preview routes — 404s with a structured body."""
    extracted = fixture_assets.get(asset_id)
    if extracted is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "asset_not_found", "message": f"No asset '{asset_id}'."}},
        )
    if not extracted.pdf_path:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "preview_not_available", "message": "No PDF wired for this asset."}},
        )
    pdf_path = Path(extracted.pdf_path)
    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "preview_file_missing",
                    "message": f"PDF file not found on disk: {pdf_path}",
                }
            },
        )
    return pdf_path


@app.get("/api/preview/{asset_id}/pages")
def get_preview_pages(asset_id: str, dpi: int = 144) -> dict:
    """
    Per-page metadata so the frontend can lay out the preview pane and
    convert PDF point coords to pixel coords for the bbox overlay.
    """
    pdf_path = _resolve_pdf_path(asset_id)
    metas = pdf_render.page_metadata(pdf_path, dpi=dpi)
    return {
        "asset_id": asset_id,
        "page_count": len(metas),
        "dpi": dpi,
        "pages": [
            {
                "page": m.page,
                "width_pt": m.width_pt,
                "height_pt": m.height_pt,
                "width_px": m.width_px,
                "height_px": m.height_px,
            }
            for m in metas
        ],
    }


@app.get("/api/preview/{asset_id}/page/{page_number}.png")
def get_preview_page_png(asset_id: str, page_number: int, dpi: int = 144):
    """Render a single PDF page as PNG bytes at the requested DPI."""
    pdf_path = _resolve_pdf_path(asset_id)
    try:
        png = pdf_render.render_page_png(pdf_path, page_number, dpi=dpi)
    except IndexError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "page_out_of_range", "message": str(e)}},
        )
    return Response(
        content=png,
        media_type="image/png",
        # Long-cached by (asset_id, page, dpi) — re-render only when the
        # underlying PDF changes (which we don't support yet).
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/api/preview/{asset_id}.pdf")
def get_preview_pdf(asset_id: str):
    """
    Stream the source PDF for a given asset_id (legacy iframe path).

    The newer paged-PNG preview (`/page/{n}.png`) is what the frontend
    overlay layer renders against. This endpoint stays for raw-PDF
    download or external embedding.
    """
    pdf_path = _resolve_pdf_path(asset_id)
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{pdf_path.name}"'},
    )


@app.get("/api/health")
def health() -> dict:
    """Liveness probe."""
    return {
        "ok": True,
        "fixtures": fixture_assets.all_ids(),
        "rules_loaded": len(_CATALOG.rules),
        "catalog_version": _CATALOG.catalog_version,
        "library_size": library.total_size(),
        "library_bootstrapped": library.total_size() != 3,  # 3 = the hardcoded fallback
        "baseline_size": baseline.total_size(),
    }
