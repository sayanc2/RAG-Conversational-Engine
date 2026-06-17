"""
Run once to:
  1. Create SQLite DB and seed 500 employee rows
  2. Embed all 500 office locations into ChromaDB employee_locations collection

Usage:  python -m oracle.seed_db
"""
import asyncio
import os
import random
import sys

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

from faker import Faker
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{_BASE_DIR}/data/oracle.db",
)

DEPARTMENTS = [
    "Engineering", "Product", "Marketing", "Sales",
    "Finance", "HR", "Operations", "Legal",
]
LOCATIONS = [
    "New York, NY", "San Francisco, CA", "Austin, TX",
    "Seattle, WA", "Chicago, IL", "Boston, MA",
    "Denver, CO", "Atlanta, GA", "Miami, FL", "Portland, OR",
]

fake = Faker()
random.seed(42)
Faker.seed(42)


def generate_employees(n: int = 500) -> list[dict]:
    employees = []
    for i in range(1, n + 1):
        emp = {
            "employee_id": f"EMP-{i:04d}",
            "name": fake.name(),
            "age": random.randint(22, 65),
            "department": random.choice(DEPARTMENTS),
            "office_location": random.choice(LOCATIONS),
        }
        employees.append(emp)

    # Row 42 hardcoded for demo
    employees[41] = {
        "employee_id": "EMP-0042",
        "name": "Raghav Sharma",
        "age": 34,
        "department": "Engineering",
        "office_location": "Austin, TX",
    }
    return employees


async def seed_database(employees: list[dict]) -> None:
    os.makedirs(os.path.join(_BASE_DIR, "data"), exist_ok=True)

    engine = create_async_engine(DATABASE_URL, echo=False)
    from oracle.db.models import Base, Employee

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionFactory() as session:
        # Clear existing rows
        from sqlalchemy import delete
        await session.execute(delete(Employee))
        await session.commit()

        # Bulk insert
        session.add_all([Employee(**emp) for emp in employees])
        await session.commit()

    print(f"Seeded {len(employees)} employees into {DATABASE_URL}")
    await engine.dispose()


def seed_embeddings(employees: list[dict]) -> None:
    print("Embedding employee locations into ChromaDB...")
    from oracle.tools.chroma_tools import embed_employee_locations
    embed_employee_locations(employees)


async def main() -> None:
    print("Loading .env...")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BASE_DIR, ".env"))

    employees = generate_employees(500)
    print(f"Generated {len(employees)} employee records.")
    print(f"Row 42: {employees[41]}")

    await seed_database(employees)
    seed_embeddings(employees)
    print("\nSeed complete! ORACLE database and ChromaDB are ready.")


if __name__ == "__main__":
    asyncio.run(main())
