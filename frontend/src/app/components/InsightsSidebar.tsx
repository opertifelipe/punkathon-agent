import { useMemo, useState } from 'react';
import { AlertTriangle, Loader2, Trophy, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';

interface Insight {
  id: string;
  type: 'warning' | 'success';
  title: string;
  description: string;
  timestamp: Date;
}

interface InsightsSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  insights: Insight[];
  isGenerating: boolean;
  error: string | null;
  onRemoveInsight: (id: string) => void;
}

export function InsightsSidebar({
  isOpen,
  onClose,
  insights,
  isGenerating,
  error,
  onRemoveInsight,
}: InsightsSidebarProps) {
  const [selectedInsightId, setSelectedInsightId] = useState<string | null>(null);

  const selectedInsight = useMemo(
    () => insights.find((insight) => insight.id === selectedInsightId) ?? null,
    [insights, selectedInsightId],
  );

  const buildPreview = (text: string) => {
    const cleaned = text.trim();
    if (cleaned.length <= 150) {
      return cleaned;
    }
    return `${cleaned.slice(0, 147).trimEnd()}...`;
  };

  return (
    <>
      {/* Sidebar */}
      <div className={`fixed right-0 top-0 z-50 h-screen w-80 overflow-y-auto border-l border-gray-200 bg-white p-6 shadow-lg transform transition-transform duration-300 dark:border-slate-800 dark:bg-slate-950 ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}>
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:text-slate-500 dark:hover:bg-slate-900 dark:hover:text-slate-200"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="space-y-4 mt-12">
          <div className="mb-6">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-slate-500">Insights AI</h3>
            <p className="text-xs text-gray-500 dark:text-slate-400">Analisi on-demand sugli ultimi 3 mesi</p>
          </div>

          {/* Insights List */}
          {isGenerating ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-gray-500 dark:text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin mb-3" />
              <p className="text-sm font-medium text-gray-700 dark:text-slate-100">Sto generando nuovi insights</p>
              <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">Obiettivo utente e spese degli ultimi 3 mesi</p>
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
              {error}
            </div>
          ) : insights.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-400 dark:text-slate-500">
              Nessun insight disponibile. Generali dal menu a sinistra.
            </div>
          ) : (
            <div className="space-y-3">
              {insights.map((insight) => (
                <div
                  key={insight.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedInsightId(insight.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelectedInsightId(insight.id);
                    }
                  }}
                  className={`rounded-xl px-4 py-4 shadow-sm hover:shadow-md transition-shadow border relative ${
                    insight.type === 'warning'
                      ? 'bg-orange-50 border-orange-200 dark:border-orange-500/30 dark:bg-orange-500/10'
                      : 'bg-green-50 border-green-200 dark:border-emerald-500/30 dark:bg-emerald-500/10'
                  } cursor-pointer`}
                >
                  {/* Remove button */}
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      onRemoveInsight(insight.id);
                      if (selectedInsightId === insight.id) {
                        setSelectedInsightId(null);
                      }
                    }}
                    className="absolute top-2 right-2 rounded p-1 text-gray-400 transition-colors hover:bg-white/50 hover:text-gray-600 dark:text-slate-500 dark:hover:bg-slate-900/50 dark:hover:text-slate-200"
                    aria-label="Rimuovi insight"
                  >
                    <X className="w-4 h-4" />
                  </button>

                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded-lg shadow-sm ${
                      insight.type === 'warning' ? 'bg-orange-100 dark:bg-orange-500/15' : 'bg-green-100 dark:bg-emerald-500/15'
                    }`}>
                      {insight.type === 'warning' ? (
                        <AlertTriangle className={`w-5 h-5 ${
                          insight.type === 'warning' ? 'text-orange-600 dark:text-orange-300' : 'text-green-600'
                        }`} />
                      ) : (
                        <Trophy className="w-5 h-5 text-green-600 dark:text-emerald-300" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0 pr-4">
                      <div className={`text-xs font-semibold mb-1 ${
                        insight.type === 'warning' ? 'text-orange-700 dark:text-orange-200' : 'text-green-700 dark:text-emerald-200'
                      }`}>
                        {insight.title}
                      </div>
                      <p className="text-xs leading-relaxed text-gray-600 dark:text-slate-300">
                        {buildPreview(insight.description)}
                      </p>
                      {insight.description.trim().length > 150 ? (
                        <div className="mt-2 text-[11px] font-medium text-gray-500 dark:text-slate-400">
                          Clicca per leggere tutto
                        </div>
                      ) : null}
                      <div className="mt-2 text-xs text-gray-400 dark:text-slate-500">
                        {insight.timestamp.toLocaleString('it-IT', {
                          day: 'numeric',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <Dialog
        open={selectedInsight !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedInsightId(null);
          }
        }}
      >
        <DialogContent className="max-w-xl">
          {selectedInsight ? (
            <>
              <DialogHeader>
                <DialogTitle className={selectedInsight.type === 'warning' ? 'text-orange-700 dark:text-orange-200' : 'text-green-700 dark:text-emerald-200'}>
                  {selectedInsight.title}
                </DialogTitle>
                <DialogDescription>
                  {selectedInsight.timestamp.toLocaleString('it-IT', {
                    day: 'numeric',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </DialogDescription>
              </DialogHeader>
              <div className="max-h-[60vh] overflow-y-auto pr-2 text-sm leading-7 text-gray-700 dark:text-slate-200">
                {selectedInsight.description}
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
