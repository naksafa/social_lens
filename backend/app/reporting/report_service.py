"""Builds the exportable audit report (HTML, optionally PDF).

The report is assembled from stored artifacts only - the latest analytics run, its
insights, and the latest audit / strategy / content plan if they exist - so it is
reproducible and never triggers new analysis or AI calls.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Undefined, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.common import format_label, label, platform_label
from app.core.enums import GeneratedBy
from app.core.exceptions import FeatureUnavailableError, NotFoundError, ReportGenerationError
from app.core.logging import get_logger
from app.models import AIAudit, ContentPlan, Insight, MarketingStrategy, Project
from app.reporting import charts
from app.services.analysis_pipeline import get_run, load_sections

logger = get_logger(__name__)
TEMPLATES = Path(__file__).with_name("templates")

DISCLAIMER = (
    "Recommendations are based on available historical data and should be tested and adjusted over time. "
    "Statistical findings describe patterns in this dataset; they are correlational and do not guarantee future results."
)


def _latest(db: Session, model, project_id: uuid.UUID):  # type: ignore[no-untyped-def]
    return db.scalars(
        select(model).where(model.project_id == project_id).order_by(model.version.desc()).limit(1)
    ).first()


def _content(row) -> dict | None:  # type: ignore[no-untyped-def]
    if row is None:
        return None
    return {**row.content, "_generated_by": "AI" if row.generated_by == GeneratedBy.LLM else "Rule-based engine",
            "_model": row.model, "_version": row.version}  # fmt: skip


def _num(v: object, digits: int = 0) -> str:
    if v is None or isinstance(v, Undefined):
        return "—"
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(v)
    return f"{f:,.{digits}f}"


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
        self.env.filters.update(num=_num, platform=platform_label, fmt_label=format_label, label=label)

    def context(self, project: Project) -> dict:
        try:
            run = get_run(self.db, project.id)
        except NotFoundError as exc:
            raise ReportGenerationError("Run an analysis before generating a report.") from exc
        sections = load_sections(self.db, run.id)
        insights = list(self.db.scalars(select(Insight).where(Insight.run_id == run.id)))
        rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        insights.sort(key=lambda i: (rank.get(getattr(i.severity, "value", i.severity), 9), i.sentiment != "negative"))

        platform_charts = {}
        for p, s in sections["platforms"].items():
            color = charts.PLATFORM_COLORS.get(p, charts.SERIES[0])
            weekly = [(w["week"][5:], w.get("median_exposure")) for w in s["trends"]["weekly"]]
            fmt_rows = [
                (format_label(r["group"]), r.get("median_er"), r["low_sample"]) for r in s["formats"]["formats"]
            ]
            platform_charts[p] = {
                "trend": charts.line_chart(weekly, color, f"{platform_label(p)} - weekly median {s['exposure_metric'] or 'exposure'}",
                                           s["exposure_metric"] or ""),
                "formats": charts.bar_chart(fmt_rows, color, "Median engagement rate by format", "%"),
            }  # fmt: skip
        pillar_order = ["educational", "promotional", "social_proof", "entertainment", "brand", "community", "other"]
        mix_chart = charts.mix_bars(
            [(platform_label(p), s["pillars"]["pillar_distribution"]) for p, s in sections["platforms"].items()],
            pillar_order,
            "Content pillar mix (% of posts)",
        )
        return {
            "project": project,
            "business": project.business_profile,
            "run": run,
            "s": sections,
            "insights": insights,
            "findings": [f for f in sections.get("findings", []) if f["confidence"] in ("high", "medium")][:25],
            "audit": _content(_latest(self.db, AIAudit, project.id)),
            "strategy": _content(_latest(self.db, MarketingStrategy, project.id)),
            "plan": _content(_latest(self.db, ContentPlan, project.id)),
            "platform_charts": platform_charts,
            "mix_chart": mix_chart,
            "platform_colors": charts.PLATFORM_COLORS,
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "disclaimer": DISCLAIMER,
        }

    def render_html(self, project: Project) -> str:
        try:
            html = self.env.get_template("report.html").render(**self.context(project))
        except ReportGenerationError:
            raise
        except Exception as exc:
            logger.exception("report.failed", extra={"project_id": str(project.id)})
            raise ReportGenerationError("The report could not be generated.") from exc
        logger.info("report.generated", extra={"project_id": str(project.id), "bytes": len(html)})
        return html

    def render_pdf(self, project: Project) -> bytes:
        """PDF via WeasyPrint when installed (it needs native libraries; available in the Docker image).
        Otherwise the HTML report's print stylesheet produces the same layout via the browser's 'Save as PDF'."""
        try:
            from weasyprint import HTML  # type: ignore[import-not-found]
        except Exception as exc:  # ImportError or missing native libs (OSError)
            raise FeatureUnavailableError(
                "PDF export is not available on this server. Open the HTML report and use the browser's "
                "'Print > Save as PDF' - the report includes a print stylesheet.",
                {"hint": "Install WeasyPrint (included in the Docker image) to enable server-side PDF."},
            ) from exc
        return HTML(string=self.render_html(project)).write_pdf()
