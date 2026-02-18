import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import create_access_token, hash_password
from app.database import get_db
from app.main import app
from app.models import Base
from app.models.user import User

TEST_DB_URL = "sqlite+aiosqlite:///test.db"

engine = create_async_engine(TEST_DB_URL, echo=False)
test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with test_session() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def db():
    async with test_session() as session:
        yield session


@pytest.fixture
async def test_user(db: AsyncSession):
    user = User(
        id="test-user-id",
        username="testuser",
        hashed_password=hash_password("testpass"),
        native_language="English",
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
def auth_token(test_user):
    return create_access_token(test_user.id)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
