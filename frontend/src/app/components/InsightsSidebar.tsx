import { AlertTriangle, Loader2, Trophy, X } from 'lucide-react';

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
  return (
    <>
      {/* Sidebar */}
      <div className={`fixed right-0 top-0 h-screen w-80 bg-white border-l border-gray-200 p-6 overflow-y-auto z-50 transform transition-transform duration-300 shadow-lg ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}>
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 text-gray-400 hover:text-gray-600 transition-colors hover:bg-gray-100 rounded-lg"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="space-y-4 mt-12">
          <div className="mb-6">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Insights AI</h3>
            <p className="text-xs text-gray-500">Analisi on-demand sugli ultimi 3 mesi</p>
          </div>

          {/* Insights List */}
          {isGenerating ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-gray-500">
              <Loader2 className="w-6 h-6 animate-spin mb-3" />
              <p className="text-sm font-medium text-gray-700">Sto generando nuovi insights</p>
              <p className="text-xs text-gray-500 mt-1">Obiettivo utente e spese degli ultimi 3 mesi</p>
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
              {error}
            </div>
          ) : insights.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              Nessun insight disponibile. Generali dal menu a sinistra.
            </div>
          ) : (
            <div className="space-y-3">
              {insights.map((insight) => (
                <div
                  key={insight.id}
                  className={`rounded-xl px-4 py-4 shadow-sm hover:shadow-md transition-shadow border relative ${
                    insight.type === 'warning'
                      ? 'bg-orange-50 border-orange-200'
                      : 'bg-green-50 border-green-200'
                  }`}
                >
                  {/* Remove button */}
                  <button
                    onClick={() => onRemoveInsight(insight.id)}
                    className="absolute top-2 right-2 p-1 text-gray-400 hover:text-gray-600 transition-colors hover:bg-white/50 rounded"
                    aria-label="Rimuovi insight"
                  >
                    <X className="w-4 h-4" />
                  </button>

                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded-lg shadow-sm ${
                      insight.type === 'warning' ? 'bg-orange-100' : 'bg-green-100'
                    }`}>
                      {insight.type === 'warning' ? (
                        <AlertTriangle className={`w-5 h-5 ${
                          insight.type === 'warning' ? 'text-orange-600' : 'text-green-600'
                        }`} />
                      ) : (
                        <Trophy className="w-5 h-5 text-green-600" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0 pr-4">
                      <div className={`text-xs font-semibold mb-1 ${
                        insight.type === 'warning' ? 'text-orange-700' : 'text-green-700'
                      }`}>
                        {insight.title}
                      </div>
                      <p className="text-xs text-gray-600 leading-relaxed">
                        {insight.description}
                      </p>
                      <div className="text-xs text-gray-400 mt-2">
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
    </>
  );
}
