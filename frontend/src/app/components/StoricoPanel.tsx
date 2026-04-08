import { Transaction } from '../App';
import { Calendar, Euro, Tag, X, ArrowLeft } from 'lucide-react';

interface StoricoPanelProps {
  transactions: Transaction[];
  isOpen: boolean;
  onClose: () => void;
}

export function StoricoPanel({ transactions, isOpen, onClose }: StoricoPanelProps) {
  const sortedTransactions = [...transactions].sort((a, b) => 
    new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('it-IT', { 
      day: '2-digit', 
      month: '2-digit', 
      year: 'numeric' 
    });
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Full page overlay */}
      <div className="fixed inset-0 z-50 bg-gray-50">
        <div className="h-screen flex flex-col">
          {/* Header */}
          <div className="bg-white border-b border-gray-200 px-6 py-4">
            <div className="max-w-4xl mx-auto flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  onClick={onClose}
                  className="p-2 text-gray-400 hover:text-gray-600 transition-colors rounded-lg hover:bg-gray-100"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
                <h2 className="text-lg font-semibold text-gray-700">
                  Estratto conto
                </h2>
              </div>
              <div className="text-sm text-gray-500">
                {transactions.length} {transactions.length === 1 ? 'transazione' : 'transazioni'}
              </div>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-6 py-6">
            <div className="max-w-4xl mx-auto">
              {transactions.length === 0 ? (
                <div className="text-center py-16">
                  <p className="text-gray-400 text-sm">Nessuna transazione ancora</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {sortedTransactions.map((transaction) => (
                    <div 
                      key={transaction.id} 
                      className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow"
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex-1">
                          <p className="text-sm font-medium text-gray-800">
                            {transaction.description}
                          </p>
                          <div className="flex items-center gap-3 mt-2">
                            <div className="flex items-center gap-1 text-xs text-gray-400">
                              <Calendar className="w-3 h-3" />
                              <span>{formatDate(transaction.date)}</span>
                            </div>
                            {transaction.isFixed && (
                              <span className="px-2 py-0.5 bg-gray-100 border border-gray-200 rounded text-xs text-gray-600">
                                Fissa
                              </span>
                            )}
                            {transaction.category && (
                              <div className="flex items-center gap-1">
                                <Tag className="w-3 h-3 text-gray-400" />
                                <span className="text-xs text-gray-500 capitalize">{transaction.category}</span>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className={`text-base font-semibold ml-4 ${ 
                          transaction.type === 'income' ? 'text-green-600' : 'text-gray-700'
                        }`}>
                          {transaction.type === 'income' ? '+' : '-'}{transaction.amount.toFixed(2)} €
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}