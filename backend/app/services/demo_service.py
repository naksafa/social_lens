"""Demo mode: create a fully analyzed project from synthetic data in one call.

The synthetic data is written in each platform's native export format and pushed
through the *real* pipeline (upload -> platform detection -> fuzzy mapping ->
normalization -> validation -> analytics), so the demo exercises everything a real
upload would.
"""

from datetime import date

import numpy as np
from sqlalchemy.orm import Session

from app.core.enums import Platform
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models import Project
from app.schemas.project import BusinessProfileBase, ProjectCreate
from app.services.analysis_pipeline import AnalysisPipeline
from app.services.file_service import FileService
from app.services.normalization_service import NormalizationService
from app.services.project_service import ProjectService
from app.synthetic.exporters import inject_quality_issues, native_export
from app.synthetic.generator import SyntheticGenerator
from app.synthetic.profiles import DEMO_BUSINESSES, DemoBusiness

logger = get_logger(__name__)


def get_business(key: str) -> DemoBusiness:
    try:
        return DEMO_BUSINESSES[key]
    except KeyError as exc:
        raise NotFoundError("Unknown demo business.", {"available": list(DEMO_BUSINESSES)}) from exc


def generate_files(
    business: DemoBusiness,
    days: int = 90,
    seed: int = 42,
    platforms: list[Platform] | None = None,
    posts_per_platform: int | None = None,
    end_date: date | None = None,
    inject_issues: bool = True,
) -> list[tuple[Platform, str, bytes]]:
    gen = SyntheticGenerator(seed)
    rng = np.random.default_rng(seed)
    out = []
    for platform in platforms or list(business.plans):
        if platform not in business.plans:
            continue
        df = gen.generate(business, platform, days, posts_per_platform, end_date)
        if inject_issues:
            df = inject_quality_issues(df, rng)
        name, content = native_export(df, platform, business.business_name, business.handle)
        out.append((platform, name, content))
    return out


class DemoService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_demo_project(self, business_key: str = "agency_uae", days: int = 90, seed: int = 42) -> Project:
        b = get_business(business_key)
        project = ProjectService(self.db).create(
            ProjectCreate(
                name=f"{b.business_name} - Social Audit (demo)",
                description=f"Synthetic {days}-day demo dataset (seed {seed}).",
                platforms=list(b.plans),
                timezone=b.timezone,
                business_profile=BusinessProfileBase(
                    business_name=b.business_name,
                    industry=b.industry,
                    country=b.country,
                    city_market=b.city_market,
                    products_services=b.products_services,
                    target_audience=b.target_audience,
                    business_objective=b.business_objective,
                    marketing_objectives=b.marketing_objectives,
                    competitors=b.competitors,
                    monthly_budget=b.monthly_budget,
                    budget_currency=b.budget_currency,
                    current_posting_frequency=b.current_posting_frequency,
                    additional_instructions=b.additional_instructions,
                ),
            ),
            is_demo=True,
        )
        files = FileService(self.db)
        for platform, name, content in generate_files(b, days, seed):
            f = files.upload_bytes(project, name, content)
            if f.platform is None:  # detection is expected to succeed; fall back to the known platform
                files.detect_mappings(project.id, f.id, platform)
            files.auto_confirm(project.id, f.id)
        NormalizationService(self.db).normalize(project)
        AnalysisPipeline(self.db).run(project)
        logger.info("demo.created", extra={"project_id": str(project.id), "business": business_key})
        return ProjectService(self.db).get(project.id)
