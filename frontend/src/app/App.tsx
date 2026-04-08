import { useState, useEffect } from 'react';
import { Menu, PlusCircle, ChevronLeft } from 'lucide-react';
import { Sidebar } from './components/Sidebar';
import { ChatArea, Message } from './components/ChatArea';
import { InputArea } from './components/InputArea';
import { WeeklyOverview } from './components/WeeklyOverview';
import { StoricoPanel } from './components/StoricoPanel';
import { InsightsSidebar } from './components/InsightsSidebar';
import {
  FrontendContext,
  fetchUtente,
  updateUtente,
  fetchSpeseSettimanali,
  generateInsights,
  streamChat,
  filesToAttachments,
  UtenteProfile,
  WeekData,
  GeneratedInsight,
} from './api/client';

export interface Transaction {
  id: string;
  type: 'income' | 'expense';
  description: string;
  amount: number;
  isFixed: boolean;
  week?: number;
  date: string;
  category?: string;
}

export interface Insight {
  id: string;
  type: 'warning' | 'success';
  title: string;
  description: string;
  timestamp: Date;
}

const MESI = [
  'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
  'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre',
];

function App() {
  // ---------------------------------------------------------------------------
  // Stato UI
  // ---------------------------------------------------------------------------
  const [showStorico, setShowStorico] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [showInsights, setShowInsights] = useState(false);

  // ---------------------------------------------------------------------------
  // Stato dati backend
  // ---------------------------------------------------------------------------
  const [utenteProfile, setUtenteProfile] = useState<UtenteProfile | null>(null);
  const [weeklyData, setWeeklyData] = useState<WeekData[]>([]);
  const [weeklyStartDate, setWeeklyStartDate] = useState<Date>(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });

  // ---------------------------------------------------------------------------
  // Stato chat
  // ---------------------------------------------------------------------------
  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = localStorage.getItem('messages');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed.map((msg: Message) => ({ ...msg, timestamp: new Date(msg.timestamp) }));
        }
      } catch {
        // ignora
      }
    }
    return [];
  });
  const [conversation, setConversation] = useState<Record<string, unknown>[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  // ---------------------------------------------------------------------------
  // Insights AI
  // ---------------------------------------------------------------------------
  const [insights, setInsights] = useState<Insight[]>([]);
  const [isGeneratingInsights, setIsGeneratingInsights] = useState(false);
  const [insightsError, setInsightsError] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Caricamento iniziale
  // ---------------------------------------------------------------------------
  useEffect(() => {
    fetchUtente()
      .then(setUtenteProfile)
      .catch(() => null);
    fetchSpeseSettimanali(weeklyStartDate)
      .then((r) => setWeeklyData(r.weeks))
      .catch(() => null);
  }, []);

  // Aggiorna spese settimanali quando cambia la settimana
  useEffect(() => {
    fetchSpeseSettimanali(weeklyStartDate)
      .then((r) => setWeeklyData(r.weeks))
      .catch(() => null);
  }, [weeklyStartDate]);

  // Persiste i messaggi nel localStorage
  useEffect(() => {
    localStorage.setItem('messages', JSON.stringify(messages));
  }, [messages]);

  // ---------------------------------------------------------------------------
  // Valori derivati dal profilo utente
  // ---------------------------------------------------------------------------
  const stipendio = utenteProfile?.stipendio_mensile ?? 0;
  const speseFissi = utenteProfile?.spese_fisse_essenziali_mensili ?? 0;
  const disponibile = utenteProfile?.disponibile_mensile ?? stipendio - speseFissi;
  const settimanale = disponibile / 5;
  const risparmio = utenteProfile?.risparmio_mensile ?? 0;
  const userGoal = utenteProfile?.obiettivo ?? '';
  const weeklyExpenses = weeklyData.map((w) => w.total);
  const frontendContext: FrontendContext | null = weeklyData.length
    ? {
        weekly_overview: {
          month_start: new Date(weeklyStartDate.getFullYear(), weeklyStartDate.getMonth(), 1)
            .toISOString()
            .slice(0, 10),
          month_label: `${MESI[weeklyStartDate.getMonth()]} ${weeklyStartDate.getFullYear()}`,
          default_week_index:
            weeklyData.find((week) => {
              const today = new Date();
              const start = new Date(`${week.start}T00:00:00`);
              const end = new Date(`${week.end}T23:59:59`);
              return today >= start && today <= end;
            })?.start
              ? weeklyData.findIndex((week) => {
                  const today = new Date();
                  const start = new Date(`${week.start}T00:00:00`);
                  const end = new Date(`${week.end}T23:59:59`);
                  return today >= start && today <= end;
                }) + 1
              : null,
          weeks: weeklyData.map((week, index) => {
            const today = new Date();
            const start = new Date(`${week.start}T00:00:00`);
            const end = new Date(`${week.end}T23:59:59`);
            return {
              index: index + 1,
              label: `Settimana ${index + 1}`,
              start: week.start,
              end: week.end,
              total: week.total,
              contains_today: today >= start && today <= end,
            };
          }),
        },
      }
    : null;

  // ---------------------------------------------------------------------------
  // Handler
  // ---------------------------------------------------------------------------
  const handleSetStipendio = async (value: number) => {
    try {
      const updated = await updateUtente({ stipendio_mensile: value });
      setUtenteProfile(updated);
    } catch {
      // ignora errori di rete
    }
  };

  const handleSetUserGoal = async (value: string) => {
    try {
      const updated = await updateUtente({ obiettivo: value });
      setUtenteProfile(updated);
    } catch {
      // ignora errori di rete
    }
  };

  const handleSendMessage = async (content: string, files: File[]) => {
    const attachments = await filesToAttachments(files);

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
      attachments: files.map((f) => f.name),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsStreaming(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', timestamp: new Date(), isThinking: true, reasoning: '' },
    ]);

    await streamChat(
      content,
      conversation,
      attachments,
      frontendContext,
      // onReasoning: accumula testo nel riquadro thinking
      (chunk) =>
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, reasoning: (m.reasoning ?? '') + chunk } : m,
          ),
        ),
      // onAnswer: primo chunk → togli thinking, aggiungi contenuto
      (chunk) =>
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isThinking: false, content: m.content + chunk } : m,
          ),
        ),
      (finalAnswer, updatedConversation) => {
        setConversation(updatedConversation);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isThinking: false, content: finalAnswer } : m,
          ),
        );
        setIsStreaming(false);
      },
      (error) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isThinking: false, content: `Errore: ${error}` } : m,
          ),
        );
        setIsStreaming(false);
      },
    );
  };

  const handleSuggestionClick = (suggestion: string) => {
    handleSendMessage(suggestion, []);
  };

  const handleNewConversation = () => {
    setMessages([]);
    setConversation([]);
    localStorage.removeItem('messages');
  };

  const handleGenerateInsights = async () => {
    setShowInsights(true);
    setInsights([]);
    setInsightsError(null);
    setIsGeneratingInsights(true);

    try {
      const response = await generateInsights();
      setInsights(
        response.insights.map((insight: GeneratedInsight) => ({
          ...insight,
          timestamp: new Date(insight.timestamp),
        })),
      );
    } catch (error) {
      setInsightsError(
        error instanceof Error
          ? `Generazione insight non riuscita: ${error.message}`
          : 'Generazione insight non riuscita.',
      );
    } finally {
      setIsGeneratingInsights(false);
    }
  };

  const handleRemoveInsight = (id: string) => {
    setInsights((prev) => prev.filter((insight) => insight.id !== id));
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar
        stipendio={stipendio}
        setStipendio={handleSetStipendio}
        userGoal={userGoal}
        setUserGoal={handleSetUserGoal}
        speseFissi={speseFissi}
        disponibile={disponibile}
        settimanale={settimanale}
        risparmio={risparmio}
        isOpen={showSidebar}
        onClose={() => setShowSidebar(false)}
        onOpenEstrattoConto={() => setShowStorico(true)}
        onGenerateInsights={handleGenerateInsights}
        isGeneratingInsights={isGeneratingInsights}
      />

      {/* Main content */}
      <div className="flex-1">
        {/* Top buttons */}
        <div className="fixed top-4 left-0 right-0 flex items-center justify-between px-4 z-30">
          {/* Hamburger menu - left */}
          <button
            onClick={() => setShowSidebar(true)}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <Menu className="w-6 h-6" />
          </button>

          {/* Right buttons */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleNewConversation}
              className="p-2 text-gray-400 hover:text-gray-600 transition-colors flex items-center gap-2"
            >
              <PlusCircle className="w-5 h-5" />
              <span className="text-sm font-medium">Nuova conversazione</span>
            </button>
            <button
              onClick={() => setShowInsights(true)}
              className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Mostra insights"
            >
              <ChevronLeft className="w-6 h-6" />
            </button>
          </div>
        </div>

        <div className="flex flex-col h-screen max-w-6xl mx-auto px-4 w-full">
          {/* Chat Area */}
          <ChatArea messages={messages} onSuggestionClick={handleSuggestionClick} />

          {/* Input */}
          <div className="mb-4">
            <div className="w-full max-w-5xl mx-auto">
              <InputArea onSendMessage={handleSendMessage} disabled={isStreaming} />
            </div>
          </div>

          {/* Cerchi settimanali */}
          <div className="mb-6 pb-6">
            <WeeklyOverview
              weeklyExpenses={weeklyExpenses}
              settimanale={settimanale}
              startDate={weeklyStartDate}
              onStartDateChange={setWeeklyStartDate}
            />
          </div>
        </div>
      </div>

      {/* Estratto Conto Modal */}
      <StoricoPanel
        isOpen={showStorico}
        onClose={() => setShowStorico(false)}
        transactions={[]}
      />

      {/* Insights Sidebar */}
      <InsightsSidebar
        isOpen={showInsights}
        onClose={() => setShowInsights(false)}
        insights={insights}
        isGenerating={isGeneratingInsights}
        error={insightsError}
        onRemoveInsight={handleRemoveInsight}
      />
    </div>
  );
}

export default App;
