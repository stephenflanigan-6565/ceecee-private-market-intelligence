
#!/usr/bin/env python3
from pathlib import Path
from db import connect, backend, executescript
ROOT=Path(__file__).resolve().parent
def main():
    c=connect()
    schema=(ROOT/("schema_postgres.sql" if backend()=="postgres" else "schema.sql")).read_text()
    executescript(c,schema); c.commit(); c.close()
    print("database bootstrap complete:",backend())
if __name__=="__main__": main()
