"""Write the API's OpenAPI schema to apps/web/openapi.json (no server needed).

`make api-client` runs this, then generates the TypeScript types from it. A test fails when the
committed schema is out of date, so the web client always matches the API.
"""

import json
from pathlib import Path

from apps.api.main import create_app

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "web" / "openapi.json"


def schema_text() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    SCHEMA_PATH.write_text(schema_text(), encoding="utf-8")
    print(f"wrote {SCHEMA_PATH}")
