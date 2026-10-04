"use client";

import React, { useState, useEffect } from 'react';
import {
    Heart, Star, Zap, MessageSquare, TrendingUp, Sparkles, Award, Coffee,
    X, ArrowLeft, CheckCircle, AlertCircle, Trophy, Clock, PartyPopper, Loader2
} from 'lucide-react';

interface MemoryGameProps {
    isProcessing: boolean;
    processingComplete: boolean;
    processingError: boolean;
    onExit: () => void;
    onViewDashboard: () => void;
}

const CARD_ICONS = [
    { Icon: Heart, color: 'text-rose-400' },
    { Icon: Star, color: 'text-amber-400' },
    { Icon: Zap, color: 'text-indigo-400' },
    { Icon: MessageSquare, color: 'text-teal-400' },
    { Icon: TrendingUp, color: 'text-emerald-400' },
    { Icon: Sparkles, color: 'text-violet-400' },
    { Icon: Award, color: 'text-orange-400' },
    { Icon: Coffee, color: 'text-cyan-400' },
];

interface Card {
    id: number;
    iconIndex: number;
    isFlipped: boolean;
    isMatched: boolean;
}

export function MemoryGame({
    isProcessing,
    processingComplete,
    processingError,
    onExit,
    onViewDashboard
}: MemoryGameProps) {
    const [cards, setCards] = useState<Card[]>([]);
    const [flippedCards, setFlippedCards] = useState<number[]>([]);
    const [moves, setMoves] = useState(0);
    const [matches, setMatches] = useState(0);
    const [gameTime, setGameTime] = useState(0);
    const [isGameActive, setIsGameActive] = useState(true);
    const [showNotification, setShowNotification] = useState(false);
    const [gameCompleted, setGameCompleted] = useState(false);

    // Timer
    useEffect(() => {
        if (!isGameActive) return;
        const timer = setInterval(() => {
            setGameTime(prev => prev + 1);
        }, 1000);
        return () => clearInterval(timer);
    }, [isGameActive]);

    // Show notification when processing completes or errors
    useEffect(() => {
        if (processingComplete || processingError) {
            setShowNotification(true);
            setIsGameActive(false);
        }
    }, [processingComplete, processingError]);

    // Check for game completion
    useEffect(() => {
        if (matches === 8 && !gameCompleted) {
            setGameCompleted(true);
            setIsGameActive(false);
            setTimeout(() => setShowNotification(true), 500);
        }
    }, [matches, gameCompleted]);

    useEffect(() => {
        // Lock background scroll when game is open
        const originalStyle = window.getComputedStyle(document.body).overflow;
        document.body.style.overflow = 'hidden';

        return () => {
            document.body.style.overflow = originalStyle;
        };
    }, []);

    const initializeGame = () => {
        const cardPairs = CARD_ICONS.flatMap((_, index) => [
            { id: index * 2, iconIndex: index, isFlipped: false, isMatched: false },
            { id: index * 2 + 1, iconIndex: index, isFlipped: false, isMatched: false },
        ]);

        const shuffled = cardPairs.sort(() => Math.random() - 0.5);
        setCards(shuffled);
        setFlippedCards([]);
        setMoves(0);
        setMatches(0);
        setGameTime(0);
        setIsGameActive(true);
        setGameCompleted(false);
        setShowNotification(false);
    };

    // Initialize game after the initializer is declared.
    useEffect(() => {
        initializeGame();
    }, []);

    const handleCardClick = (cardId: number) => {
        if (!isGameActive) return;
        if (flippedCards.length === 2) return;
        if (flippedCards.includes(cardId)) return;

        const card = cards.find(c => c.id === cardId);
        if (card?.isMatched) return;

        const newFlippedCards = [...flippedCards, cardId];
        setFlippedCards(newFlippedCards);

        setCards(prev => prev.map(c =>
            c.id === cardId ? { ...c, isFlipped: true } : c
        ));

        if (newFlippedCards.length === 2) {
            setMoves(prev => prev + 1);

            const [firstId, secondId] = newFlippedCards;
            const firstCard = cards.find(c => c.id === firstId);
            const secondCard = cards.find(c => c.id === secondId);

            if (firstCard && secondCard && firstCard.iconIndex === secondCard.iconIndex) {
                setTimeout(() => {
                    setCards(prev => prev.map(c =>
                        c.id === firstId || c.id === secondId
                            ? { ...c, isMatched: true }
                            : c
                    ));
                    setMatches(prev => prev + 1);
                    setFlippedCards([]);
                }, 500);
            } else {
                setTimeout(() => {
                    setCards(prev => prev.map(c =>
                        c.id === firstId || c.id === secondId
                            ? { ...c, isFlipped: false }
                            : c
                    ));
                    setFlippedCards([]);
                }, 1000);
            }
        }
    };

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const handleExit = () => {
        if (processingComplete) {
            onViewDashboard();
        } else {
            onExit();
        }
    };

    const handleContinue = () => {
        setShowNotification(false);
        if (!gameCompleted) {
            setIsGameActive(true);
        }
    };

    return (
        <div className="fixed inset-0 bg-zinc-900/95 backdrop-blur-xl z-50 flex items-center justify-center animate-in fade-in duration-300">
            <div className="w-full max-w-3xl md:[@media(pointer:coarse)]:max-w-5xl h-[100dvh] flex flex-col overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:display-none">
                {/* Compact Header */}
                <div className="flex-shrink-0 px-4 md:[@media(pointer:coarse)]:px-8 py-3 md:[@media(pointer:coarse)]:py-6 flex items-center justify-between gap-4 md:[@media(pointer:coarse)]:gap-8 border-b border-zinc-700/50">
                    <button
                        onClick={handleExit}
                        className="p-2 md:[@media(pointer:coarse)]:p-3.5 rounded-lg bg-zinc-800/50 border border-zinc-700/50 text-zinc-400 hover:text-white hover:border-zinc-600 transition-all cursor-pointer"
                    >
                        <ArrowLeft className="w-4 h-4 md:[@media(pointer:coarse)]:w-6 md:[@media(pointer:coarse)]:h-6" />
                    </button>

                    <div className="flex items-center gap-2 md:[@media(pointer:coarse)]:gap-6">
                        <div className="flex items-center gap-2 md:[@media(pointer:coarse)]:gap-6 px-2.5 md:[@media(pointer:coarse)]:px-6 py-2 md:[@media(pointer:coarse)]:py-4 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
                            <div className="flex items-center gap-1.5 md:[@media(pointer:coarse)]:gap-3">
                                <Clock className="w-3.5 h-3.5 md:[@media(pointer:coarse)]:w-5 md:[@media(pointer:coarse)]:h-5 text-zinc-400" />
                                <span className="text-xs md:[@media(pointer:coarse)]:text-lg font-bold text-white">{formatTime(gameTime)}</span>
                            </div>
                            <div className="w-px h-3 md:[@media(pointer:coarse)]:h-6 bg-zinc-700" />
                            <div className="flex items-center gap-1.5 md:[@media(pointer:coarse)]:gap-3">
                                <Trophy className="w-3.5 h-3.5 md:[@media(pointer:coarse)]:w-5 md:[@media(pointer:coarse)]:h-5 text-amber-400" />
                                <span className="text-xs md:[@media(pointer:coarse)]:text-lg font-bold text-white">{moves}</span>
                            </div>
                            <div className="w-px h-3 md:[@media(pointer:coarse)]:h-6 bg-zinc-700" />
                            <div className="flex items-center gap-1.5 md:[@media(pointer:coarse)]:gap-3">
                                <CheckCircle className="w-3.5 h-3.5 md:[@media(pointer:coarse)]:w-5 md:[@media(pointer:coarse)]:h-5 text-emerald-400" />
                                <span className="text-xs md:[@media(pointer:coarse)]:text-lg font-bold text-white">{matches}/8</span>
                            </div>
                        </div>

                        {/* Processing Indicator (Icon Only, No Background) */}
                        {isProcessing && !processingComplete && !processingError && (
                            <div className="flex items-center justify-center shrink-0 px-1 sm:px-2" title="Processing...">
                                <Loader2 className="w-5 h-5 md:[@media(pointer:coarse)]:w-7 md:[@media(pointer:coarse)]:h-7 text-indigo-400 animate-spin" />
                            </div>
                        )}
                    </div>
                </div>

                {/* Responsive Game Content */}
                <div className="flex-1 flex flex-col items-center justify-center py-2 md:[@media(pointer:coarse)]:py-12 gap-4 md:[@media(pointer:coarse)]:gap-10">
                    <div className="text-center px-4 mt-2">
                        <h2 className="text-xl md:[@media(pointer:coarse)]:text-3xl font-bold text-white mb-1 md:[@media(pointer:coarse)]:mb-3">Memory Match</h2>
                        <p className="text-xs md:[@media(pointer:coarse)]:text-lg text-zinc-400">Find all matching pairs!</p>
                    </div>

                    {/* Responsive Grid */}
                    <div className="grid grid-cols-4 gap-2 md:[@media(pointer:coarse)]:gap-6 px-4 max-w-[min(400px,65vh)] md:[@media(pointer:coarse)]:max-w-[min(650px,75vh)] w-full">
                        {cards.map((card) => {
                            const { Icon, color } = CARD_ICONS[card.iconIndex];
                            const isFlipped = card.isFlipped || card.isMatched;

                            return (
                                <button
                                    key={card.id}
                                    onClick={() => handleCardClick(card.id)}
                                    disabled={!isGameActive || card.isMatched}
                                    className={`
                                        aspect-square rounded-xl border transition-all duration-300 cursor-pointer flex items-center justify-center
                                        ${isFlipped
                                            ? card.isMatched
                                                ? 'bg-emerald-500/10 border-emerald-500/30 scale-95'
                                                : 'bg-zinc-700/50 border-zinc-600'
                                            : 'bg-zinc-800/50 border-zinc-700/50 hover:border-zinc-600 hover:active:scale-95'
                                        }
                                        ${!isGameActive && !card.isMatched ? 'opacity-50' : ''}
                                    `}
                                >
                                    <div className="w-full h-full flex items-center justify-center p-2 md:[@media(pointer:coarse)]:p-4">
                                        {isFlipped ? (
                                            <Icon className={`w-full h-full max-w-[40px] md:[@media(pointer:coarse)]:max-w-[72px] max-h-[40px] md:[@media(pointer:coarse)]:max-h-[72px] ${color}`} />
                                        ) : (
                                            <div className="w-1/2 h-1/2 rounded-full bg-zinc-700/50 border border-zinc-600/50" />
                                        )}
                                    </div>
                                </button>
                            );
                        })}
                    </div>

                    {/* Compact Reset */}
                    <button
                        onClick={initializeGame}
                        className="px-5 md:[@media(pointer:coarse)]:px-12 py-2 md:[@media(pointer:coarse)]:py-5 rounded-lg bg-zinc-800/50 border border-zinc-700/50 text-sm md:[@media(pointer:coarse)]:text-xl font-bold text-zinc-300 hover:text-white hover:border-zinc-600 transition-all cursor-pointer"
                    >
                        New Game
                    </button>
                </div>
            </div>

            {/* Notification Overlay */}
            {
                showNotification && (
                    <div className="absolute inset-0 bg-black/70 flex items-center justify-center animate-in fade-in duration-300 shadow-2xl">
                        <div className={`
                        max-w-[320px] md:[@media(pointer:coarse)]:max-w-md w-full mx-4 rounded-2xl p-6 md:[@media(pointer:coarse)]:p-8 border animate-in zoom-in-95 duration-300
                        ${gameCompleted
                                ? 'bg-[#121214] border-zinc-800'
                                : processingComplete
                                    ? 'bg-[#121214] border-zinc-800'
                                    : 'bg-[#121214] border-red-900/20'
                            }
                    `}>
                            <div className="flex flex-col items-center text-center">
                                {gameCompleted ? (
                                    <>
                                        <h3 className="text-xl md:[@media(pointer:coarse)]:text-2xl font-bold text-white mb-1">You Won!</h3>
                                        <p className="text-sm md:[@media(pointer:coarse)]:text-base text-zinc-400 mb-2">All pairs matched!</p>
                                        <div className="flex items-center gap-4 md:[@media(pointer:coarse)]:gap-6 mb-6 md:[@media(pointer:coarse)]:mb-8 text-zinc-400">
                                            <div className="flex items-center gap-2">
                                                <Clock className="w-4 h-4 md:[@media(pointer:coarse)]:w-5 md:[@media(pointer:coarse)]:h-5" />
                                                <span className="text-sm md:[@media(pointer:coarse)]:text-lg font-bold">{formatTime(gameTime)}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Trophy className="w-4 h-4 md:[@media(pointer:coarse)]:w-5 md:[@media(pointer:coarse)]:h-5" />
                                                <span className="text-sm md:[@media(pointer:coarse)]:text-lg font-bold">{moves} moves</span>
                                            </div>
                                        </div>
                                        <div className="flex flex-col gap-2.5 md:[@media(pointer:coarse)]:gap-4 w-full">
                                            <button
                                                onClick={initializeGame}
                                                className="w-full px-6 py-2.5 md:[@media(pointer:coarse)]:px-8 md:[@media(pointer:coarse)]:py-4 rounded-xl bg-white text-zinc-950 text-sm md:[@media(pointer:coarse)]:text-lg font-bold hover:bg-zinc-200 transition-all cursor-pointer active:scale-[0.98]"
                                            >
                                                Play Again
                                            </button>
                                            <button
                                                onClick={handleExit}
                                                className="w-full px-6 py-2.5 md:[@media(pointer:coarse)]:px-8 md:[@media(pointer:coarse)]:py-4 rounded-xl bg-zinc-800/50 border border-zinc-700 text-sm md:[@media(pointer:coarse)]:text-lg font-bold text-zinc-300 hover:text-white hover:bg-zinc-800 transition-all cursor-pointer active:scale-[0.98]"
                                            >
                                                Exit
                                            </button>
                                        </div>
                                    </>
                                ) : processingComplete ? (
                                    <>
                                        <h3 className="text-xl md:[@media(pointer:coarse)]:text-2xl font-bold text-white mb-1">Chat Processed!</h3>
                                        <p className="text-sm md:[@media(pointer:coarse)]:text-base text-zinc-400 mb-6 md:[@media(pointer:coarse)]:mb-8">Your analysis is ready to view.</p>
                                        <div className="flex flex-col gap-2.5 md:[@media(pointer:coarse)]:gap-4 w-full">
                                            <button
                                                onClick={onViewDashboard}
                                                className="w-full px-6 py-2.5 md:[@media(pointer:coarse)]:px-8 md:[@media(pointer:coarse)]:py-4 rounded-xl bg-white text-zinc-950 text-sm md:[@media(pointer:coarse)]:text-lg font-bold hover:bg-zinc-200 transition-all cursor-pointer shadow-lg active:scale-[0.98]"
                                            >
                                                View Dashboard
                                            </button>
                                            <button
                                                onClick={handleContinue}
                                                className="w-full px-6 py-2.5 md:[@media(pointer:coarse)]:px-8 md:[@media(pointer:coarse)]:py-4 rounded-xl bg-zinc-800/50 border border-zinc-700 text-sm md:[@media(pointer:coarse)]:text-lg font-bold text-zinc-300 hover:text-white hover:bg-zinc-800 transition-all cursor-pointer active:scale-[0.98]"
                                            >
                                                Keep Playing
                                            </button>
                                        </div>
                                    </>
                                ) : (
                                    <>
                                        <h3 className="text-xl md:[@media(pointer:coarse)]:text-2xl font-bold text-white mb-1">Processing Failed</h3>
                                        <p className="text-sm md:[@media(pointer:coarse)]:text-base text-zinc-400 mb-6 md:[@media(pointer:coarse)]:mb-8">Please try again.</p>
                                        <div className="flex flex-col gap-2.5 md:[@media(pointer:coarse)]:gap-4 w-full">
                                            <button
                                                onClick={onExit}
                                                className="w-full px-6 py-2.5 md:[@media(pointer:coarse)]:px-8 md:[@media(pointer:coarse)]:py-4 rounded-xl bg-red-500 text-white text-sm md:[@media(pointer:coarse)]:text-lg font-bold hover:bg-red-600 transition-all cursor-pointer shadow-lg shadow-red-500/20 active:scale-[0.98]"
                                            >
                                                Back to Upload
                                            </button>
                                            <button
                                                onClick={handleContinue}
                                                className="w-full px-6 py-2.5 md:[@media(pointer:coarse)]:px-8 md:[@media(pointer:coarse)]:py-4 rounded-xl bg-zinc-800/50 border border-zinc-700 text-sm md:[@media(pointer:coarse)]:text-lg font-bold text-zinc-300 hover:text-white hover:bg-zinc-800 transition-all cursor-pointer active:scale-[0.98]"
                                            >
                                                Keep Playing
                                            </button>
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                )
            }
        </div >
    );
}
