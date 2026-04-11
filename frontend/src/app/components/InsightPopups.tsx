import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Loader2, Pause, Trophy, Volume2, X } from 'lucide-react';

import { synthesizeInsightSpeech } from '../api/client';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';

export interface InsightPopupItem {
  planId: string;
  type: 'warning' | 'success';
  title: string;
  description: string;
  timestamp: Date | null;
  status: 'loading' | 'ready' | 'error';
}

interface InsightPopupsProps {
  insights: InsightPopupItem[];
  onRemoveInsight: (planId: string) => void;
}

const POPUP_PREVIEW_MAX_LENGTH = 170;

function buildPreview(text: string): string {
  const cleaned = text.trim();
  if (cleaned.length <= POPUP_PREVIEW_MAX_LENGTH) {
    return cleaned;
  }

  return `${cleaned.slice(0, POPUP_PREVIEW_MAX_LENGTH - 3).trimEnd()}...`;
}

function buildInsightSpeechText(insight: InsightPopupItem): string {
  const title = insight.title.trim();
  const description = insight.description.trim();

  if (!title) {
    return description;
  }
  if (!description) {
    return title;
  }
  return `${title}. ${description}`;
}

function buildInsightAudioKey(insight: InsightPopupItem): string {
  return `${insight.planId}:${buildInsightSpeechText(insight)}`;
}

