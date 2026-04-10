import { useEffect, useState } from 'react';
import { Target, AlertCircle, TrendingUp, Wallet, PiggyBank, X, FileText, Sparkles, Loader2, Settings, Moon, Sun } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Switch } from './ui/switch';

interface SidebarProps {
  stipendio: number | null;
  setStipendio: (value: number) => void;
  userGoal?: string;
  setUserGoal: (value: string) => void;
  speseFissi: number;
  disponibile: number | null;
  settimanale: number | null;
  risparmio: number;
  isOpen: boolean;
  onClose: () => void;
  onOpenEstrattoConto: () => void;
  onGenerateInsights: () => void;
  isGeneratingInsights: boolean;
  themeMode: 'light' | 'dark';
  onThemeChange: (themeMode: 'light' | 'dark') => void;
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
  themeMode,
  onThemeChange,
}: SidebarProps) {
  const [isEditingGoal, setIsEditingGoal] = useState(false);
  const [goalInput, setGoalInput] = useState(userGoal || '');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const [isEditingStipendio, setIsEditingStipendio] = useState(false);
  const [stipendioInput, setStipendioInput] = useState(stipendio === null ? '' : stipendio.toString());

  useEffect(() => {
    setGoalInput(userGoal || '');
  }, [userGoal]);

  useEffect(() => {
    setStipendioInput(stipendio === null ? '' : stipendio.toString());
  }, [stipendio]);

  const formatCurrency = (value: number | null) => {
    if (value === null) {
      return 'NA';
    }
    return `${value.toFixed(2)} €`;
  };

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
        className={`fixed left-0 top-0 h-screen w-72 overflow-y-auto border-r border-gray-200 bg-white p-6 shadow-lg z-50 transform transition-transform duration-300 dark:border-slate-800 dark:bg-slate-950 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:text-slate-500 dark:hover:bg-slate-900 dark:hover:text-slate-200"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="space-y-4 mt-12">
          <div className="mb-6">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-slate-500">
              Panoramica finanziaria
            </h3>
          </div>

          {/* Obiettivo */}
          <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-4 shadow-sm transition-shadow hover:shadow-md dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-white p-2 shadow-sm dark:bg-slate-900 dark:shadow-none">
                <Target className="w-5 h-5 text-gray-600 dark:text-slate-300" />
              </div>
              <div className="flex-1">
                <div className="mb-1 text-xs font-medium text-gray-600 dark:text-slate-400">Obiettivo</div>
                {isEditingGoal ? (
                  <input
                    type="text"
                    value={goalInput}
                    onChange={(e) => setGoalInput(e.target.value)}
                    onBlur={handleGoalSave}
                    onKeyPress={(e) => e.key === 'Enter' && handleGoalSave()}
                    className="w-full border-b-2 border-gray-400 bg-transparent text-sm font-semibold text-gray-800 outline-none dark:border-slate-600 dark:text-slate-100"
                    autoFocus
                    placeholder="Es: Comprare una macchina"
                  />
                ) : (
                  <div
                    className="cursor-pointer text-sm font-semibold text-gray-800 transition-colors hover:text-gray-600 dark:text-slate-100 dark:hover:text-slate-300"
                    onClick={() => {
                      setIsEditingGoal(true);
                      setGoalInput(userGoal || '');
                    }}
                  >
                    {userGoal || 'Controllare le spese'}
                  </div>
                )}
                <p className="mt-1 text-xs text-gray-400 dark:text-slate-500">Clicca per modificare</p>
              </div>
            </div>
          </div>

          {/* Stipendio */}
          <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-4 shadow-sm transition-shadow hover:shadow-md dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-white p-2 shadow-sm dark:bg-slate-900 dark:shadow-none">
                <Wallet className="w-5 h-5 text-gray-600 dark:text-slate-300" />
              </div>
              <div className="flex-1">
                <div className="mb-1 text-xs font-medium text-gray-600 dark:text-slate-400">Stipendio mensile</div>
                {isEditingStipendio ? (
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      value={stipendioInput}
                      onChange={(e) => setStipendioInput(e.target.value)}
                      onBlur={handleStipendioSave}
                      onKeyPress={(e) => e.key === 'Enter' && handleStipendioSave()}
                      className="w-32 border-b-2 border-gray-400 bg-transparent text-xl font-bold text-gray-800 outline-none dark:border-slate-600 dark:text-slate-100"
                      autoFocus
                    />
                    <span className="text-xl font-bold text-gray-800 dark:text-slate-100">€</span>
                  </div>
                ) : (
                  <div
                    className="cursor-pointer text-xl font-bold text-gray-800 transition-colors hover:text-gray-600 dark:text-slate-100 dark:hover:text-slate-300"
                    onClick={() => {
                      setIsEditingStipendio(true);
                      setStipendioInput(stipendio === null ? '' : stipendio.toString());
                    }}
                  >
                    {formatCurrency(stipendio)}
                  </div>
                )}
                <p className="mt-1 text-xs text-gray-400 dark:text-slate-500">Clicca per modificare</p>
              </div>
            </div>
          </div>

          {/* Spese Fisse (read-only) */}
          <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-4 shadow-sm transition-shadow hover:shadow-md dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-white p-2 shadow-sm dark:bg-slate-900 dark:shadow-none">
                <AlertCircle className="w-5 h-5 text-gray-600 dark:text-slate-300" />
              </div>
              <div className="flex-1">
                <div className="mb-1 text-xs font-medium text-gray-600 dark:text-slate-400">Spese fisse</div>
                <div className="text-lg font-bold text-gray-800 dark:text-slate-100">{speseFissi.toFixed(2)} €</div>
                <p className="mt-1 text-xs text-gray-400 dark:text-slate-500">Calcolato automaticamente</p>
              </div>
            </div>
          </div>

          {/* Disponibile */}
          <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-4 shadow-sm transition-shadow hover:shadow-md dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-white p-2 shadow-sm dark:bg-slate-900 dark:shadow-none">
                <TrendingUp className="w-5 h-5 text-gray-600 dark:text-slate-300" />
              </div>
              <div className="flex-1">
                <div className="mb-2 text-xs font-medium text-gray-600 dark:text-slate-400">Disponibile</div>
                <div className="mb-1 text-xl font-bold text-gray-800 dark:text-slate-100">
                  {formatCurrency(disponibile)}
                </div>
                <div className="text-xs text-gray-500 dark:text-slate-500">
                  {settimanale === null ? '(NA a settimana)' : `(${settimanale.toFixed(2)} € a settimana)`}
                </div>
              </div>
            </div>
          </div>

          {/* Risparmio (read-only) */}
          <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-4 shadow-sm transition-shadow hover:shadow-md dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex items-start gap-3">
              <div className="rounded-lg bg-white p-2 shadow-sm dark:bg-slate-900 dark:shadow-none">
                <PiggyBank className="w-5 h-5 text-gray-600 dark:text-slate-300" />
              </div>
              <div className="flex-1">
                <div className="mb-1 text-xs font-medium text-gray-600 dark:text-slate-400">Risparmio mensile</div>
                <div className="text-lg font-bold text-gray-800 dark:text-slate-100">{risparmio.toFixed(2)} €</div>
                <p className="mt-1 text-xs text-gray-400 dark:text-slate-500">Entrate − Spese del mese</p>
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="my-6 border-t border-gray-200 dark:border-slate-800"></div>

          {/* Estratto Conto Button */}
          <button
            onClick={handleEstrattoConto}
            className="w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-3.5 text-gray-700 shadow-sm transition-all hover:border-gray-300 hover:bg-gray-100 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-100 dark:hover:border-slate-700 dark:hover:bg-slate-900"
          >
            <div className="flex items-center gap-3">
              <FileText className="w-5 h-5" />
            <span className="text-sm">Estratto conto</span>
            </div>
          </button>

          <button
            onClick={handleGenerateInsights}
            disabled={isGeneratingInsights}
            className="w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-3.5 text-gray-700 shadow-sm transition-all hover:border-gray-300 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-100 dark:hover:border-slate-700 dark:hover:bg-slate-900"
          >
            <div className="flex items-center gap-3">
              {isGeneratingInsights ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
              <span className="text-sm">
                {isGeneratingInsights ? 'Generazione insights...' : 'Genera nuovi insights'}
              </span>
            </div>
          </button>
        </div>

        <button
          onClick={() => setIsSettingsOpen(true)}
          className="absolute bottom-5 left-5 rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:text-slate-500 dark:hover:bg-slate-900 dark:hover:text-slate-200"
          aria-label="Apri impostazioni tema"
        >
          <Settings className="w-5 h-5" />
        </button>
      </div>

      <Dialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Impostazioni</DialogTitle>
            <DialogDescription>
              Scegli il tema migliore per leggere l'app di giorno o di notte.
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold text-gray-800 dark:text-slate-100">
                  {themeMode === 'dark' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
                  Tema notturno
                </div>
                <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">
                  Attiva il dark mode per una visione piu' riposante in ambienti bui.
                </p>
              </div>

              <Switch
                checked={themeMode === 'dark'}
                onCheckedChange={(checked) => onThemeChange(checked ? 'dark' : 'light')}
                aria-label="Attiva tema scuro"
              />
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
