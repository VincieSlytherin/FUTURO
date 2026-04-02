from __future__ import annotations

import asyncio
import html
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

from sqlalchemy import desc, func, select

from app.config import settings
from app.database import AsyncSessionLocal
from app.memory.manager import MemoryManager
from app.models.db import Company, CompanyEvent, JobListing
from app.providers.base import TaskType
from app.providers.router import get_provider


def notifications_enabled(email: str | None = None, password: str | None = None) -> bool:
    notify_email = (email if email is not None else settings.notify_email).strip()
    gmail_password = "".join((password if password is not None else settings.gmail_app_password).split())
    return bool(notify_email and gmail_password)


def _salary_label(job: dict[str, Any]) -> str:
    salary_min = job.get("salary_min")
    salary_max = job.get("salary_max")
    currency = job.get("salary_currency") or "USD"
    if salary_min and salary_max:
        return f"{currency} {int(salary_min):,} - {int(salary_max):,}"
    if salary_min:
        return f"{currency} {int(salary_min):,}+"
    return "Not listed"


def _score_badge(score: int | None) -> str:
    if score is None:
        return "Unscored"
    if score >= 85:
        return "Excellent fit"
    if score >= 70:
        return "Strong fit"
    if score >= 60:
        return "Worth a look"
    return "Lower fit"


def _encouragement_line(now: datetime) -> str:
    options = [
        "Momentum compounds. A few thoughtful moves this week can change the whole search.",
        "Consistency wins here. Keep backing your strongest stories with real follow-through.",
        "You do not need perfect odds on every role. You need steady progress on the right ones.",
        "The goal is not to do everything. It is to keep moving the highest-fit opportunities forward.",
    ]
    return options[now.isocalendar().week % len(options)]


ENCOURAGEMENT_SYSTEM = """You write one short encouragement line for a weekly job search digest.

Rules:
- Use the user's actual weekly situation, not generic motivation.
- Mention momentum, focus, recovery, or restraint only if it matches the data.
- Sound warm, grounded, and specific.
- Keep it to one sentence, max 28 words.
- No emojis.
- No exclamation marks.
- Do not mention raw JSON.
Return only the sentence."""


def _section_body(markdown_section: str, header: str) -> str:
    prefix = f"## {header}"
    body = markdown_section.strip()
    if body.startswith(prefix):
        body = body[len(prefix):].strip()
    return body.strip()


def _html_escape_lines(text: str) -> str:
    if not text.strip():
        return "<p style='margin:0;color:#6b7280;'>No weekly focus saved yet.</p>"

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bullet_lines = [
        line[1:].strip() for line in lines
        if line.startswith("-") or line.startswith("*")
    ]
    if bullet_lines and len(bullet_lines) == len(lines):
        items = "".join(
            f"<li style='margin:0 0 8px 0;'>{html.escape(line)}</li>"
            for line in bullet_lines
        )
        return f"<ul style='margin:0;padding-left:18px;color:#111827;'>{items}</ul>"

    paragraphs = "".join(
        f"<p style='margin:0 0 10px 0;color:#111827;'>{html.escape(line)}</p>"
        for line in lines
    )
    return paragraphs


