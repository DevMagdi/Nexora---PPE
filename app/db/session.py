from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "dev",
    future=True,
)

# ✅ SQLite بيتجاهل الـ Foreign Key constraints تمامًا افتراضيًا (لازم تتفعل
# يدويًا لكل اتصال). من غير السطر ده، حذف كاميرا كان بيسيب مخالفات "يتيمة"
# في جدول violations بتأشر على camera_id بقى مش موجود، رغم إننا حطينا
# ondelete="CASCADE" في الموديل — لأن الداتابيز نفسها مش شغالة بالـ constraint.
if engine.sync_engine.dialect.name == "sqlite":

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """
    ⚠️ ملاحظة مهمة: create_all() بتنشئ الجداول الناقصة بس، ومش بتعدّل
    جداول موجودة بالفعل (مثلاً لو ضفت عمود جديد لـ Camera، مش هيتضاف
    لملف .db موجود من قبل). لو هتضيف جداول/أعمدة جديدة (Users، Organizations..)
    على قاعدة بيانات فيها بيانات حقيقية بالفعل، لازم تستخدم Alembic
    للـ migrations بدل الاعتماد على create_all وحدها.
    """
    from app.db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)