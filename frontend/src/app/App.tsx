import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, LogOut, Menu, PlusCircle } from 'lucide-react';

import { AuthDialog, type AuthMode } from './components/AuthDialog';
import { ChatArea, Message } from './components/ChatArea';
import { InputArea } from './components/InputArea';
import { InsightsSidebar } from './components/InsightsSidebar';
import { MarketingPage } from './components/MarketingPage';
import { Sidebar } from './components/Sidebar';
import { StoricoPanel } from './components/StoricoPanel';
import { WeeklyOverview } from './components/WeeklyOverview';
import {
  AuthSession,
  FrontendContext,
  GeneratedInsight,
  UtenteProfile,
  WeekData,
  clearStoredAuthSession,
  deleteAllTransactions,
  fetchCurrentUser,
  fetchSpeseSettimanali,
  fetchUtente,
  filesToAttachments,
  generateInsights,
  getStoredAuthSession,
  storeAuthSession,
  streamChat,
  updateUtente,
} from './api/client';

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
const DEFAULT_USER_GOAL = 'Controllare le spese';
const THEME_STORAGE_KEY = 'punkagent-theme-mode';

type ThemeMode = 'light' | 'dark';

function isAuthError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }

  const message = error.message.toLowerCase();
  return (
    message.includes('autenticazione richiesta')
    || message.includes('sessione scaduta')
    || message.includes('token non valido')
    || message.includes('utente non trovato')
    || message.includes('401')
  );
}