def _parse_checklist_items(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = None
        if line.startswith("- [ ] "):
            match = (False, line[6:].strip())
        elif line.startswith("- [x] ") or line.startswith("- [X] "):
            match = (True, line[6:].strip())
        if match and match[1]:
            items.append({"done": match[0], "text": match[1]})
    return items


def _html_checklist(items: list[dict[str, Any]], empty_text: str) -> str:
    if not items:
        return f"<p style='margin:0;color:#6b7280;'>{html.escape(empty_text)}</p>"

    rows = []
    for item in items:
        icon = "☑" if item["done"] else "☐"
        color = "#6b7280" if item["done"] else "#111827"
        decoration = "line-through" if item["done"] else "none"
        rows.append(
            f"<li style='margin:0 0 8px 0;color:{color};text-decoration:{decoration};'>{icon} {html.escape(item['text'])}</li>"
        )
    return f"<ul style='margin:0;padding-left:18px;'>{''.join(rows)}</ul>"


def _text_checklist(items: list[dict[str, Any]], empty_text: str) -> list[str]:
    if not items:
        return [empty_text]
    return [
        f"- [{'x' if item['done'] else ' '}] {item['text']}"
        for item in items
    ]


class EmailNotificationService:
    def __init__(self, memory: MemoryManager | None = None):
        self.memory = memory or MemoryManager(settings.memory_dir, git_auto_commit=False)

    async def send_scout_run_summary(
        self,
        *,
        config_name: str,
        search_term: str,
        location: str,
        min_score: int,
        jobs_found: int,
        jobs_new: int,
        jobs_scored: int,
        jobs: list[dict[str, Any]],
        recipient_email: str | None = None,
        gmail_password: str | None = None,
        test_mode: bool = False,
    ) -> bool:
        to_email = (recipient_email if recipient_email is not None else settings.notify_email).strip()
        app_password = "".join((gmail_password if gmail_password is not None else settings.gmail_app_password).split())
        if not notifications_enabled(to_email, app_password):
            return False

        subject_prefix = "Test: " if test_mode else ""
        subject = (
            f"{subject_prefix}Futuro Scout finished: {config_name} "
            f"({len(jobs)} jobs at {min_score}+)"
        )
        html_body = self._build_scout_email_html(
            config_name=config_name,
            search_term=search_term,
            location=location,
            min_score=min_score,
            jobs_found=jobs_found,
            jobs_new=jobs_new,
            jobs_scored=jobs_scored,
            jobs=jobs,
            test_mode=test_mode,
        )
        text_body = self._build_scout_email_text(
            config_name=config_name,
            search_term=search_term,
            location=location,
            min_score=min_score,
            jobs_found=jobs_found,
            jobs_new=jobs_new,
            jobs_scored=jobs_scored,
            jobs=jobs,
            test_mode=test_mode,
        )
        await asyncio.to_thread(self._send_email_sync, to_email, app_password, subject, html_body, text_body)
        return True

    async def send_weekly_digest(
        self,
        *,
        recipient_email: str | None = None,
        gmail_password: str | None = None,
        test_mode: bool = False,
    ) -> bool:
        to_email = (recipient_email if recipient_email is not None else settings.notify_email).strip()
        app_password = "".join((gmail_password if gmail_password is not None else settings.gmail_app_password).split())
        if not notifications_enabled(to_email, app_password):
            return False

        digest = await self._build_weekly_digest_payload()
        subject_prefix = "Test: " if test_mode else ""
        subject = f"{subject_prefix}Futuro Weekly Digest"
        html_body = self._build_weekly_digest_html(digest, test_mode=test_mode)
        text_body = self._build_weekly_digest_text(digest, test_mode=test_mode)
        await asyncio.to_thread(self._send_email_sync, to_email, app_password, subject, html_body, text_body)
        return True

    async def build_test_scout_jobs(self) -> list[dict[str, Any]]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(JobListing)
                .order_by(desc(JobListing.discovered_at))
                .limit(3)
            )
            jobs = result.scalars().all()

        if not jobs:
            return [
                {
                    "title": "Applied AI Engineer",
                    "company": "Sample AI Co",
                    "job_url": "https://example.com/jobs/ai-engineer",
                    "location": "Remote",
                    "salary_min": 170000,
                    "salary_max": 210000,
                    "salary_currency": "USD",
                    "score": 86,
                    "score_summary": "Strong fit for production LLM systems, RAG, and cross-functional delivery.",
                    "sponsorship_likely": True,
                    "site": "sample",
                }
            ]

        return [
            {
                "title": job.title,
                "company": job.company,
                "job_url": job.job_url,
                "location": job.location,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "salary_currency": job.salary_currency,
                "score": job.score,
                "score_summary": job.score_summary,
                "sponsorship_likely": job.sponsorship_likely,
                "site": job.site,
            }
            for job in jobs
        ]

    async def _build_weekly_digest_payload(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        async with AsyncSessionLocal() as db:
            top_jobs_result = await db.execute(
                select(JobListing)
                .where(JobListing.discovered_at >= week_ago, JobListing.score >= 70)
                .order_by(desc(JobListing.score), desc(JobListing.discovered_at))
                .limit(5)
            )
            top_jobs = top_jobs_result.scalars().all()

            current_counts_result = await db.execute(
                select(Company.stage, func.count())
                .group_by(Company.stage)
            )
            current_counts = {
                stage: count for stage, count in current_counts_result.all()
            }

            companies_result = await db.execute(
                select(Company.id, Company.created_at)
                .where(Company.created_at <= week_ago)
            )
            previous_companies = companies_result.all()
            previous_counts: dict[str, int] = {}
            if previous_companies:
                company_ids = [company_id for company_id, _ in previous_companies]
                stages_by_company = {company_id: "RESEARCHING" for company_id in company_ids}
                events_result = await db.execute(
                    select(CompanyEvent.company_id, CompanyEvent.stage_to, CompanyEvent.happened_at)
                    .where(
                        CompanyEvent.company_id.in_(company_ids),
                        CompanyEvent.happened_at <= week_ago,
                        CompanyEvent.stage_to.isnot(None),
                    )
                    .order_by(CompanyEvent.company_id, CompanyEvent.happened_at)
                )
                for company_id, stage_to, _ in events_result.all():
                    if stage_to:
                        stages_by_company[company_id] = stage_to

                for stage in stages_by_company.values():
                    previous_counts[stage] = previous_counts.get(stage, 0) + 1

            applied_this_week = (
                await db.execute(
                    select(func.count())
                    .select_from(CompanyEvent)
                    .where(
                        CompanyEvent.stage_to == "APPLIED",
                        CompanyEvent.happened_at >= week_ago,
                    )
                )
            ).scalar_one()

        focus_md = self.memory.read_section("L1_campaign.md", "Weekly focus")
        weekly_focus = _section_body(focus_md, "Weekly focus")
        daily_tasks_md = self.memory.read_section("planner.md", "Daily tasks")
        learning_backlog_md = self.memory.read_section("planner.md", "Learning backlog")
        daily_tasks = _parse_checklist_items(_section_body(daily_tasks_md, "Daily tasks"))
        learning_backlog = _parse_checklist_items(_section_body(learning_backlog_md, "Learning backlog"))

        digest = {
            "generated_at": now,
            "top_jobs": [
                {
                    "title": job.title,
                    "company": job.company,
                    "job_url": job.job_url,
                    "location": job.location,
                    "salary_min": job.salary_min,
                    "salary_max": job.salary_max,
                    "salary_currency": job.salary_currency,
                    "score": job.score,
                    "score_summary": job.score_summary,
                    "sponsorship_likely": job.sponsorship_likely,
                    "site": job.site,
                }
                for job in top_jobs
            ],
            "current_stage_counts": current_counts,
            "previous_stage_counts": previous_counts,
            "applied_this_week": applied_this_week,
            "weekly_focus": weekly_focus,
            "daily_tasks": daily_tasks,
            "learning_backlog": learning_backlog,
            "encouragement": "",
        }
        digest["encouragement"] = await self._generate_encouragement(digest)
        return digest

    async def _generate_encouragement(self, digest: dict[str, Any]) -> str:
        fallback = _encouragement_line(digest["generated_at"])
        prompt = self._encouragement_prompt(digest)
        try:
            provider = get_provider(TaskType.CHAT)
            text = await provider.complete(
                system=ENCOURAGEMENT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=80,
            )
        except Exception:
            return fallback

        cleaned = " ".join((text or "").strip().split())
        if not cleaned:
            return fallback
        cleaned = cleaned.replace("!", ".")
        return cleaned[:220].strip()

    def _encouragement_prompt(self, digest: dict[str, Any]) -> str:
        top_jobs = digest.get("top_jobs", [])
        scored_jobs = ", ".join(
            f"{job.get('company')} {job.get('title')} ({job.get('score')}/100)"
            for job in top_jobs[:3]
        ) or "No 70+ score roles this week."
        open_tasks = sum(1 for item in digest.get("daily_tasks", []) if not item.get("done"))
        done_tasks = sum(1 for item in digest.get("daily_tasks", []) if item.get("done"))
        learning_open = sum(1 for item in digest.get("learning_backlog", []) if not item.get("done"))
        pipeline_bits = []
        current_counts = digest.get("current_stage_counts", {})
        previous_counts = digest.get("previous_stage_counts", {})
        for stage, count in sorted(current_counts.items()):
            delta = count - previous_counts.get(stage, 0)
            pipeline_bits.append(f"{stage}: {count} ({delta:+d} vs last week)")
        pipeline_summary = ", ".join(pipeline_bits) or "No pipeline data yet."
        weekly_focus = digest.get("weekly_focus") or "No weekly focus written."
        return (
            "Write one encouragement line for this weekly digest.\n\n"
            f"Applications sent this week: {digest.get('applied_this_week', 0)}\n"
            f"Top jobs: {scored_jobs}\n"
            f"Pipeline movement: {pipeline_summary}\n"
            f"Open daily tasks: {open_tasks}\n"
            f"Completed daily tasks: {done_tasks}\n"
            f"Open learning items: {learning_open}\n"
            f"Weekly focus: {weekly_focus}\n"
        )

    def _build_scout_email_html(
        self,
        *,
        config_name: str,
        search_term: str,
        location: str,
        min_score: int,
        jobs_found: int,
        jobs_new: int,
        jobs_scored: int,
        jobs: list[dict[str, Any]],
        test_mode: bool,
    ) -> str:
        cards = []
        for job in jobs:
            sponsorship = "H-1B likely" if job.get("sponsorship_likely") else "No sponsorship signal"
            score = job.get("score")
            cards.append(
                f"""
                <div style="border:1px solid #e5e7eb;border-radius:18px;padding:18px;background:#ffffff;margin:0 0 14px 0;">
                  <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;">
                    <div>
                      <div style="font-size:18px;font-weight:700;color:#111827;margin:0 0 4px 0;">{html.escape(job.get("title") or "Untitled role")}</div>
                      <div style="font-size:14px;color:#4b5563;margin:0 0 8px 0;">{html.escape(job.get("company") or "Unknown company")} · {html.escape(job.get("location") or "Unknown location")}</div>
                    </div>
                    <div style="text-align:right;">
                      <div style="display:inline-block;background:#e0f2fe;color:#075985;border-radius:999px;padding:6px 10px;font-size:12px;font-weight:700;">{score if score is not None else "--"}/100</div>
                      <div style="margin-top:6px;font-size:11px;color:#6b7280;">{_score_badge(score)}</div>
                    </div>
                  </div>
                  <div style="display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px 0;">
                    <span style="background:#f3f4f6;border-radius:999px;padding:5px 9px;font-size:12px;color:#374151;">Salary: {_salary_label(job)}</span>
                    <span style="background:#f3f4f6;border-radius:999px;padding:5px 9px;font-size:12px;color:#374151;">{html.escape(sponsorship)}</span>
                    <span style="background:#f3f4f6;border-radius:999px;padding:5px 9px;font-size:12px;color:#374151;">Source: {html.escape(job.get("site") or "unknown")}</span>
                  </div>
                  <div style="font-size:14px;line-height:1.6;color:#111827;margin:0 0 12px 0;"><strong>Why it scored well:</strong> {html.escape(job.get("score_summary") or "No summary provided.")}</div>
                  <a href="{html.escape(job.get('job_url') or '#')}" style="display:inline-block;background:#111827;color:#ffffff;text-decoration:none;padding:10px 14px;border-radius:12px;font-size:13px;font-weight:600;">Open job</a>
                </div>
                """
            )

        cards_html = "".join(cards) if cards else """
          <div style="border:1px dashed #d1d5db;border-radius:18px;padding:20px;background:#ffffff;color:#6b7280;">
            No new jobs cleared the threshold on this run. The scout still finished cleanly, so you can leave this config active.
          </div>
        """

        banner = "This is a test email from Futuro." if test_mode else "Your scout just finished running."
        return f"""
        <html>
          <body style="margin:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#111827;">
            <div style="max-width:760px;margin:0 auto;padding:32px 20px;">
              <div style="background:linear-gradient(135deg,#dbeafe,#bfdbfe);border-radius:24px;padding:28px;">
                <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#1d4ed8;font-weight:800;margin:0 0 10px 0;">Futuro Scout</div>
                <h1 style="margin:0 0 10px 0;font-size:28px;line-height:1.15;color:#0f172a;">{html.escape(config_name)} finished</h1>
                <p style="margin:0;font-size:15px;line-height:1.6;color:#1e293b;">{html.escape(banner)} Search: {html.escape(search_term)} in {html.escape(location)}. Threshold: {min_score}+.</p>
              </div>

              <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:20px 0;">
                <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;padding:16px;"><div style="font-size:12px;color:#6b7280;">Jobs found</div><div style="font-size:28px;font-weight:700;">{jobs_found}</div></div>
                <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;padding:16px;"><div style="font-size:12px;color:#6b7280;">New jobs</div><div style="font-size:28px;font-weight:700;">{jobs_new}</div></div>
                <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;padding:16px;"><div style="font-size:12px;color:#6b7280;">Scored</div><div style="font-size:28px;font-weight:700;">{jobs_scored}</div></div>
              </div>

              <div style="margin:22px 0 12px 0;font-size:18px;font-weight:700;color:#111827;">High-score new roles</div>
              {cards_html}
            </div>
          </body>
        </html>
        """

    def _build_scout_email_text(
        self,
        *,
        config_name: str,
        search_term: str,
        location: str,
        min_score: int,
        jobs_found: int,
        jobs_new: int,
        jobs_scored: int,
        jobs: list[dict[str, Any]],
        test_mode: bool,
    ) -> str:
        lines = [
            f"{'TEST - ' if test_mode else ''}Futuro Scout finished: {config_name}",
            f"Search: {search_term} in {location}",
            f"Threshold: {min_score}+",
            f"Jobs found: {jobs_found}",
            f"New jobs: {jobs_new}",
            f"Scored: {jobs_scored}",
            "",
        ]
        if not jobs:
            lines.append("No new jobs cleared the threshold on this run.")
        else:
            for job in jobs:
                lines.extend([
                    f"- {job.get('title')} @ {job.get('company')} ({job.get('score')}/100)",
                    f"  Salary: {_salary_label(job)}",
                    f"  Sponsorship: {'H-1B likely' if job.get('sponsorship_likely') else 'No sponsorship signal'}",
                    f"  Why: {job.get('score_summary') or 'No summary provided.'}",
                    f"  Link: {job.get('job_url')}",
                    "",
                ])
        return "\n".join(lines)

    def _build_weekly_digest_html(self, digest: dict[str, Any], *, test_mode: bool) -> str:
        stage_cards = []
        for stage, count in sorted(digest["current_stage_counts"].items()):
            previous = digest["previous_stage_counts"].get(stage, 0)
            delta = count - previous
            delta_prefix = "+" if delta > 0 else ""
            stage_cards.append(
                f"""
                <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;padding:16px;">
                  <div style="font-size:12px;color:#6b7280;">{html.escape(stage.title())}</div>
                  <div style="font-size:28px;font-weight:700;color:#111827;">{count}</div>
                  <div style="font-size:12px;color:{'#059669' if delta >= 0 else '#dc2626'};">{delta_prefix}{delta} vs last week</div>
                </div>
                """
            )

        top_job_cards = []
        for job in digest["top_jobs"]:
            top_job_cards.append(
                f"""
                <div style="border:1px solid #e5e7eb;border-radius:18px;padding:18px;background:#ffffff;margin:0 0 14px 0;">
                  <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;">
                    <div>
                      <div style="font-size:18px;font-weight:700;color:#111827;margin:0 0 4px 0;">{html.escape(job.get("title") or "Untitled role")}</div>
                      <div style="font-size:14px;color:#4b5563;margin:0 0 8px 0;">{html.escape(job.get("company") or "Unknown company")} · {html.escape(job.get("location") or "Unknown location")}</div>
                    </div>
                    <div style="display:inline-block;background:#e0f2fe;color:#075985;border-radius:999px;padding:6px 10px;font-size:12px;font-weight:700;">{job.get("score") if job.get("score") is not None else "--"}/100</div>
                  </div>
                  <div style="font-size:14px;line-height:1.6;color:#111827;margin:0 0 12px 0;">{html.escape(job.get("score_summary") or "No summary provided.")}</div>
                  <a href="{html.escape(job.get('job_url') or '#')}" style="display:inline-block;background:#111827;color:#ffffff;text-decoration:none;padding:10px 14px;border-radius:12px;font-size:13px;font-weight:600;">Open job</a>
                </div>
                """
            )

        if not top_job_cards:
            top_job_cards.append(
                """
                <div style="border:1px dashed #d1d5db;border-radius:18px;padding:20px;background:#ffffff;color:#6b7280;">
                  No 70+ score jobs were discovered this week. That is still useful signal for tightening search terms and channels.
                </div>
                """
            )

        return f"""
        <html>
          <body style="margin:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#111827;">
            <div style="max-width:760px;margin:0 auto;padding:32px 20px;">
              <div style="background:linear-gradient(135deg,#dbeafe,#bfdbfe);border-radius:24px;padding:28px;">
                <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#1d4ed8;font-weight:800;margin:0 0 10px 0;">Futuro Weekly Digest</div>
                <h1 style="margin:0 0 10px 0;font-size:28px;line-height:1.15;color:#0f172a;">Your weekly job-search snapshot</h1>
                <p style="margin:0;font-size:15px;line-height:1.6;color:#1e293b;">{html.escape('This is a test weekly digest.' if test_mode else 'Here is the latest picture of your pipeline, search momentum, and next focus.')}</p>
              </div>

              <div style="margin:22px 0 12px 0;font-size:18px;font-weight:700;color:#111827;">Top new high-score jobs</div>
              {''.join(top_job_cards)}

              <div style="margin:22px 0 12px 0;font-size:18px;font-weight:700;color:#111827;">Pipeline movement</div>
              <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 18px 0;">
                {''.join(stage_cards) or "<div style='color:#6b7280;'>No pipeline data yet.</div>"}
              </div>

              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;padding:18px;">
                  <div style="font-size:12px;color:#6b7280;margin:0 0 8px 0;">Applications sent this week</div>
                  <div style="font-size:34px;font-weight:700;color:#111827;">{digest['applied_this_week']}</div>
                </div>
                <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;padding:18px;">
                  <div style="font-size:12px;color:#6b7280;margin:0 0 8px 0;">Encouragement</div>
                  <div style="font-size:15px;line-height:1.6;color:#111827;">{html.escape(digest['encouragement'])}</div>
                </div>
              </div>

              <div style="margin:22px 0 12px 0;font-size:18px;font-weight:700;color:#111827;">Next week's focus</div>
              <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;padding:18px;">
                {_html_escape_lines(digest['weekly_focus'])}
              </div>

              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:18px;">
                <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;padding:18px;">
                  <div style="font-size:12px;color:#6b7280;margin:0 0 10px 0;">Daily tasks</div>
                  {_html_checklist(digest['daily_tasks'], 'No daily tasks saved yet.')}
                </div>
                <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;padding:18px;">
                  <div style="font-size:12px;color:#6b7280;margin:0 0 10px 0;">Learning backlog</div>
                  {_html_checklist(digest['learning_backlog'], 'No learning backlog saved yet.')}
                </div>
              </div>
            </div>
          </body>
        </html>
        """

    def _build_weekly_digest_text(self, digest: dict[str, Any], *, test_mode: bool) -> str:
        lines = [
            f"{'TEST - ' if test_mode else ''}Futuro Weekly Digest",
            "",
            "Top new high-score jobs:",
        ]
        if digest["top_jobs"]:
            for job in digest["top_jobs"]:
                lines.extend([
                    f"- {job['title']} @ {job['company']} ({job['score']}/100)",
                    f"  Why: {job.get('score_summary') or 'No summary provided.'}",
                    f"  Link: {job['job_url']}",
                ])
        else:
            lines.append("- No 70+ score jobs this week.")

        lines.extend(["", "Pipeline movement:"])
        for stage, count in sorted(digest["current_stage_counts"].items()):
            previous = digest["previous_stage_counts"].get(stage, 0)
            delta = count - previous
            lines.append(f"- {stage}: {count} ({delta:+d} vs last week)")

        lines.extend([
            "",
            f"Applications sent this week: {digest['applied_this_week']}",
            "",
            "Next week's focus:",
            digest["weekly_focus"] or "No weekly focus saved yet.",
            "",
            "Daily tasks:",
            *_text_checklist(digest["daily_tasks"], "No daily tasks saved yet."),
            "",
            "Learning backlog:",
            *_text_checklist(digest["learning_backlog"], "No learning backlog saved yet."),
            "",
            digest["encouragement"],
        ])
        return "\n".join(lines)

    def _send_email_sync(
        self,
        to_email: str,
        app_password: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = to_email
        msg["To"] = to_email
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(to_email, app_password)
            server.send_message(msg)
