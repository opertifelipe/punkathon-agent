import { useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { Transaction } from '../App';

interface SummaryCardsProps {
  transactions: Transaction[];
}

export function SummaryCards({
  transactions
}: SummaryCardsProps) {
  const [showIrrinunciabili, setShowIrrinunciabili] = useState(false);

  const irrinunciabili = transactions.filter(t => t.type === 'expense' && t.category === 'irrinunciabile');

  if (irrinunciabili.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2.5">
      {/* Spese Irrinunciabili */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-gray-500" />
            <div className="text-sm">
              <span className="text-gray-600">Spese irrinunciabili: </span>
              <span className="font-semibold text-gray-700">
                {irrinunciabili.reduce((sum, t) => sum + t.amount, 0).toFixed(2)} €
              </span>
            </div>
          </div>
          <button
            onClick={() => setShowIrrinunciabili(!showIrrinunciabili)}
            className="text-xs text-gray-500 hover:text-gray-700 underline"
          >
            {showIrrinunciabili ? 'Nascondi' : 'Dettagli'}
          </button>
        </div>
        {showIrrinunciabili && (
          <div className="mt-3 pt-3 border-t border-gray-200 space-y-2">
            <div className="text-xs font-medium text-gray-600 mb-2">Spese irrinunciabili:</div>
            {irrinunciabili.map((expense) => (
              <div key={expense.id} className="flex justify-between text-xs">
                <span className="text-gray-600">{expense.description}</span>
                <span className="font-medium text-gray-700">{expense.amount.toFixed(2)} €</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}