export function InsightPopups({ insights, onRemoveInsight }: InsightPopupsProps) {
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [loadingAudioKey, setLoadingAudioKey] = useState<string | null>(null);
  const [playingAudioKey, setPlayingAudioKey] = useState<string | null>(null);
  const [audioError, setAudioError] = useState<{ key: string; message: string } | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlCacheRef = useRef<Map<string, string>>(new Map());

  const selectedInsight = useMemo(
    () => insights.find((insight) => insight.planId === selectedPlanId) ?? null,
    [insights, selectedPlanId],
  );

  const stopPlayback = () => {
    const audio = audioElementRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
      audio.onended = null;
      audio.onerror = null;
    }
    audioElementRef.current = null;
    setPlayingAudioKey(null);
  };

  useEffect(() => {
    return () => {
      stopPlayback();
      audioUrlCacheRef.current.forEach((url) => URL.revokeObjectURL(url));
      audioUrlCacheRef.current.clear();
    };
  }, []);

  useEffect(() => {
    const validKeys = new Set(insights.filter((insight) => insight.status === 'ready').map(buildInsightAudioKey));

    if (playingAudioKey && !validKeys.has(playingAudioKey)) {
      stopPlayback();
    }

    audioUrlCacheRef.current.forEach((url, key) => {
      if (!validKeys.has(key)) {
        URL.revokeObjectURL(url);
        audioUrlCacheRef.current.delete(key);
      }
    });

    if (audioError && !validKeys.has(audioError.key)) {
      setAudioError(null);
    }
  }, [audioError, insights, playingAudioKey]);

  const toggleInsightAudio = async (insight: InsightPopupItem) => {
    if (insight.status !== 'ready') {
      return;
    }

    const audioKey = buildInsightAudioKey(insight);

    if (loadingAudioKey === audioKey) {
      return;
    }

    if (playingAudioKey === audioKey) {
      stopPlayback();
      return;
    }

    stopPlayback();
    setAudioError(null);

    let audioUrl = audioUrlCacheRef.current.get(audioKey);

    if (!audioUrl) {
      setLoadingAudioKey(audioKey);
      try {
        const blob = await synthesizeInsightSpeech(buildInsightSpeechText(insight));
        audioUrl = URL.createObjectURL(blob);
        audioUrlCacheRef.current.set(audioKey, audioUrl);
      } catch (error) {
        setAudioError({
          key: audioKey,
          message: error instanceof Error ? error.message : 'Impossibile riprodurre l\'insight in audio.',
        });
        return;
      } finally {
        setLoadingAudioKey((current) => (current === audioKey ? null : current));
      }
    }

    const audio = new Audio(audioUrl);
    audioElementRef.current = audio;
    audio.onended = () => {
      if (audioElementRef.current === audio) {
        audioElementRef.current = null;
      }
      setPlayingAudioKey((current) => (current === audioKey ? null : current));
    };
    audio.onerror = () => {
      if (audioElementRef.current === audio) {
        audioElementRef.current = null;
      }
      setPlayingAudioKey((current) => (current === audioKey ? null : current));
      setAudioError({
        key: audioKey,
        message: 'Audio non disponibile in questo momento.',
      });
    };

    try {
      setPlayingAudioKey(audioKey);
      await audio.play();
    } catch (error) {
      if (audioElementRef.current === audio) {
        audioElementRef.current = null;
      }
      setPlayingAudioKey(null);
      setAudioError({
        key: audioKey,
        message: error instanceof Error ? error.message : 'Impossibile avviare la riproduzione audio.',
      });
    }
  };

  if (insights.length === 0) {
    return null;
  }

  return (
    <>
      <div className="pointer-events-none fixed right-3 top-24 z-40 flex max-h-[calc(100vh-7rem)] w-[min(22rem,calc(100vw-1.5rem))] flex-col gap-3 overflow-y-auto rounded-[1.6rem] bg-gray-50 p-1 pb-6 md:right-4 md:top-28 dark:bg-slate-950">
        {insights.map((insight) => {
          const isWarning = insight.type === 'warning';
          const borderClasses = isWarning
            ? 'border-amber-300/80 text-amber-950 dark:border-amber-500/30 dark:text-amber-50'
            : 'border-emerald-300/80 text-emerald-950 dark:border-emerald-500/30 dark:text-emerald-50';
          const iconWrapClasses = isWarning
            ? 'bg-amber-950/10 text-amber-700 dark:bg-amber-200/10 dark:text-amber-200'
            : 'bg-emerald-950/10 text-emerald-700 dark:bg-emerald-200/10 dark:text-emerald-200';
          const preview = buildPreview(insight.description);
          const audioKey = buildInsightAudioKey(insight);
          const isAudioLoading = loadingAudioKey === audioKey;
          const isAudioPlaying = playingAudioKey === audioKey;
          const audioErrorMessage = audioError?.key === audioKey ? audioError.message : null;

          return (
            <div
              key={insight.planId}
              role={insight.status === 'loading' ? undefined : 'button'}
              tabIndex={insight.status === 'loading' ? -1 : 0}
              onClick={() => {
                if (insight.status !== 'loading') {
                  setSelectedPlanId(insight.planId);
                }
              }}
              onKeyDown={(event) => {
                if (insight.status === 'loading') {
                  return;
                }
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  setSelectedPlanId(insight.planId);
                }
              }}
              className={`pointer-events-auto relative overflow-hidden rounded-[1.35rem] border bg-white p-4 dark:bg-slate-950 ${borderClasses} ${
                insight.status === 'loading' ? '' : 'cursor-pointer'
              }`}
            >
              <div className="absolute right-3 top-3 flex items-center gap-1">
                {insight.status === 'ready' ? (
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      void toggleInsightAudio(insight);
                    }}
                    className="flex items-center gap-1 rounded-full border border-current/15 bg-white/85 px-2.5 py-1 text-[11px] font-medium text-current/80 transition-colors hover:bg-white dark:bg-slate-900/80 dark:hover:bg-slate-900"
                    aria-label={isAudioPlaying ? 'Ferma audio insight' : 'Riproduci audio insight'}
                  >
                    {isAudioLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : isAudioPlaying ? <Pause className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
                    <span>{isAudioPlaying ? 'Stop' : 'Audio'}</span>
                  </button>
                ) : null}

                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    if (playingAudioKey === audioKey) {
                      stopPlayback();
                    }
                    onRemoveInsight(insight.planId);
                  }}
                  className="rounded-full p-1 text-current/50 transition-colors hover:bg-black/5 hover:text-current dark:hover:bg-white/10"
                  aria-label="Rimuovi insight"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="mb-3 flex items-start gap-3 pr-24">
                <div className={`rounded-2xl p-2.5 ${iconWrapClasses}`}>
                  {insight.status === 'loading' ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : isWarning ? (
                    <AlertTriangle className="h-5 w-5" />
                  ) : (
                    <Trophy className="h-5 w-5" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-semibold leading-6">
                    {insight.title}
                  </h3>
                </div>
              </div>

              <p className="text-sm leading-6 text-current/80">
                {preview}
              </p>

              {audioErrorMessage ? (
                <div className="mt-3 text-xs leading-5 text-red-600 dark:text-red-300">
                  {audioErrorMessage}
                </div>
              ) : null}

              {insight.status === 'loading' ? (
                <div className="mt-3 text-[11px] font-medium uppercase tracking-[0.16em] text-current/50">
                  Generazione in corso
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <Dialog
        open={selectedInsight !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedPlanId(null);
          }
        }}
      >
        <DialogContent className="max-h-[85vh] max-w-lg grid-rows-[auto,minmax(0,1fr)] overflow-hidden">
          {selectedInsight ? (
            <>
              <DialogHeader>
                <DialogTitle className="pr-8 text-base leading-6">
                  {selectedInsight.title}
                </DialogTitle>
                {selectedInsight.status === 'loading' ? (
                  <DialogDescription>
                    Generazione in corso
                  </DialogDescription>
                ) : null}
              </DialogHeader>
              {selectedInsight.status === 'ready' ? (
                <div className="flex items-center justify-between gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      void toggleInsightAudio(selectedInsight);
                    }}
                    className="inline-flex w-fit items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    {loadingAudioKey === buildInsightAudioKey(selectedInsight) ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : playingAudioKey === buildInsightAudioKey(selectedInsight) ? (
                      <Pause className="h-4 w-4" />
                    ) : (
                      <Volume2 className="h-4 w-4" />
                    )}
                    <span>{playingAudioKey === buildInsightAudioKey(selectedInsight) ? 'Ferma audio' : 'Ascolta insight'}</span>
                  </button>
                  {audioError?.key === buildInsightAudioKey(selectedInsight) ? (
                    <span className="text-xs text-red-600 dark:text-red-300">{audioError.message}</span>
                  ) : null}
                </div>
              ) : null}
              <div className="min-h-0 overflow-y-auto whitespace-pre-wrap break-words pr-2 text-sm leading-7 text-slate-700 dark:text-slate-200">
                {selectedInsight.description}
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
