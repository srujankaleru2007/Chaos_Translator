"use client";

import React, { useState, useEffect } from 'react';
import { Upload, FileText, AlertCircle, Loader2, Gamepad2, Shield } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { extractIntelligence, MAX_SOURCE_LENGTH, type ExtractionResult } from '@/lib/api';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

interface UploadSectionProps {
    onDataLoaded: (data: ExtractionResult) => void;
    loading: boolean;
    setLoading: (loading: boolean) => void;
    setShowGame: (show: boolean) => void;
    processingComplete: boolean;
    setProcessingComplete: (complete: boolean) => void;
    processingError: boolean;
    setProcessingError: (error: boolean) => void;
}

export function UploadSection({
    onDataLoaded,
    loading,
    setLoading,
    setShowGame,
    processingComplete,
    setProcessingComplete,
    processingError,
    setProcessingError
}: UploadSectionProps) {
    const [error, setError] = useState<string | null>(null);
    const [dragActive, setDragActive] = useState(false);
    const ANIMATED_WORDS = ['DNA', 'Habits', 'Patterns', 'Secrets', 'Stories'] as const;
    const [wordIndex, setWordIndex] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setWordIndex((prev) => (prev + 1) % ANIMATED_WORDS.length);
        }, 2000);
        return () => clearInterval(interval);
    }, [ANIMATED_WORDS.length]);

    const handleFile = async (file: File) => {
        if (!file.name.endsWith('.txt')) {
            setError('Please upload a .txt file exported from WhatsApp.');
            return;
        }

        setError(null);
        setProcessingComplete(false);
        setProcessingError(false);
        setLoading(true);

        try {
            const text = await file.text();
            if (!text.trim()) throw new Error('The selected file is empty.');
            if (text.length > MAX_SOURCE_LENGTH) throw new Error(`Source text must be ${MAX_SOURCE_LENGTH.toLocaleString()} characters or fewer.`);
            const result = await extractIntelligence(text, 'whatsapp');
            setProcessingComplete(true);
            onDataLoaded(result);
            setLoading(false);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'Failed to analyze the chat.';
            setError(message);
            setProcessingError(true);
            setLoading(false);
        }
    };

    const onDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setDragActive(true);
    };

    const onDragLeave = () => {
        setDragActive(false);
    };

    const onDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFile(e.dataTransfer.files[0]);
        }
    };

    const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            handleFile(e.target.files[0]);
        }
    };

    return (
        <div className="w-full max-w-2xl md:[@media(pointer:coarse)]:max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-1000">
            <div className="text-center mb-6 md:mb-10 md:[@media(pointer:coarse)]:mb-16">
                <h1 className="text-2xl md:text-4xl md:[@media(pointer:coarse)]:text-6xl font-bold mb-2 md:mb-4 md:[@media(pointer:coarse)]:mb-6 bg-clip-text text-transparent bg-gradient-to-r from-white via-zinc-200 to-zinc-500 pb-1">
                    Analyze Your Conversations
                </h1>
                <p className="text-zinc-400 text-base sm:text-lg md:text-xl md:[@media(pointer:coarse)]:text-2xl max-w-md md:[@media(pointer:coarse)]:max-w-2xl mx-auto">
                    Upload your exported WhatsApp chat file and get deep insights into your social dynamics.
                </p>
            </div>

            <div
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
                className={cn(
                    "relative group border-2 border-dashed rounded-2xl md:rounded-[2rem] md:[@media(pointer:coarse)]:rounded-[3rem] p-6 md:p-12 md:[@media(pointer:coarse)]:p-20 transition-all duration-300",
                    dragActive
                        ? "border-indigo-500 bg-indigo-500/5 shadow-[0_0_50px_-12px_rgba(99,102,241,0.25)]"
                        : "border-white/10 hover:border-white/20 bg-white/5 hover:bg-white/10",
                    loading && "pointer-events-none opacity-60"
                )}
            >
                <input
                    type="file"
                    id="file-upload"
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-50"
                    onChange={onFileChange}
                    disabled={loading}
                    accept=".txt"
                />

                <div className="flex flex-col items-center justify-center gap-4 md:gap-6 md:[@media(pointer:coarse)]:gap-10">
                    <div className={cn(
                        "w-12 h-12 md:w-16 md:h-16 md:[@media(pointer:coarse)]:w-24 md:[@media(pointer:coarse)]:h-24 rounded-xl md:rounded-2xl md:[@media(pointer:coarse)]:rounded-[2rem] bg-zinc-900 border border-zinc-800 flex items-center justify-center transition-transform group-hover:scale-110 duration-500",
                        dragActive && "scale-110 border-indigo-500/50"
                    )}>
                        {loading ? (
                            <Loader2 className="w-8 h-8 md:[@media(pointer:coarse)]:w-12 md:[@media(pointer:coarse)]:h-12 text-indigo-500 animate-spin" />
                        ) : (
                            <Upload className={cn(
                                "w-8 h-8 md:[@media(pointer:coarse)]:w-12 md:[@media(pointer:coarse)]:h-12 text-zinc-500 transition-colors",
                                dragActive ? "text-indigo-500" : "group-hover:text-zinc-300"
                            )} />
                        )}
                    </div>

                    <div className="text-center">
                        <p className="text-base md:text-xl md:[@media(pointer:coarse)]:text-3xl font-medium text-zinc-200 mb-1 md:[@media(pointer:coarse)]:mb-3">
                            {loading ? 'Processing chat...' : (dragActive ? 'Drop it here' : 'Drop your chat file here')}
                        </p>
                        {!loading && <p className="text-zinc-500 text-sm md:[@media(pointer:coarse)]:text-lg">or click to browse files</p>}
                    </div>

                    <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3">
                        <div className="flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1.5 sm:py-2 rounded-full bg-zinc-950 border border-zinc-800/50 text-[11px] sm:text-xs md:text-sm text-zinc-400">
                            <FileText className="w-3 h-3 sm:w-3.5 sm:h-3.5 md:w-4 md:h-4" />
                            <span className="whitespace-nowrap">.txt files only</span>
                        </div>
                        <div className="flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1.5 sm:py-2 rounded-full bg-zinc-950 border border-zinc-800/50 text-[11px] sm:text-xs md:text-sm text-zinc-400">
                            <Shield className="w-3 h-3 sm:w-3.5 sm:h-3.5 md:w-4 md:h-4" />
                            <span className="whitespace-nowrap">End-to-end local analysis</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Play Game Button - shown during processing */}
            {loading && (
                <div className="mt-6 md:[@media(pointer:coarse)]:mt-10 flex justify-center animate-in fade-in slide-in-from-bottom-2 duration-500">
                    <button
                        onClick={() => setShowGame(true)}
                        className="group flex items-center gap-3 md:[@media(pointer:coarse)]:gap-6 px-6 md:[@media(pointer:coarse)]:px-10 py-3 md:[@media(pointer:coarse)]:py-6 rounded-xl md:[@media(pointer:coarse)]:rounded-2xl bg-zinc-900 border border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800 transition-all cursor-pointer shadow-lg active:scale-95"
                    >
                        <Gamepad2 className="w-5 h-5 md:[@media(pointer:coarse)]:w-8 md:[@media(pointer:coarse)]:h-8 text-zinc-400 group-hover:text-white transition-colors" />
                        <div className="text-left">
                            <p className="text-sm md:[@media(pointer:coarse)]:text-xl font-bold text-white">Play While We Process</p>
                            <p className="text-xs md:[@media(pointer:coarse)]:text-base text-zinc-500">Memory Match Game</p>
                        </div>
                    </button>
                </div>
            )}

            {error && (
                <div className="mt-6 flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm animate-in fade-in zoom-in-95">
                    <AlertCircle className="w-5 h-5 flex-shrink-0" />
                    <p>{error}</p>
                </div>
            )}

            {/* Image Background CTA Banner */}
            {!loading && (
                <div 
                    className="mt-8 md:mt-12 md:[@media(pointer:coarse)]:mt-16 relative w-full rounded-xl md:rounded-2xl overflow-hidden flex items-center justify-center p-4 md:p-5 md:px-6 group shadow-2xl border border-white/10 transition-transform hover:scale-[1.01] bg-cover bg-center"
                    style={{ backgroundImage: 'url("/two.jpg")' }}
                >
                    {/* Subtle Overlay to ensure text readability */}
                    <div className="absolute inset-0 bg-black/20 pointer-events-none" />

                    {/* Content */}
                    <div className="relative z-10 flex flex-wrap sm:flex-row items-center justify-center gap-3 md:gap-5 w-full">
                        <div className="flex items-center gap-1 md:gap-2 px-3 md:px-4 py-1.5 rounded-lg bg-black/40 backdrop-blur-md border border-white/20 shadow-sm shrink-0">
                            <Shield className="w-3.5 h-3.5 md:w-4 md:h-4 text-white" />
                            <span className="text-[10px] md:text-xs font-black tracking-widest text-white uppercase">100% Local</span>
                        </div>
                        <h3 className="text-base sm:text-lg md:text-xl font-black text-white tracking-tight text-center drop-shadow-lg flex flex-row items-center justify-center gap-1">
                            <span>Uncover your chat</span>
                            <span className="relative inline-block text-left min-w-[4rem] sm:min-w-[4.5rem] md:min-w-[5rem]">
                                <AnimatePresence mode="popLayout">
                                    <motion.span
                                        key={ANIMATED_WORDS[wordIndex]}
                                        initial={{ y: 20, opacity: 0 }}
                                        animate={{ y: 0, opacity: 1 }}
                                        exit={{ y: -20, opacity: 0 }}
                                        transition={{ duration: 0.3, ease: "easeOut" }}
                                        className="absolute top-0 left-0 whitespace-nowrap text-cyan-200"
                                    >
                                        {ANIMATED_WORDS[wordIndex]}.
                                    </motion.span>
                                </AnimatePresence>
                                <span className="opacity-0 pointer-events-none whitespace-nowrap">Patterns.</span>
                            </span>
                        </h3>
                    </div>
                </div>
            )}        </div>
    );
}
