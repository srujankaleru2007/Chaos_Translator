"use client";

import { useEffect, useState } from "react";
import { extractIntelligence, generateBriefingAudio, parseDocumentSource, parseWhatsAppSource, MAX_SOURCE_LENGTH, type CanonicalSourcePreview, type ExtractionResult, type IntelligenceClaim } from "@/lib/api";

function Evidence({ claim }: { claim: IntelligenceClaim }) {
  return <details className="mt-3 rounded-lg border border-[#e5ebe5] bg-white p-3 text-sm"><summary className="cursor-pointer font-medium text-[#477157]">Evidence · {claim.evidence.length} reference{claim.evidence.length === 1 ? "" : "s"}</summary><div className="mt-3 space-y-2">{claim.evidence.map((evidence, index) => <blockquote key={`${evidence.source_id}-${index}`} className="border-l-2 border-[#a8c8ac] pl-3 italic leading-6 text-[#748178]">“{evidence.quote}”<span className="mt-1 block not-italic text-xs text-[#91a097]">{evidence.source_id}{evidence.message_index ? ` · message ${evidence.message_index}` : ""}{evidence.line_start ? ` · line ${evidence.line_start}` : ""}{evidence.timestamp ? ` · ${evidence.timestamp}` : ""}</span></blockquote>)}</div></details>;
}

function ClaimCard({ claim, title }: { claim: IntelligenceClaim; title?: string }) {
  const detail = claim as IntelligenceClaim & { claim_a?: string; claim_b?: string; resolution?: string | null; authoritative_claim?: string | null };
  return <article className="rounded-xl border border-[#e5ebe5] bg-[#fbfcfa] p-5"><div className="flex items-center justify-between"><span className="font-mono text-[10px] uppercase tracking-widest text-[#477157]">{title || "claim"}</span><span className="font-mono text-xs text-[#8aa18e]">{Math.round(claim.confidence * 100)}%</span></div><h3 className="mt-3 text-base font-semibold">{claim.text}</h3>{detail.claim_a && <div className="mt-3 space-y-2 rounded-lg bg-[#fff9ed] p-3 text-sm"><p><b>Side A:</b> {detail.claim_a}</p><p><b>Side B:</b> {detail.claim_b}</p><p><b>Resolution:</b> {detail.resolution || "Unresolved"}</p>{detail.authoritative_claim && <p><b>Authoritative claim:</b> {detail.authoritative_claim}</p>}</div>}{claim.uncertain && <p className="mt-2 text-xs text-[#a26a45]">Uncertain — the source does not fully establish this claim.</p>}<Evidence claim={claim} /></article>;
}

