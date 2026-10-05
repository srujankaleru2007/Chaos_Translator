export const MAX_SOURCE_LENGTH = 200_000;
export type ExtractionItem = { kind: string; text: string; confidence: number; evidence_quote: string };
export type EvidenceRef = { quote: string; source_id: string; message_index?: number | null; line_start?: number | null; line_end?: number | null; timestamp?: string | null; page_number?: number | null };
export type IntelligenceClaim = { text: string; confidence: number; evidence: EvidenceRef[]; uncertain?: boolean };
export type PersonClaim = IntelligenceClaim & { name: string; role?: string | null };
export type TaskClaim = IntelligenceClaim & { owner?: string | null; status?: string | null; due_date?: string | null; priority?: string | null; dependencies?: string[] };
export type DeadlineClaim = IntelligenceClaim & { date_or_time?: string | null; owner?: string | null; deadline_type?: string | null; timezone?: string | null; confirmation_status?: string | null };
export type DecisionClaim = IntelligenceClaim & { decision: string; decided_by?: string | null; decided_at?: string | null };
export type QuestionClaim = IntelligenceClaim & { answered: boolean; answer?: string | null };
export type TechnicalIssueClaim = IntelligenceClaim & { impact?: string | null; status?: string | null; component?: string | null; resolution?: string | null };
export type DependencyClaim = IntelligenceClaim & { depends_on: string; blocked: boolean; dependent_task?: string | null; relationship?: string | null };
export type ContradictionClaim = IntelligenceClaim & { claim_a: string; claim_b: string; resolution?: string | null; resolution_status: string; authoritative_claim?: string | null };
export type ExtractionResult = {
  summary: string; items: ExtractionItem[]; people: PersonClaim[]; tasks: TaskClaim[];
  deadlines: DeadlineClaim[]; decisions: DecisionClaim[]; questions: QuestionClaim[];
  technical_issues: TechnicalIssueClaim[]; dependencies: DependencyClaim[];
  contradictions: ContradictionClaim[]; provider?: string | null; model?: string | null; cloud_fallback_used?: boolean; correlation_id?: string | null; partial?: boolean; chunks_processed?: number; chunks_total?: number; failed_chunks?: number[];
};
export type WhatsAppSourceUnit = {
  unit_id: string; source_id: string; content_type: string; text: string; position: number;
  timestamp?: string | null; sender_or_speaker?: string | null;
  locator: { source_id: string; message_index?: number | null; metadata?: Record<string, unknown> };
};
export type CanonicalWhatsAppSource = {
  source_id: string; source_type: "whatsapp"; original_filename?: string | null;
  processing_status: string; warnings: string[]; errors: string[];
  original_metadata: Record<string, unknown>; units: WhatsAppSourceUnit[];
};
export type CanonicalSourcePreview = CanonicalWhatsAppSource & { source_type: string };

const CATEGORIES = ["people", "tasks", "deadlines", "decisions", "questions", "technical_issues", "dependencies", "contradictions"] as const;
type Category = typeof CATEGORIES[number];

function apiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

function connectionError(url: string): ApiError {
  return new ApiError(`Could not reach the Chaos Translator API at ${url}. Start the FastAPI backend or verify NEXT_PUBLIC_API_URL.`, undefined, "api_unavailable");
}

export class ApiError extends Error {
  readonly status?: number;
  readonly category?: string;

  constructor(message: string, status?: number, category?: string) {
    super(message);
    this.status = status;
    this.category = category;
  }
}

