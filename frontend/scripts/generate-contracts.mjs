import { readFile, writeFile } from "node:fs/promises";
import openapiTS, { astToString } from "openapi-typescript";
import ts from "typescript";

const [input, output] = process.argv.slice(2);
const schema = JSON.parse(await readFile(input, "utf8"));
const declarations = await openapiTS(schema, {
  alphabetize: true,
  defaultNonNullable: false,
  transform(node) {
    if (node.format === "binary" || node.contentMediaType === "application/octet-stream") {
      return ts.factory.createTypeReferenceNode("Blob");
    }
  },
});
await writeFile(output,
  "// Generated from contracts/openapi.json. Do not edit.\n" + astToString(declarations));
