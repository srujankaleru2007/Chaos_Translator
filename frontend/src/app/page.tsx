"use client";

import { useState } from "react";
import { extractIntelligence, MAX_SOURCE_LENGTH, type ExtractionResult } from "@/lib/api";

export default function Home() {
  const [sourceText, setSourceText] = useState("");
  const [sourceType, setSourceType] = useState("whatsapp");
  const [fileName, setFileName] = useState("");
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleFile(file: File) {
    setFileName(file.name);
    setSourceType(file.name.toLowerCase().endsWith(".txt") ? "whatsapp" : "document");
    setSourceText(await file.text());
    setResult(null);
    setError("");
  }

  async function extract() {
    if (!sourceText.trim()) { setError("Add a source first by uploading a file or pasting text."); return; }
    if (sourceText.length > MAX_SOURCE_LENGTH) { setError(`Source text must be ${MAX_SOURCE_LENGTH.toLocaleString()} characters or fewer.`); return; }
    setLoading(true); setError(""); setResult(null);
    try {
      setResult(await extractIntelligence(sourceText, sourceType));
    } catch (err) { setError(err instanceof Error ? err.message : "Could not reach the Chaos Translator API."); }
    finally { setLoading(false); }
  }

  return <main className="min-h-screen bg-[#f6f7f3] text-[#1d2924]">
    <header className="border-b border-[#dfe6df] bg-[#f6f7f3]/90 px-6 py-5 backdrop-blur md:px-12"><div className="mx-auto flex max-w-7xl items-center justify-between"><div className="flex items-center gap-3 font-semibold tracking-tight"><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#28523d] text-lg text-white">✣</span><span>The Chaos Translator</span></div><span className="rounded-full border border-[#cbdacd] px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-[#557061]">Gemma · local</span></div></header>
    <section className="mx-auto grid max-w-7xl gap-12 px-6 py-16 md:grid-cols-[0.9fr_1.1fr] md:px-12 md:py-24"><div><p className="font-mono text-xs uppercase tracking-[0.2em] text-[#6b8a74]">Turn scattered information into clarity</p><h1 className="mt-5 max-w-xl text-5xl font-semibold leading-[0.98] tracking-[-0.05em] md:text-7xl">Find what matters inside the mess.</h1><p className="mt-7 max-w-lg text-base leading-7 text-[#68776d]">Upload a conversation or paste a source. Gemma identifies tasks, deadlines, decisions, people, and questions—while preserving the evidence behind each one.</p><div className="mt-10 flex gap-8 text-sm text-[#617268]"><span><b className="block text-xl text-[#28523d]">01</b>Upload a source</span><span><b className="block text-xl text-[#28523d]">02</b>Extract intelligence</span><span><b className="block text-xl text-[#28523d]">03</b>Keep the evidence</span></div></div>
      <div className="rounded-2xl border border-[#dbe5dc] bg-white p-5 shadow-[0_20px_60px_rgba(47,75,56,0.08)] md:p-7"><div className="flex items-center justify-between"><div><p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#72907b]">Source intake</p><h2 className="mt-2 text-2xl font-semibold">Translate the chaos</h2></div><span className="text-2xl text-[#9bb6a0]">↗</span></div><label className="mt-7 block cursor-pointer rounded-xl border border-dashed border-[#b9cdbd] bg-[#f7faf6] p-5 transition hover:border-[#6b9977] hover:bg-[#f2f8f2]"><input type="file" className="sr-only" accept=".txt,.md,.csv" onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} /><span className="block text-sm font-medium">{fileName || "Drop a WhatsApp export or text file"}</span><span className="mt-1 block text-xs text-[#7c8b80]">TXT, MD, and CSV for this foundation step</span></label><div className="my-5 flex items-center gap-3 text-[10px] font-mono uppercase tracking-widest text-[#98a59b]"><span className="h-px flex-1 bg-[#e5ebe5]" />or paste text<span className="h-px flex-1 bg-[#e5ebe5]" /></div><textarea value={sourceText} onChange={e => { setSourceText(e.target.value); setFileName(""); }} placeholder="Rahul will prepare the presentation. The deadline is October 8…" className="min-h-36 w-full resize-y rounded-xl border border-[#dce5dc] bg-[#fbfcfa] p-4 text-sm leading-6 outline-none transition placeholder:text-[#a3afa5] focus:border-[#76a181]" /><div className="mt-4 flex items-center justify-between gap-4"><span className="text-xs text-[#7d8b81]">Content stays in your configured local pipeline.</span><button onClick={extract} disabled={loading} className="rounded-lg bg-[#28523d] px-5 py-3 text-sm font-medium text-white transition hover:bg-[#1d402e] disabled:cursor-wait disabled:opacity-60">{loading ? "Gemma is reading…" : "Extract intelligence  ↗"}</button></div>{error && <div className="mt-5 rounded-lg border border-[#efc9c4] bg-[#fff4f1] p-3 text-sm text-[#a24e45]">{error}</div>}</div>
    </section>
    {result && <section className="mx-auto max-w-7xl px-6 pb-20 md:px-12"><div className="rounded-2xl border border-[#dbe5dc] bg-white p-6 md:p-8"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#72907b]">Structured intelligence</p><h2 className="mt-2 text-3xl font-semibold tracking-tight">Here&apos;s what surfaced.</h2><p className="mt-3 max-w-2xl text-[#68776d]">{result.summary}</p></div><span className="rounded-full bg-[#e7f1e8] px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-[#477157]">{result.items.length} evidence-backed items</span></div><div className="mt-8 grid gap-4 md:grid-cols-2">{result.items.map((item, index) => <article key={`${item.kind}-${index}`} className="rounded-xl border border-[#e5ebe5] bg-[#fbfcfa] p-5"><div className="flex items-center justify-between"><span className="rounded-full bg-[#e7f1e8] px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest text-[#477157]">{item.kind}</span><span className="font-mono text-xs text-[#8aa18e]">{Math.round(item.confidence * 100)}%</span></div><h3 className="mt-4 text-base font-semibold">{item.text}</h3><blockquote className="mt-4 border-l-2 border-[#a8c8ac] pl-3 text-sm italic leading-6 text-[#748178]">“{item.evidence_quote}”</blockquote></article>)}</div></div></section>}
  </main>;
}
