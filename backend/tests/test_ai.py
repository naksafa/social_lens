import json
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.ai.base_provider import LLMProvider, LLMResult, SchemaViolation, T, Usage
from app.ai.guardrails import allowed_numbers, extract_numbers, verify_output
from app.ai.schemas import AuditOutput, ContentPlanOutput, StrategyOutput
from app.core.exceptions import AIProviderError


class Item(BaseModel):
    title: str
    evidence: str


class FakeProvider(LLMProvider):
    """Scripted provider: returns (or raises) the queued responses in order."""

    name = "fake"
    model = "fake-1"

    def __init__(self, responses: list) -> None:  # type: ignore[type-arg]
        self.responses = responses
        self.calls: list[list[dict]] = []

    def _generate(self, system: str, prompt: str, max_tokens: int) -> LLMResult:
        return LLMResult("ok")

    def _structured(self, system: str, messages: list[dict], schema: type[T], max_tokens: int) -> tuple[T, Usage]:
        self.calls.append(messages)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return schema.model_validate(r), Usage(10, 5)


class TestStructuredRetry:
    def test_retries_once_with_schema_correction(self) -> None:
        p = FakeProvider([SchemaViolation("missing field 'evidence'"), {"title": "t", "evidence": "e"}])
        res = p.generate_structured("sys", "prompt", Item)
        assert res.attempts == 2 and res.data.title == "t"
        assert "did not match the required JSON schema" in p.calls[1][-1]["content"]
        assert res.usage.input_tokens == 10

    def test_pydantic_validation_error_also_retried(self) -> None:
        p = FakeProvider([{"title": "t"}, {"title": "t", "evidence": "e"}])  # first lacks a field
        assert p.generate_structured("sys", "prompt", Item).attempts == 2

    def test_gives_up_after_second_failure(self) -> None:
        p = FakeProvider([SchemaViolation("bad"), SchemaViolation("still bad")])
        with pytest.raises(AIProviderError):
            p.generate_structured("sys", "prompt", Item)


class TestGuardrails:
    def test_extract_numbers(self) -> None:
        assert extract_numbers("Reach grew 12.5% to 1,234 from 900") == [12.5, 1234.0, 900.0]

    def test_flags_invented_statistics(self) -> None:
        payload = {"reach": 6476.0, "diff": 204.5, "er": 0.0431}
        out = Item(title="x", evidence="Reels reach 6476 (+204.5%), ER 4.3%, but saves rose 87.2%")
        report = verify_output(out, payload)
        assert report["status"] == "needs_review"
        assert report["issues"][0]["unverified_numbers"] == [87.2]

    def test_small_integers_and_roundings_allowed(self) -> None:
        out = Item(title="x", evidence="Post 3 times per week; median reach 6,476 (about 6476.3)")
        assert verify_output(out, {"r": 6476.3})["status"] == "verified"
        assert 204.5 in allowed_numbers({"s": "text with 204.5 inside"})


def _demo(client: TestClient) -> str:
    r = client.post("/demo/generate", json={"business": "saas_uk", "days": 60, "seed": 3})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_rule_based_chain_without_api_key(client: TestClient) -> None:
    pid = _demo(client)
    # Order is enforced: strategy needs an audit.
    assert client.post(f"/projects/{pid}/strategy").status_code == 404

    audit = client.post(f"/projects/{pid}/audit", json={"instructions": "Focus on LinkedIn"}).json()
    assert audit["generated_by"] == "rules" and audit["version"] == 1
    AuditOutput.model_validate({k: v for k, v in audit["content"].items() if not k.startswith("_")})
    assert audit["content"]["executive_summary"]
    assert {pa["platform"] for pa in audit["content"]["platform_audits"]} == {"linkedin", "instagram"}

    strategy = client.post(f"/projects/{pid}/strategy").json()
    s = StrategyOutput.model_validate({k: v for k, v in strategy["content"].items() if not k.startswith("_")})
    for ps in s.platform_strategies:
        assert 98 <= sum(x.share_pct for x in ps.content_mix) <= 100
        promo = next((x.share_pct for x in ps.content_mix if x.pillar == "promotional"), 0)
        assert promo <= 26  # promotional capped

    plan = client.post(f"/projects/{pid}/content-plan", json={"start_date": "2025-10-01"}).json()
    p = ContentPlanOutput.model_validate({k: v for k, v in plan["content"].items() if not k.startswith(("_", "start"))})
    assert p.entries and all(1 <= e.day <= 30 for e in p.entries)
    assert p.entries[0].date >= "2025-10-01"  # type: ignore[operator]
    # Not every platform every day
    days_per_platform = {pl: {e.day for e in p.entries if e.platform == pl} for pl in {e.platform for e in p.entries}}
    assert all(len(d) < 30 for d in days_per_platform.values())

    # Versioned: a second audit keeps the first.
    assert client.post(f"/projects/{pid}/audit").json()["version"] == 2
    assert client.get(f"/projects/{pid}/audit?version=1").json()["version"] == 1


def test_ai_classification_requires_provider(client: TestClient) -> None:
    pid = _demo(client)
    r = client.post(f"/projects/{pid}/classify")
    assert r.status_code == 503 and r.json()["code"] == "ai_not_configured"


def test_llm_audit_path_with_fake_provider(client: TestClient) -> None:
    """Exercise the LLM branch end-to-end (prompt building, verification, persistence, request log)."""
    from sqlalchemy import select

    from app.ai.prompt_builder import build_analytics_summary
    from app.db.session import SessionLocal
    from app.models import AIRequestLog
    from app.services.ai_service import AIService
    from app.services.project_service import ProjectService

    pid = _demo(client)
    with SessionLocal() as db:
        project = ProjectService(db).get(uuid.UUID(pid))
        # Build a valid audit whose evidence quotes a real number and one invented number.
        rules_audit = client.post(f"/projects/{pid}/audit", json={"use_ai": False}).json()["content"]
        rules_audit = {k: v for k, v in rules_audit.items() if not k.startswith("_")}
        rules_audit["executive_summary"] = "Engagement jumped 987.65% last quarter."  # invented statistic
        fake = FakeProvider([rules_audit])
        row = AIService(db, provider=fake).generate_audit(project, "Focus on leads")
        assert row.generated_by.value == "llm" and row.provider == "fake"
        ver = row.content["_verification"]
        assert ver["status"] == "needs_review"
        assert any(987.65 in i["unverified_numbers"] for i in ver["issues"])
        # The LLM saw a compact summary, never raw rows.
        prompt = fake.calls[0][0]["content"]
        assert "<verified_analytics>" in prompt and "Focus on leads" in prompt
        assert len(prompt) < 120_000
        log = db.scalars(select(AIRequestLog).where(AIRequestLog.project_id == project.id)).all()
        assert log and log[-1].success and log[-1].input_tokens == 10

        summary = build_analytics_summary({**_sections(db, project)}, [], {"analysis_version": 1})
        json.dumps(summary)


def _sections(db, project):  # type: ignore[no-untyped-def]
    from app.services.analysis_pipeline import get_run, load_sections

    return load_sections(db, get_run(db, project.id).id)