export default function Home() {
  const [sourceText, setSourceText] = useState("");
  const [sourceType, setSourceType] = useState("whatsapp");
  const [fileName, setFileName] = useState("");
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [parsedSource, setParsedSource] = useState<CanonicalSourcePreview | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [audioLoading, setAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState(false);

  useEffect(() => () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  async function handleFile(file: File) {
    setFileName(file.name);
    const isWhatsApp = file.name.toLowerCase().endsWith(".txt");
    setSourceType(isWhatsApp ? "whatsapp" : "document");
    setSelectedFile(file);
    setSourceText(isWhatsApp ? await file.text() : "");
    setResult(null); setParsedSource(null);
    setError("");
  }

  async function extract() {
    if (!sourceText.trim() && !selectedFile) { setError("Add a source first by uploading a file or pasting text."); return; }
    if (sourceText.length > MAX_SOURCE_LENGTH) { setError(`Source text must be ${MAX_SOURCE_LENGTH.toLocaleString()} characters or fewer.`); return; }
    setLoading(true); setError(""); setAudioUrl(""); setAudioError(false);
    try {
      if (sourceType === "document" && selectedFile) {
        setParsedSource(await parseDocumentSource(selectedFile));
        return;
      }
      if (sourceType === "whatsapp") setParsedSource(await parseWhatsAppSource(sourceText, fileName || undefined));
      setResult(await extractIntelligence(sourceText, sourceType, true));
    } catch (err) { setError(err instanceof Error ? err.message : "Could not reach the Chaos Translator API."); }
    finally { setLoading(false); }
  }

  async function listenToBriefing() {
    if (!result?.summary) return;
    setAudioLoading(true);
    setAudioError(false);
    setAudioUrl("");
    try {
      const audio = await generateBriefingAudio(result.summary);
      setAudioUrl(URL.createObjectURL(audio));
    } catch {
      setAudioError(true);
    } finally {
      setAudioLoading(false);
    }
  }

  return <main className="neo-shell min-h-screen text-[#111827]">
    <header className="border-b border-[#dfe6df] bg-[#f6f7f3]/90 px-6 py-5 backdrop-blur md:px-12"><div className="mx-auto flex max-w-7xl items-center justify-between"><div className="flex items-center gap-3 font-semibold tracking-tight"><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#28523d] text-lg text-white">✣</span><span>The Chaos Translator</span></div><span className="rounded-full border border-[#cbdacd] px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-[#557061]">Qwen 3.5 · local</span></div></header>
    <section className="mx-auto grid max-w-7xl gap-12 px-6 py-16 md:grid-cols-[0.9fr_1.1fr] md:px-12 md:py-24"><div><p className="font-mono text-xs uppercase tracking-[0.2em] text-[#6b8a74]">Turn scattered information into clarity</p><h1 className="mt-5 max-w-xl text-5xl font-semibold leading-[0.98] tracking-[-0.05em] md:text-7xl">Find what matters inside the mess.</h1><p className="mt-7 max-w-lg text-base leading-7 text-[#68776d]">Upload a conversation or document. The translator preserves source structure and evidence while identifying what matters.</p><div className="mt-10 flex gap-8 text-sm text-[#617268]"><span><b className="block text-xl text-[#28523d]">01</b>Upload a source</span><span><b className="block text-xl text-[#28523d]">02</b>Extract intelligence</span><span><b className="block text-xl text-[#28523d]">03</b>Keep the evidence</span></div></div>
      <div className="rounded-2xl border border-[#dbe5dc] bg-white p-5 shadow-[0_20px_60px_rgba(47,75,56,0.08)] md:p-7"><div className="flex items-center justify-between"><div><p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#72907b]">Source intake</p><h2 className="mt-2 text-2xl font-semibold">Translate the chaos</h2></div><span className="text-2xl text-[#9bb6a0]">↗</span></div><label className="mt-7 block cursor-pointer rounded-xl border border-dashed border-[#b9cdbd] bg-[#f7faf6] p-5 transition hover:border-[#6b9977] hover:bg-[#f2f8f2]"><input type="file" className="sr-only" accept=".txt,.pdf,.docx,.pptx" onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} /><span className="block text-sm font-medium">{fileName || "Drop a WhatsApp export or document"}</span><span className="mt-1 block text-xs text-[#7c8b80]">TXT, PDF, DOCX, and PPTX</span></label><div className="my-5 flex items-center gap-3 text-[10px] font-mono uppercase tracking-widest text-[#98a59b]"><span className="h-px flex-1 bg-[#e5ebe5]" />or paste text<span className="h-px flex-1 bg-[#e5ebe5]" /></div><textarea value={sourceText} onChange={e => { setSourceText(e.target.value); setFileName(""); setSelectedFile(null); setParsedSource(null); }} placeholder="Rahul will prepare the presentation. The deadline is October 8…" className="min-h-36 w-full resize-y rounded-xl border border-[#dce5dc] bg-[#fbfcfa] p-4 text-sm leading-6 outline-none transition placeholder:text-[#a3afa5]" /><div className="mt-4 flex items-center justify-between gap-4"><span className="text-xs text-[#7d8b81]">Documents are parsed locally through the configured backend.</span><button onClick={extract} disabled={loading} className="rounded-lg bg-[#28523d] px-5 py-3 text-sm font-medium text-white transition hover:bg-[#1d402e] disabled:cursor-wait disabled:opacity-60">{loading ? "Parsing source…" : sourceType === "document" ? "Parse document  ↗" : "Extract intelligence  ↗"}</button></div>{error && <div className="mt-5 rounded-lg border border-[#efc9c4] bg-[#fff4f1] p-3 text-sm text-[#a24e45]">{error}</div>}</div>
    </section>
    {result && <section className="mx-auto max-w-7xl px-6 pb-20 md:px-12"><div className="rounded-2xl border border-[#dbe5dc] bg-white p-6 md:p-8"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#72907b]">Structured intelligence</p><h2 className="mt-2 text-3xl font-semibold tracking-tight">Here&apos;s what surfaced.</h2><p className="mt-3 max-w-2xl text-[#68776d]">{result.summary}</p><div className="mt-4 flex flex-wrap items-center gap-3"><button type="button" onClick={listenToBriefing} disabled={audioLoading} className="rounded-lg border border-[#cbdacd] px-3 py-2 text-sm font-medium text-[#28523d] transition hover:bg-[#f2f8f2] disabled:cursor-wait disabled:opacity-60">{audioLoading ? "⏳ Generating briefing..." : audioUrl ? "🔊 Generate again" : audioError ? "⚠️ Audio unavailable · try again" : "🔊 Listen to briefing"}</button>{audioUrl && <audio controls preload="none" src={audioUrl} aria-label="Briefing audio" className="h-10 max-w-full" />}</div></div><span className="rounded-full bg-[#e7f1e8] px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-[#477157]">{Object.values(result).filter(Array.isArray).reduce((total, values) => total + values.length, 0)} structured findings</span></div><div className="mt-8 space-y-8">{([["people", result.people], ["tasks", result.tasks], ["deadlines", result.deadlines], ["decisions", result.decisions], ["questions", result.questions], ["technical issues", result.technical_issues], ["dependencies", result.dependencies], ["contradictions", result.contradictions]] as [string, IntelligenceClaim[]][]).map(([label, claims]) => <section key={label}><div className="flex items-center justify-between"><h3 className="text-xl font-semibold capitalize">{label}</h3>{claims.length === 0 && <span className="text-xs text-[#91a097]">No supported findings</span>}</div>{claims.length > 0 && <div className="mt-3 grid gap-4 md:grid-cols-2">{claims.map((claim, index) => <ClaimCard key={`${label}-${index}`} claim={claim} title={label} />)}</div>}</section>)}{result.items.length > 0 && <section><h3 className="text-xl font-semibold">Legacy highlights</h3><div className="mt-3 grid gap-4 md:grid-cols-2">{result.items.map((item, index) => <article key={`${item.kind}-${index}`} className="rounded-xl border border-[#e5ebe5] bg-[#fbfcfa] p-5"><span className="font-mono text-[10px] uppercase tracking-widest text-[#477157]">{item.kind}</span><h3 className="mt-3 text-base font-semibold">{item.text}</h3><blockquote className="mt-3 border-l-2 border-[#a8c8ac] pl-3 text-sm italic text-[#748178]">“{item.evidence_quote}”</blockquote></article>)}</div></section>}</div></div></section>}
    {parsedSource && <section className="mx-auto max-w-7xl px-6 pb-12 md:px-12"><div className="rounded-2xl border border-[#dbe5dc] bg-white p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#72907b]">Parsed source</p><h2 className="mt-2 text-2xl font-semibold">{parsedSource.original_metadata.participants instanceof Array ? parsedSource.original_metadata.participants.join(", ") || "No named participants" : "WhatsApp chat"}</h2></div><span className="rounded-full bg-[#e7f1e8] px-3 py-1 text-xs text-[#477157]">{parsedSource.units.length} messages · {parsedSource.processing_status}</span></div>{parsedSource.warnings.length > 0 && <p className="mt-3 text-sm text-[#a26a45]">{parsedSource.warnings.length} parsing warning{parsedSource.warnings.length === 1 ? "" : "s"} preserved.</p>}<div className="mt-4 max-h-72 space-y-2 overflow-auto">{parsedSource.units.slice(0, 50).map(unit => <div key={unit.unit_id} className="rounded-lg bg-[#f7faf6] p-3 text-sm"><span className="font-mono text-xs text-[#72907b]">#{unit.locator.message_index ?? unit.position + 1} · {unit.sender_or_speaker || "System"}</span><p className="mt-1 whitespace-pre-wrap text-[#526258]">{unit.text}</p></div>)}</div></div></section>}
  </main>;
}
