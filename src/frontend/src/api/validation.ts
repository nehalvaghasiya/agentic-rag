import Ajv2020, { type ValidateFunction } from "ajv/dist/2020";
import schema from "../../../../contracts/openapi.json";
import type { ApiPath, Dto, Endpoint, ExecutionEvent, JsonResponse, MethodFor } from "./contracts";

const root = "urn:agentic-rag:contract";
const ajv = new Ajv2020({
  strict: false, // OpenAPI annotations (e.g. discriminator) accompany JSON Schema keywords.
  validateFormats: false, // Existing serialized datetimes can omit timezone offsets.
  coerceTypes: false,
  useDefaults: false,
  removeAdditional: false,
});
ajv.addSchema({ ...schema, $id: root });

function compile<T>(pointer: string): ValidateFunction<T> {
  const validator = ajv.getSchema<T>(root + pointer);
  if (!validator) throw new Error(`Missing contract schema: ${pointer}`);
  return validator;
}

/** Validate a referenced contract schema without claiming a TypeScript type. */
export function schemaValidator(pointer: string): ValidateFunction<unknown> {
  return compile<unknown>(pointer);
}

export const validateError = compile<Dto<"ErrorEnvelope">>("#/components/schemas/ErrorEnvelope");
export const validateCorrelationId = compile<Dto<"PublicError">["correlation_id"]>(
  "#/components/schemas/PublicError/properties/correlation_id",
);
export const validateEvent = compile<ExecutionEvent>("#/components/schemas/ExecutionEvent");
const responses = new Map<string, ValidateFunction>();

function escapePointer(value: string): string {
  return value.replace(/~/g, "~0").replace(/\//g, "~1");
}

export function responseValidator<P extends ApiPath, M extends MethodFor<P>>(
  endpoint: Endpoint<P, M>,
): ValidateFunction<JsonResponse<P, M>> {
  const pointer = `#/paths/${escapePointer(endpoint.path)}/${endpoint.method}/responses/200/content/application~1json/schema`;
  // Each cache key identifies exactly one generated response type and schema.
  let validator = responses.get(pointer) as ValidateFunction<JsonResponse<P, M>> | undefined;
  if (!validator) {
    validator = compile<JsonResponse<P, M>>(pointer);
    responses.set(pointer, validator);
  }
  return validator;
}
