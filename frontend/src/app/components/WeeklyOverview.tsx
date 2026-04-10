import { ChevronLeft, ChevronRight } from 'lucide-react';

interface WeeklyOverviewProps {
  weeklyExpenses: number[];
  settimanale: number;
  startDate: Date; // sempre il 1° del mese selezionato
  onStartDateChange: (date: Date) => void;
}

const MESI = [
  'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
  'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre',
];

export function WeeklyOverview({
  weeklyExpenses,
  settimanale,
  startDate,
  onStartDateChange,
}: WeeklyOverviewProps) {
  const firstOfMonth = new Date(startDate.getFullYear(), startDate.getMonth(), 1);

  const handlePrevMonth = () => {
    const d = new Date(firstOfMonth);
    d.setMonth(d.getMonth() - 1);
    onStartDateChange(d);
  };

  const handleNextMonth = () => {
    const d = new Date(firstOfMonth);
    d.setMonth(d.getMonth() + 1);
    onStartDateChange(d);
  };

  const monthLabel = `${MESI[firstOfMonth.getMonth()]} ${firstOfMonth.getFullYear()}`;

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Navigazione mese */}
      <div className="flex items-center gap-4">
        <button
          onClick={handlePrevMonth}
          className="p-1 text-gray-400 transition-colors hover:text-gray-600 dark:text-slate-500 dark:hover:text-slate-200"
          aria-label="Mese precedente"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>

        <span className="w-36 text-center text-sm font-medium text-gray-600 dark:text-slate-300">{monthLabel}</span>

        <button
          onClick={handleNextMonth}
          className="p-1 text-gray-400 transition-colors hover:text-gray-600 dark:text-slate-500 dark:hover:text-slate-200"
          aria-label="Mese successivo"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {/* Cerchi settimanali */}
      <div className="flex justify-center gap-4">
        {[0, 1, 2, 3, 4].map((i) => {
          const spent = weeklyExpenses[i] || 0;
          const isOverBudget = settimanale > 0 && spent > settimanale;

          const weekStart = new Date(firstOfMonth);
          weekStart.setDate(1 + i * 7);

          const weekEnd = new Date(weekStart);
          weekEnd.setDate(weekStart.getDate() + 6);

          const fmt = (d: Date) =>
            `${d.getDate()} ${d.toLocaleDateString('it-IT', { month: 'short' })}`;

          return (
            <div key={i} className="flex flex-col items-center">
              <div className="text-center mb-2">
                <div className="text-[10px] font-medium text-gray-500 dark:text-slate-400">Settimana {i + 1}</div>
                <div className="text-[9px] text-gray-400 dark:text-slate-500">{fmt(weekStart)} – {fmt(weekEnd)}</div>
              </div>

              <div
                className={`w-14 h-14 rounded-full flex items-center justify-center border-2 transition-colors ${
                  isOverBudget
                    ? 'border-gray-400 bg-gray-100 dark:border-amber-500/40 dark:bg-amber-500/10'
                    : 'border-gray-300 bg-white dark:border-slate-700 dark:bg-slate-900'
                }`}
              >
                <div className="text-sm font-semibold text-gray-700 dark:text-slate-100">{spent.toFixed(0)}€</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
