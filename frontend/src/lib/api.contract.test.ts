import assert from "node:assert/strict";
// Node's native TypeScript runner needs the extension; the application compiler ignores this test import.
// @ts-ignore TS5097: runtime-only .ts import used by the contract test command.
import { parseExtractionResult } from "./api.ts";

const evidence = [{ quote: "Asha owns the API", source_id: "source-1", message_index: null }];
const complete = {
  summary: "Project discussion",
  items: [],
  people: [{ name: "Asha", text: "Asha owns the API", confidence: 0.9, evidence }],
  tasks: [], deadlines: [], decisions: [], questions: [], technical_issues: [], dependencies: [], contradictions: [],
};

const parsed = parseExtractionResult(complete);
assert.equal(parsed.people.length, 1);
assert.equal(parsed.people[0].evidence[0].quote, "Asha owns the API");
assert.equal(parseExtractionResult({ summary: "Empty", items: [] }).tasks.length, 0);
assert.equal(parseExtractionResult({ ...complete, tasks: undefined }).tasks.length, 0);
assert.throws(() => parseExtractionResult({ ...complete, people: [{ text: "bad", confidence: 0.5 }] }), /malformed structured data/);
assert.throws(() => parseExtractionResult({ ...complete, people: [{ ...complete.people[0], evidence: [null] }] }), /malformed structured data/);

console.log("frontend API contract tests passed");
