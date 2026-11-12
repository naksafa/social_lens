import io
import zipfile
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.enums import Platform
from app.db.session import get_db
from app.schemas.project import ProjectRead
from app.services.demo_service import DemoService, generate_files, get_business
from app.synthetic.profiles import DEMO_BUSINESSES

router = APIRouter(prefix="/demo", tags=["demo"])

Days = Literal[30, 60, 90, 180]


class DemoBusinessRead(BaseModel):
    key: str
    business_name: str
    industry: str
    country: str
    city_market: str
    marketing_objectives: list[str]
    platforms: list[Platform]
    posts_per_90_days: dict[str, int]


class DemoGenerateRequest(BaseModel):
    business: str = Field(default="agency_uae", description="Demo business key (see GET /demo/businesses)")
    days: Days = 90
    seed: int = Field(default=42, ge=0, le=1_000_000)


class DatasetRequest(BaseModel):
    business: str = "agency_uae"
    days: Days = 90
    seed: int = Field(default=42, ge=0, le=1_000_000)
    platforms: list[Platform] | None = None
    posts_per_platform: int | None = Field(default=None, ge=5, le=2000)
    inject_issues: bool = True


@router.get("/businesses", response_model=list[DemoBusinessRead])
def list_demo_businesses() -> list[DemoBusinessRead]:
    return [
        DemoBusinessRead(
            key=b.key,
            business_name=b.business_name,
            industry=b.industry,
            country=b.country,
            city_market=b.city_market,
            marketing_objectives=[o.value for o in b.marketing_objectives],
            platforms=list(b.plans),
            posts_per_90_days={p.value: plan.posts for p, plan in b.plans.items()},
        )
        for b in DEMO_BUSINESSES.values()
    ]


@router.post("/generate", response_model=ProjectRead, status_code=201)
def generate_demo(body: DemoGenerateRequest | None = None, db: Session = Depends(get_db)) -> ProjectRead:
    """Create a fully analyzed demo project from synthetic native-format exports."""
    body = body or DemoGenerateRequest()
    return ProjectRead.model_validate(DemoService(db).create_demo_project(body.business, body.days, body.seed))


@router.post("/dataset", response_class=Response)
def download_dataset(body: DatasetRequest) -> Response:
    """Download synthetic exports (ZIP of CSV/XLSX) to try the manual upload flow."""
    files = generate_files(
        get_business(body.business), body.days, body.seed, body.platforms, body.posts_per_platform,
        inject_issues=body.inject_issues,
    )  # fmt: skip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for _, name, content in files:
            zf.writestr(name, content)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="sociallens_demo_{body.business}_{body.days}d.zip"'},
    )
