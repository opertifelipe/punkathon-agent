import { TrendingUp, AlertTriangle, CheckCircle, Info } from 'lucide-react';

interface InsightsPanelProps {
  totalIncome: number;
  speseFissi: number;
  weeklyExpenses: number[];
  weeklyBudget: number;
  risparmio: number;
}

export function InsightsPanel({ 
  totalIncome, 
  speseFissi, 
  weeklyExpenses, 
  weeklyBudget,
  risparmio
}: InsightsPanelProps) {
  const totalSpent = weeklyExpenses.reduce((sum, exp) => sum + exp, 0);
  const disponibile = totalIncome - speseFissi - risparmio;
  const percentageSpent = disponibile > 0 ? (totalSpent / disponibile) * 100 : 0;
  
  const highestWeek = Math.max(...weeklyExpenses);
  const highestWeekIndex = weeklyExpenses.indexOf(highestWeek);
  
  const insights = [];

  // Insight 1: Spending trend
  if (percentageSpent > 80) {
    insights.push({
      type: 'warning',
      message: `Hai già speso ${percentageSpent.toFixed(0)}% del budget disponibile.`
    });
  } else if (percentageSpent < 50 && totalIncome > 0) {
    insights.push({
      type: 'success',
      message: `Hai speso solo ${percentageSpent.toFixed(0)}% del budget disponibile.`
    });
  }

  // Insight 2: Weekly comparison
  if (highestWeek > weeklyBudget * 1.5) {
    insights.push({
      type: 'warning',
      message: `La settimana ${highestWeekIndex + 1} ha avuto spese significativamente alte (${highestWeek.toFixed(2)} €).`
    });
  }

  // Insight 3: Savings
  const savingsPercentage = (risparmio / totalIncome) * 100;
  if (savingsPercentage > 20) {
    insights.push({
      type: 'success',
      message: `Stai risparmiando ${savingsPercentage.toFixed(0)}% dello stipendio.`
    });
  } else if (savingsPercentage < 10 && totalIncome > 0) {
    insights.push({
      type: 'info',
      message: `Considera di aumentare il risparmio al 10-15%.`
    });
  }

  // Insight 4: Fixed expenses
  const fixedExpensesPercentage = (speseFissi / totalIncome) * 100;
  if (fixedExpensesPercentage > 50) {
    insights.push({
      type: 'warning',
      message: `Le spese fisse rappresentano ${fixedExpensesPercentage.toFixed(0)}% dello stipendio.`
    });
  }

  if (insights.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-3 overflow-x-auto pb-1">
      {insights.map((insight, index) => (
        <div 
          key={index} 
          className="flex items-center gap-2 bg-gray-100 border border-gray-200 rounded-lg px-3 py-2 whitespace-nowrap flex-shrink-0"
        >
          <AlertTriangle className="w-4 h-4 text-gray-500 flex-shrink-0" />
          <p className="text-xs text-gray-600">
            {insight.message}
          </p>
        </div>
      ))}
    </div>
  );
}