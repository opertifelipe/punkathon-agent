import { useState } from 'react';
import { Plus, Euro } from 'lucide-react';
import { Transaction } from '../App';

interface HeaderProps {
  stipendio: number;
  setStipendio: (value: number) => void;
  additionalIncomes: Transaction[];
  addIncome: (description: string, amount: number) => void;
}

export function Header({ stipendio, setStipendio, additionalIncomes, addIncome }: HeaderProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState(stipendio.toString());
  const [showIncomeModal, setShowIncomeModal] = useState(false);
  const [newIncomeDesc, setNewIncomeDesc] = useState('');
  const [newIncomeAmount, setNewIncomeAmount] = useState('');

  const handleSave = () => {
    const value = parseFloat(inputValue);
    if (!isNaN(value) && value >= 0) {
      setStipendio(value);
    }
    setIsEditing(false);
  };

  const handleAddIncome = () => {
    const amount = parseFloat(newIncomeAmount);
    if (newIncomeDesc.trim() && !isNaN(amount) && amount > 0) {
      addIncome(newIncomeDesc, amount);
      setNewIncomeDesc('');
      setNewIncomeAmount('');
      setShowIncomeModal(false);
    }
  };

  const totalIncome = stipendio + additionalIncomes.reduce((sum, inc) => sum + inc.amount, 0);

  return (
    <div className="text-center">
      <div className="flex flex-col items-center">
        <div className="flex items-center justify-center gap-2">
          <div className="flex items-center gap-2">
            {isEditing ? (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onBlur={handleSave}
                  onKeyPress={(e) => e.key === 'Enter' && handleSave()}
                  className="text-lg font-medium border-b border-gray-400 outline-none w-28 text-gray-700 bg-transparent"
                  autoFocus
                />
                <span className="text-lg font-medium text-gray-700">€</span>
              </div>
            ) : (
              <div
                className="text-lg font-medium cursor-pointer hover:text-gray-700 text-gray-600"
                onClick={() => {
                  setIsEditing(true);
                  setInputValue(totalIncome.toString());
                }}
              >
                {totalIncome.toFixed(2)} €
              </div>
            )}
          </div>

          <button
            onClick={() => setShowIncomeModal(true)}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>
        
        <div className="text-xs text-gray-400 mt-1">
          stipendio
        </div>
      </div>

      {/* Income Modal */}
      {showIncomeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96 shadow-xl">
            <h3 className="text-xl font-bold mb-4 text-gray-800">Aggiungi Entrata Extra</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Descrizione
                </label>
                <input
                  type="text"
                  value={newIncomeDesc}
                  onChange={(e) => setNewIncomeDesc(e.target.value)}
                  placeholder="Es: Freelance, Bonus..."
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-gray-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Valore (€)
                </label>
                <input
                  type="number"
                  value={newIncomeAmount}
                  onChange={(e) => setNewIncomeAmount(e.target.value)}
                  placeholder="0.00"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:border-gray-500"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleAddIncome}
                  className="flex-1 bg-gray-700 hover:bg-gray-800 text-white rounded-lg py-2 font-medium transition-colors"
                >
                  Aggiungi
                </button>
                <button
                  onClick={() => {
                    setShowIncomeModal(false);
                    setNewIncomeDesc('');
                    setNewIncomeAmount('');
                  }}
                  className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg py-2 font-medium transition-colors"
                >
                  Annulla
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}