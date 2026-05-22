from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Integer, func, select
from datetime import datetime, timezone
from typing import Optional

engine = None
SessionLocal = None


class Base(DeclarativeBase):
    pass


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(100), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_date: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    query: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(Integer)          # 1 = good, -1 = bad
    source: Mapped[str] = mapped_column(String(20), default="explicit")  # explicit | implicit
    correction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


async def save_feedback(
    session_id: str, query: str, response: str,
    rating: int, source: str = "explicit", correction: Optional[str] = None
) -> None:
    async with SessionLocal() as session:
        session.add(Feedback(
            session_id=session_id, query=query, response=response,
            rating=rating, source=source, correction=correction,
        ))
        await session.commit()


async def get_feedback_stats() -> dict:
    async with SessionLocal() as session:
        total = (await session.execute(select(func.count()).select_from(Feedback))).scalar()
        positive = (await session.execute(
            select(func.count()).select_from(Feedback).where(Feedback.rating == 1)
        )).scalar()
        negative = (await session.execute(
            select(func.count()).select_from(Feedback).where(Feedback.rating == -1)
        )).scalar()
        corrections = (await session.execute(
            select(func.count()).select_from(Feedback).where(
                Feedback.rating == -1, Feedback.correction.isnot(None)
            )
        )).scalar()
        rows = (await session.execute(
            select(Feedback).where(Feedback.rating == -1, Feedback.correction.isnot(None))
            .order_by(Feedback.created_at.desc()).limit(20)
        )).scalars().all()
        pending_evals = [
            {"query": r.query, "correction": r.correction, "source": r.source}
            for r in rows
        ]
    return {
        "total": total, "positive": positive, "negative": negative,
        "corrections_available": corrections, "pending_eval_candidates": pending_evals,
    }


async def save_daily_report(report_date: str, content: str) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(DailyReport).where(DailyReport.report_date == report_date)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.content = content
            existing.generated_at = datetime.now(timezone.utc)
        else:
            session.add(DailyReport(report_date=report_date, content=content))
        await session.commit()


async def get_latest_report() -> DailyReport | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(DailyReport).order_by(DailyReport.report_date.desc()).limit(1)
        )
        return result.scalar_one_or_none()


async def init_db(database_url: str):
    global engine, SessionLocal

    async_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(async_url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
