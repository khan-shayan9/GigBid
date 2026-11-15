// Generates src/lib/api/schema.d.ts from openapi.json. The schema is passed as an object, not a
// path, because openapi-typescript resolves paths as URLs and this repo's folder has a "#".
import fs from "node:fs";
import openapiTS, { astToString } from "openapi-typescript";

const schema = JSON.parse(fs.readFileSync("openapi.json", "utf8"));
const header = "// Generated from apps/web/openapi.json by `make api-client`. Never edit by hand.\n";
fs.writeFileSync("src/lib/api/schema.d.ts", header + astToString(await openapiTS(schema)));