function AuthenticatedApp({
  onSignOut,
  session,
}: {
  onSignOut: () => void;
  session: AuthSession;
}) {
  const [showStorico, setShowStorico] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [showInsights, setShowInsights] = useState(false);
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    if (typeof window === 'undefined') {
      return 'light';
    }

    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (storedTheme === 'light' || storedTheme === 'dark') {
      return storedTheme;
    }

    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  const [utenteProfile, setUtenteProfile] = useState<UtenteProfile | null>(null);
  const [weeklyData, setWeeklyData] = useState<WeekData[]>([]);
  const [weeklyStartDate, setWeeklyStartDate] = useState<Date>(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const messagesStorageKey = `punkagent-messages:${session.user.id}`;
  const conversationStorageKey = `punkagent-conversation:${session.user.id}`;
  const [messages, setMessages] = useState<Message[]>(() => {
    if (typeof window === 'undefined') {
      return [];
    }

    const saved = window.localStorage.getItem(messagesStorageKey);
    if (!saved) {
      return [];
    }

    try {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed.map((msg: Message) => ({ ...msg, timestamp: new Date(msg.timestamp) }));
      }
    } catch {
      // ignora stato locale corrotto
    }

    return [];
  });
  const latestMessagesRef = useRef<Message[]>(messages);
  const [conversation, setConversation] = useState<Record<string, unknown>[]>(() => {
    if (typeof window === 'undefined') {
      return [];
    }

    const saved = window.localStorage.getItem(conversationStorageKey);
    if (!saved) {
      return [];
    }

    try {
      const parsed = JSON.parse(saved);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });
  const [isStreaming, setIsStreaming] = useState(false);
  const [isDeletingAllTransactions, setIsDeletingAllTransactions] = useState(false);

  const [insights, setInsights] = useState<Insight[]>([]);
  const [isGeneratingInsights, setIsGeneratingInsights] = useState(false);
  const [insightsError, setInsightsError] = useState<string | null>(null);

  const handleSessionError = (error: unknown) => {
    if (isAuthError(error)) {
      onSignOut();
      return true;
    }
    return false;
  };

  const reloadPage = (updatedMessages?: Message[], updatedConversation?: Record<string, unknown>[]) => {
    if (updatedMessages) {
      latestMessagesRef.current = updatedMessages;
      window.localStorage.setItem(messagesStorageKey, JSON.stringify(updatedMessages));
    }

    if (updatedConversation) {
      window.localStorage.setItem(conversationStorageKey, JSON.stringify(updatedConversation));
    }

    window.location.reload();
  };

  useEffect(() => {
    let ignore = false;

    fetchUtente()
      .then((profile) => {
        if (!ignore) {
          setUtenteProfile(profile);
        }
      })
      .catch((error) => {
        if (!ignore) {
          handleSessionError(error);
        }
      });

    fetchSpeseSettimanali(weeklyStartDate)
      .then((response) => {
        if (!ignore) {
          setWeeklyData(response.weeks);
        }
      })
      .catch((error) => {
        if (!ignore) {
          handleSessionError(error);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;

    fetchSpeseSettimanali(weeklyStartDate)
      .then((response) => {
        if (!ignore) {
          setWeeklyData(response.weeks);
        }
      })
      .catch((error) => {
        if (!ignore) {
          handleSessionError(error);
        }
      });

    return () => {
      ignore = true;
    };
  }, [weeklyStartDate]);

  useEffect(() => {
    latestMessagesRef.current = messages;
    window.localStorage.setItem(messagesStorageKey, JSON.stringify(messages));
  }, [messages, messagesStorageKey]);

  useEffect(() => {
    window.localStorage.setItem(conversationStorageKey, JSON.stringify(conversation));
  }, [conversation, conversationStorageKey]);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', themeMode === 'dark');
    document.documentElement.style.colorScheme = themeMode;
    window.localStorage.setItem(THEME_STORAGE_KEY, themeMode);
  }, [themeMode]);

  const stipendio = utenteProfile?.stipendio_mensile ?? null;
  const speseFissi = utenteProfile?.spese_fisse_essenziali_mensili ?? 0;
  const disponibile = stipendio === null
    ? null
    : (utenteProfile?.disponibile_mensile ?? stipendio - speseFissi);
  const settimanale = disponibile === null ? null : disponibile / 5;
  const settimanaleBudget = settimanale ?? 0;
  const risparmio = utenteProfile?.risparmio_mensile ?? 0;
  const userGoal = (utenteProfile?.obiettivo ?? '').trim() || DEFAULT_USER_GOAL;
  const weeklyExpenses = weeklyData.map((week) => week.total);
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

  const handleSetStipendio = async (value: number) => {
    try {
      const updated = await updateUtente({ stipendio_mensile: value });
      setUtenteProfile(updated);
      reloadPage();
    } catch (error) {
      handleSessionError(error);
    }
  };

  const handleSetUserGoal = async (value: string) => {
    try {
      const updated = await updateUtente({ obiettivo: value });
      setUtenteProfile(updated);
      reloadPage();
    } catch (error) {
      handleSessionError(error);
    }
  };

  const handleDeleteAllTransactions = async () => {
    setIsDeletingAllTransactions(true);

    try {
      await deleteAllTransactions();
      reloadPage();
    } catch (error) {
      if (handleSessionError(error)) {
        return;
      }
      throw error instanceof Error ? error : new Error('Cancellazione transazioni non riuscita.');
    } finally {
      setIsDeletingAllTransactions(false);
    }
  };

  const handleSendMessage = async (content: string, files: File[]) => {
    const attachments = await filesToAttachments(files);

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
      attachments: files.map((file) => file.name),
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
      (chunk) =>
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId ? { ...message, reasoning: (message.reasoning ?? '') + chunk } : message,
          ),
        ),
      (chunk) =>
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId ? { ...message, isThinking: false, content: message.content + chunk } : message,
          ),
        ),
      (finalAnswer, updatedConversation, reload) => {
        const nextMessages = latestMessagesRef.current.map((message) =>
          message.id === assistantId ? { ...message, isThinking: false, content: finalAnswer } : message,
        );

        latestMessagesRef.current = nextMessages;
        setConversation(updatedConversation);
        setMessages(nextMessages);
        setIsStreaming(false);

        if (reload) {
          reloadPage(nextMessages, updatedConversation);
        }
      },
      (error) => {
        if (isAuthError(new Error(error))) {
          onSignOut();
          return;
        }

        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId ? { ...message, isThinking: false, content: `Errore: ${error}` } : message,
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
    latestMessagesRef.current = [];
    window.localStorage.removeItem(messagesStorageKey);
    window.localStorage.removeItem(conversationStorageKey);
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
      if (handleSessionError(error)) {
        return;
      }

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
    <div className="min-h-screen bg-gray-50 text-gray-900 transition-colors dark:bg-slate-950 dark:text-slate-100">
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
        onDeleteAllTransactions={handleDeleteAllTransactions}
        isGeneratingInsights={isGeneratingInsights}
        isDeletingAllTransactions={isDeletingAllTransactions}
        themeMode={themeMode}
        onThemeChange={setThemeMode}
      />

      <div className="flex-1">
        <div className="fixed left-0 right-0 top-4 z-30 flex items-center justify-between px-4 relative">
          <button
            onClick={() => setShowSidebar(true)}
            className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:text-slate-500 dark:hover:bg-slate-900 dark:hover:text-slate-200"
          >
            <Menu className="h-6 w-6" />
          </button>

          <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-2 pointer-events-none">
            <img src="/logo.png" alt="PunkAgent" className="h-7 w-7 object-contain" />
            <span
              className="text-sm font-semibold uppercase tracking-[0.22em] text-orange-500"
              style={{ fontFamily: '"Space Grotesk", "Avenir Next", sans-serif' }}
            >
              PunkAgent
            </span>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-white/70 bg-white/80 px-3 py-2 shadow-lg backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
            <div className="hidden text-right sm:block">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-orange-500">Sessione</p>
              <p className="text-sm text-slate-700 dark:text-slate-200">
                {session.user.nome} {session.user.cognome}
              </p>
            </div>

            <button
              onClick={handleNewConversation}
              className="flex items-center gap-2 rounded-full px-3 py-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
            >
              <PlusCircle className="h-5 w-5" />
              <span className="hidden text-sm font-medium md:inline">Nuova conversazione</span>
            </button>
            <button
              onClick={() => setShowInsights(true)}
              className="rounded-full p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
              aria-label="Mostra insights"
            >
              <ChevronLeft className="h-6 w-6" />
            </button>
            <button
              onClick={onSignOut}
              className="rounded-full p-2 text-gray-500 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-950/30 dark:hover:text-red-300"
              aria-label="Esci"
            >
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="mx-auto flex h-screen max-w-6xl w-full flex-col px-4">
          <ChatArea messages={messages} onSuggestionClick={handleSuggestionClick} />

          <div className="mb-4">
            <div className="mx-auto w-full max-w-5xl">
              <InputArea onSendMessage={handleSendMessage} disabled={isStreaming} />
            </div>
          </div>

          <div className="mb-6 pb-6">
            <WeeklyOverview
              weeklyExpenses={weeklyExpenses}
              settimanale={settimanaleBudget}
              startDate={weeklyStartDate}
              onStartDateChange={setWeeklyStartDate}
            />
          </div>
        </div>
      </div>

      <StoricoPanel
        isOpen={showStorico}
        onClose={() => setShowStorico(false)}
      />

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

function App() {
  const [authSession, setAuthSession] = useState<AuthSession | null>(() => getStoredAuthSession());
  const [authChecked, setAuthChecked] = useState(false);
  const [authDialogOpen, setAuthDialogOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>('signup');

  useEffect(() => {
    const stored = getStoredAuthSession();
    if (!stored) {
      setAuthChecked(true);
      return;
    }

    let ignore = false;

    fetchCurrentUser()
      .then((user) => {
        if (ignore) {
          return;
        }
        const refreshedSession = { ...stored, user };
        storeAuthSession(refreshedSession);
        setAuthSession(refreshedSession);
      })
      .catch(() => {
        if (ignore) {
          return;
        }
        clearStoredAuthSession();
        setAuthSession(null);
      })
      .finally(() => {
        if (!ignore) {
          setAuthChecked(true);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  const handleAuthenticated = (session: AuthSession) => {
    storeAuthSession(session);
    setAuthSession(session);
    setAuthDialogOpen(false);
  };

  const handleOpenAuth = (mode: AuthMode) => {
    setAuthMode(mode);
    setAuthDialogOpen(true);
  };

  const handleSignOut = () => {
    clearStoredAuthSession();
    setAuthSession(null);
  };

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[linear-gradient(135deg,#f6efe8_0%,#f9fbff_42%,#eef7f1_100%)] px-6">
        <div className="rounded-[2rem] border border-white/80 bg-white/80 px-8 py-7 text-center shadow-[0_28px_90px_rgba(15,23,42,0.1)]">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-600">PunkAgent</p>
          <p className="mt-3 text-lg text-slate-700">Sto ripristinando la tua sessione...</p>
        </div>
      </div>
    );
  }

  if (!authSession) {
    return (
      <>
        <MarketingPage
          onOpenSignin={() => handleOpenAuth('signin')}
          onOpenSignup={() => handleOpenAuth('signup')}
        />
        <AuthDialog
          mode={authMode}
          onAuthenticated={handleAuthenticated}
          onModeChange={setAuthMode}
          onOpenChange={setAuthDialogOpen}
          open={authDialogOpen}
        />
      </>
    );
  }

  return (
    <AuthenticatedApp
      key={authSession.user.id}
      onSignOut={handleSignOut}
      session={authSession}
    />
  );
}

export default App;
