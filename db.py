from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime
from datetime import datetime, timezone
from sqlalchemy import select

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
