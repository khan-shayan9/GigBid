"""The Postgres checkpointer (C6): every graph step is saved, so a crashed run resumes.

    async with postgres_checkpointer(os.environ["DATABASE_URL"]) as saver:
        graph = build_bid_graph(saver)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


@asynccontextmanager
async def postgres_checkpointer(database_url: str) -> AsyncIterator[AsyncPostgresSaver]:
    # psycopg wants a plain postgresql:// URL; .env uses the SQLAlchemy-style +psycopg form.
    async with AsyncPostgresSaver.from_conn_string(
            database_url.replace("+psycopg", "")) as saver:
        await saver.setup()  # creates the checkpoint tables once; safe to repeat
        yield saver
