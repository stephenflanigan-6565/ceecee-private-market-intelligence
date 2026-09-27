
import os, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///ceecee.db")

def backend():
    return "postgres" if DATABASE_URL.startswith(("postgres://","postgresql://")) else "sqlite"

def connect():
    if backend()=="sqlite":
        path=DATABASE_URL.removeprefix("sqlite:///")
        if not Path(path).is_absolute(): path=str(ROOT/path)
        c=sqlite3.connect(path)
        c.row_factory=sqlite3.Row
        return c
    try:
        import psycopg
    except ImportError as e:
        raise RuntimeError("PostgreSQL selected but psycopg is not installed. Install requirements.txt.") from e
    return psycopg.connect(DATABASE_URL)

def sql(q):
    return q.replace("?", "%s") if backend()=="postgres" else q

def execute(c,q,params=()):
    return c.execute(sql(q),params)

def executescript(c,script):
    if backend()=="sqlite":
        return c.executescript(script)
    # Schema is intentionally simple: split statements outside this helper's callers.
    for stmt in [s.strip() for s in script.split(";") if s.strip()]:
        c.execute(stmt)


def insert_id(c, q, params=(), id_column="id"):
    """Portable insert that returns generated primary key."""
    if backend()=="postgres":
        cur=c.execute(sql(q.rstrip().rstrip(";") + f" RETURNING {id_column}"), params)
        row=cur.fetchone()
        return row[0]
    cur=c.execute(q, params)
    return cur.lastrowid


class PortableCursor:
    def __init__(self, cursor, generated_id=None):
        self._cursor=cursor
        self._generated_id=generated_id
    @property
    def lastrowid(self):
        if self._generated_id is not None:
            return self._generated_id
        return getattr(self._cursor,"lastrowid",None)
    def __getattr__(self,name):
        return getattr(self._cursor,name)

def insert_cursor(c,q,params=(),id_column="id"):
    """Execute INSERT and expose a portable lastrowid-compatible property."""
    if backend()=="postgres":
        cur=c.execute(sql(q.rstrip().rstrip(";")+f" RETURNING {id_column}"),params)
        row=cur.fetchone()
        return PortableCursor(cur,row[0] if row else None)
    return PortableCursor(c.execute(q,params))
