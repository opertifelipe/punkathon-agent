import { useState } from 'react';
import { Target, AlertCircle, TrendingUp, Wallet, PiggyBank, X, FileText, Sparkles, Loader2 } from 'lucide-react';

interface SidebarProps {
  stipendio: number;
  setStipendio: (value: number) => void;
  userGoal?: string;
  setUserGoal: (value: string) => void;
  speseFissi: number;
  disponibile: number;
  settimanale: number;
  risparmio: number;
  isOpen: boolean;
  onClose: () => void;
  onOpenEstrattoConto: () => void;
  onGenerateInsights: () => void;
  isGeneratingInsights: boolean;
}

export function Sidebar({
  stipendio,
  setStipendio,
  userGoal,
  setUserGoal,
  speseFissi,
  disponibile,
  settimanale,
  risparmio,
  isOpen,
  onClose,
  onOpenEstrattoConto,
  onGenerateInsights,
  isGeneratingInsights,
}: SidebarProps) {
  const [isEditingGoal, setIsEditingGoal] = useState(false);
  const [goalInput, setGoalInput] = useState(userGoal || '');

  const [isEditingStipendio, setIsEditingStipendio] = useState(false);
  const [stipendioInput, setStipendioInput] = useState(stipendio.toString());

  const handleGoalSave = () => {
    if (goalInput.trim()) {
      setUserGoal(goalInput.trim());
    }
    setIsEditingGoal(false);
  };

  const handleStipendioSave = () => {
    const value = parseFloat(stipendioInput);
    if (!isNaN(value) && value >= 0) {
      setStipendio(value);
    }
    setIsEditingStipendio(false);
  };

  const handleEstrattoConto = () => {
    onOpenEstrattoConto();
    onClose();
  };

  const handleGenerateInsights = () => {
    onGenerateInsights();
    onClose();
  };

  return (
    <>
      <div
        className={`fixed left-0 top-0 h-screen w-72 bg-white border-r border-gray-200 p-6 overflow-y-auto z-50 transform transition-transform duration-300 shadow-lg ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 text-gray-400 hover:text-gray-600 transition-colors hover:bg-gray-100 rounded-lg"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="space-y-4 mt-12">
          <div className="mb-6">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Panoramica finanziaria
            </h3>
          </div>

          {/* Obiettivo */}
          <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-4 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-white rounded-lg shadow-sm">
                <Target className="w-5 h-5 text-gray-600" />
              </div>
              <div className="flex-1">
                <div className="text-xs font-medium text-gray-600 mb-1">Obiettivo</div>
                {isEditingGoal ? (
                  <input
                    type="text"
                    value={goalInput}
                    onChange={(e) => setGoalInput(e.target.value)}
                    onBlur={handleGoalSave}
                    onKeyPress={(e) => e.key === 'Enter' && handleGoalSave()}
                    className="border-b-2 border-gray-400 outline-none w-full bg-transparent font-semibold text-gray-800 text-sm"
                    autoFocus
                    placeholder="Es: Comprare una macchina"
                  />
                ) : (
                  <div
                    className="text-sm font-semibold text-gray-800 cursor-pointer hover:text-gray-600 transition-colors"
                    onClick={() => {
                      setIsEditingGoal(true);
                      setGoalInput(userGoal || '');
                    }}
                  >
                    {userGoal || 'Imposta un obiettivo'}
                  </div>
                )}
                <p className="text-xs text-gray-400 mt-1">Clicca per modificare</p>
              </div>
            </div>
          </div>

          {/* Stipendio */}
          <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-4 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-white rounded-lg shadow-sm">
                <Wallet className="w-5 h-5 text-gray-600" />
              </div>
              <div className="flex-1">
                <div className="text-xs font-medium text-gray-600 mb-1">Stipendio mensile</div>
                {isEditingStipendio ? (
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      value={stipendioInput}
                      onChange={(e) => setStipendioInput(e.target.value)}
                      onBlur={handleStipendioSave}
                      onKeyPress={(e) => e.key === 'Enter' && handleStipendioSave()}
                      className="border-b-2 border-gray-400 outline-none w-32 bg-transparent font-bold text-gray-800 text-xl"
                      autoFocus
                    />
                    <span className="font-bold text-gray-800 text-xl">€</span>
                  </div>
                ) : (
                  <div
                    className="text-xl font-bold text-gray-800 cursor-pointer hover:text-gray-600 transition-colors"
                    onClick={() => {
                      setIsEditingStipendio(true);
                      setStipendioInput(stipendio.toString());
                    }}
                  >
                    {stipendio.toFixed(2)} €
                  </div>
                )}
                <p className="text-xs text-gray-400 mt-1">Clicca per modificare</p>
              </div>
            </div>
          </div>

          {/* Spese Fisse (read-only) */}
          <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-4 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-white rounded-lg shadow-sm">
                <AlertCircle className="w-5 h-5 text-gray-600" />
              </div>
              <div className="flex-1">
                <div className="text-xs font-medium text-gray-600 mb-1">Spese fisse</div>
                <div className="text-lg font-bold text-gray-800">{speseFissi.toFixed(2)} €</div>
                <p className="text-xs text-gray-400 mt-1">Calcolato automaticamente</p>
              </div>
            </div>
          </div>

          {/* Disponibile */}
          <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-4 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-white rounded-lg shadow-sm">
                <TrendingUp className="w-5 h-5 text-gray-600" />
              </div>
              <div className="flex-1">
                <div className="text-xs font-medium text-gray-600 mb-2">Disponibile</div>
                <div className="text-xl font-bold text-gray-800 mb-1">
                  {disponibile.toFixed(2)} €
                </div>
                <div className="text-xs text-gray-500">({settimanale.toFixed(2)} € a settimana)</div>
              </div>
            </div>
          </div>

          {/* Risparmio (read-only) */}
          <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-4 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-white rounded-lg shadow-sm">
                <PiggyBank className="w-5 h-5 text-gray-600" />
              </div>
              <div className="flex-1">
                <div className="text-xs font-medium text-gray-600 mb-1">Risparmio mensile</div>
                <div className="text-lg font-bold text-gray-800">{risparmio.toFixed(2)} €</div>
                <p className="text-xs text-gray-400 mt-1">Entrate − Spese del mese</p>
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-gray-200 my-6"></div>

          {/* Estratto Conto Button */}
          <button
            onClick={handleEstrattoConto}
            className="w-full flex items-center gap-3 px-4 py-3.5 text-gray-700 bg-gray-50 hover:bg-gray-100 rounded-xl transition-all font-medium border border-gray-200 hover:border-gray-300 shadow-sm"
          >
            <FileText className="w-5 h-5" />
            <span className="text-sm">Estratto conto</span>
          </button>

          <button
            onClick={handleGenerateInsights}
            disabled={isGeneratingInsights}
            className="w-full flex items-center gap-3 px-4 py-3.5 text-white bg-gray-900 hover:bg-gray-800 rounded-xl transition-all font-medium border border-gray-900 shadow-sm disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isGeneratingInsights ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
            <span className="text-sm">
              {isGeneratingInsights ? 'Generazione insights...' : 'Genera nuovi insights'}
            </span>
          </button>
        </div>
      </div>
    </>
  );
}
