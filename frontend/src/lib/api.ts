export const MAX_SOURCE_LENGTH = 30_000;
export type ExtractionItem = { kind: string; text: string; confidence: number; evidence_quote: string };
export type ExtractionResult = { summary: string; items: ExtractionItem[] };

export class ApiError extends Error {
  constructor(message: string, readonly status?: number, readonly category?: string) { super(message); }
}

function validationMessage(detail: unknown): string {
  if (!Array.isArray(detail)) return "The source could not be validated.";
  return detail.map((item: { loc?: unknown[]; msg?: string }) => {
    const field = Array.isArray(item.loc) ? String(item.loc[item.loc.length - 1]) : "request";
    return `${field}: ${item.msg || "invalid value"}`;
  }).join(" ");
}

export async function extractIntelligence(text: string, sourceType: string): Promise<ExtractionResult> {
  const trimmed = text.trim();
  if (!trimmed) throw new ApiError("Add some source text before extracting.", 422, "invalid_input");
  if (text.length > MAX_SOURCE_LENGTH) throw new ApiError(`Source text must be ${MAX_SOURCE_LENGTH.toLocaleString()} characters or fewer.`, 422, "invalid_input");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/v1/inference/test`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, source_type: sourceType }) });
  } catch { throw new ApiError("Could not reach the Chaos Translator API.", undefined, "api_unavailable"); }
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 422 && typeof payload === "object" && payload !== null && "detail" in payload) throw new ApiError(validationMessage((payload as { detail?: unknown }).detail), 422, "invalid_input");
    if (response.status === 503 && typeof payload === "object" && payload !== null && "detail" in payload) { const detail = (payload as { detail?: { message?: string } }).detail; throw new ApiError(detail?.message || "Inference is temporarily unavailable. Check Ollama and the configured models.", 503, "provider_failure"); }
    throw new ApiError(`Extraction failed (HTTP ${response.status}).`, response.status);
  }
  return payload as ExtractionResult;
}