function validationMessage(detail: unknown): string {
  if (!Array.isArray(detail)) return "The source could not be validated.";
  return detail.map((item: { loc?: unknown[]; msg?: string }) => {
    const field = Array.isArray(item.loc) ? String(item.loc[item.loc.length - 1]) : "request";
    return `${field}: ${item.msg || "invalid value"}`;
  }).join(" ");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function malformedResponse(message: string): never {
  throw new ApiError(`The Chaos Translator API returned malformed structured data: ${message}`, 502, "malformed_response");
}

function validateEvidence(value: unknown, category: string, index: number): EvidenceRef[] {
  if (!Array.isArray(value) || value.length === 0) malformedResponse(`${category}[${index}].evidence must be a non-empty array.`);
  return value.map((entry, evidenceIndex) => {
    if (!isRecord(entry) || typeof entry.quote !== "string" || typeof entry.source_id !== "string") {
      malformedResponse(`${category}[${index}].evidence[${evidenceIndex}] is invalid.`);
    }
    return entry as unknown as EvidenceRef;
  });
}

function validateClaims(value: unknown, category: Category): IntelligenceClaim[] {
  if (value === undefined) return [];
  if (!Array.isArray(value)) malformedResponse(`${category} must be an array.`);
  return value.map((entry, index) => {
    if (!isRecord(entry) || typeof entry.text !== "string" || typeof entry.confidence !== "number") {
      malformedResponse(`${category}[${index}] is missing required claim fields.`);
    }
    return { ...entry, evidence: validateEvidence(entry.evidence, category, index) } as IntelligenceClaim;
  });
}

export function parseExtractionResult(payload: unknown): ExtractionResult {
  if (!isRecord(payload) || typeof payload.summary !== "string" || !Array.isArray(payload.items)) {
    malformedResponse("summary and items are required.");
  }
  const items = payload.items.map((item, index) => {
    if (!isRecord(item) || typeof item.kind !== "string" || typeof item.text !== "string" || typeof item.confidence !== "number" || typeof item.evidence_quote !== "string") {
      malformedResponse(`items[${index}] is missing required fields.`);
    }
    return item as unknown as ExtractionItem;
  });
  const categories = Object.fromEntries(CATEGORIES.map(category => [category, validateClaims(payload[category], category)])) as Record<Category, IntelligenceClaim[]>;
  return { summary: payload.summary, items, ...categories } as ExtractionResult;
}

export async function extractIntelligence(text: string, sourceType: string, cloudConsent = false): Promise<ExtractionResult> {
  const trimmed = text.trim();
  if (!trimmed) throw new ApiError("Add some source text before extracting.", 422, "invalid_input");
  if (text.length > MAX_SOURCE_LENGTH) throw new ApiError(`Source text must be ${MAX_SOURCE_LENGTH.toLocaleString()} characters or fewer.`, 422, "invalid_input");
  const apiUrl = apiBaseUrl();
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/v1/inference/test`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, source_type: sourceType, cloud_consent: cloudConsent }) });
  } catch { throw connectionError(apiUrl); }
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 422 && typeof payload === "object" && payload !== null && "detail" in payload) throw new ApiError(validationMessage((payload as { detail?: unknown }).detail), 422, "invalid_input");
    if (response.status === 503 && typeof payload === "object" && payload !== null && "detail" in payload) { const detail = (payload as { detail?: { message?: string; correlation_id?: string; categories?: string[] } }).detail; const suffix = detail?.correlation_id ? ` Reference: ${detail.correlation_id}.` : ""; throw new ApiError(`${detail?.message || "Inference is temporarily unavailable."}${suffix}`, 503, "provider_failure"); }
    throw new ApiError(`Extraction failed (HTTP ${response.status}).`, response.status);
  }
  return parseExtractionResult(payload);
}

export async function parseWhatsAppSource(text: string, filename?: string): Promise<CanonicalWhatsAppSource> {
  const trimmed = text.trim();
  if (!trimmed) throw new ApiError("Add a WhatsApp export before parsing.", 422, "invalid_input");
  if (text.length > 1_000_000) throw new ApiError("WhatsApp exports must be 1,000,000 characters or fewer.", 422, "invalid_input");
  const apiUrl = apiBaseUrl();
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/v1/sources/whatsapp`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, filename }) });
  } catch { throw connectionError(apiUrl); }
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(`WhatsApp parsing failed (HTTP ${response.status}).`, response.status, "whatsapp_parse_failed");
  if (!isRecord(payload) || payload.source_type !== "whatsapp" || !Array.isArray(payload.units) || typeof payload.source_id !== "string") {
    malformedResponse("WhatsApp source response is missing required fields.");
  }
  return payload as unknown as CanonicalWhatsAppSource;
}

export async function parseDocumentSource(file: File): Promise<CanonicalSourcePreview> {
  const apiUrl = apiBaseUrl();
  const form = new FormData();
  form.append("file", file);
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/v1/sources/document`, { method: "POST", body: form });
  } catch { throw connectionError(apiUrl); }
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : `Document parsing failed (HTTP ${response.status}).`;
    throw new ApiError(detail, response.status, "document_parse_failed");
  }
  if (!isRecord(payload) || typeof payload.source_id !== "string" || typeof payload.source_type !== "string" || !Array.isArray(payload.units)) malformedResponse("Document source response is missing required fields.");
  return payload as unknown as CanonicalSourcePreview;
}
