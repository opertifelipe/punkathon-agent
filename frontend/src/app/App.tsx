import { useEffect, useRef, useState } from 'react';
import { LogOut, Menu, PlusCircle } from 'lucide-react';

import { AuthDialog, type AuthMode } from './components/AuthDialog';
import { ChatArea, Message } from './components/ChatArea';
import { InsightPopups, type InsightPopupItem } from './components/InsightPopups';
import { InputArea } from './components/InputArea';
import { MarketingPage } from './components/MarketingPage';
import { Sidebar } from './components/Sidebar';
import { StoricoPanel } from './components/StoricoPanel';
import { WeeklyOverview } from './components/WeeklyOverview';
import {
  AuthSession,
  FrontendContext,
  clearStoredAuthSession,
  deleteAllTransactions,
  fetchInsightsStatus,
  fetchCurrentUser,
  fetchSpeseSettimanali,
  fetchUtente,
  filesToAttachments,
  generateSingleInsight,
  getStoredAuthSession,
  storeAuthSession,
  streamChat,
  updateUtente,
  UtenteProfile,
  WeekData,
} from './api/client';

type InsightType = 'warning' | 'success';

interface InsightPlan {
  id: string;
  type: InsightType;
  focusHint: string;
  loadingTitle: string;
  loadingDescription: string;
}

const MESI = [
  'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
  'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre',
];
const DEFAULT_USER_GOAL = 'Controllo delle finanze';
const THEME_STORAGE_KEY = 'punkagent-theme-mode';
const INSIGHT_PLANS: InsightPlan[] = [
  {
    id: 'success-budget-discipline',
    type: 'success',
    focusHint: 'Evidenzia un comportamento disciplinato sul budget o sul cashflow recente.',
    loadingTitle: 'Vediamo dove sei stato bravo',
    loadingDescription: 'Setaccio i numeri per trovare dove stai tenendo i soldi al guinzaglio.',
  },
  {
    id: 'warning-budget-leak',
    type: 'warning',
    focusHint: 'Segnala la perdita di controllo piu urgente su budget, margine o categoria di spesa.',
    loadingTitle: 'Sto fiutando dove perdi i soldi',
    loadingDescription: 'Controllo quali buchi hai nel budget.',
  },
  {
    id: 'success-good-habit',
    type: 'success',
    focusHint: 'Evidenzia un\'abitudine utile o una categoria sotto controllo che protegge il margine.',
    loadingTitle: 'Sto cercando una buona abitudine',
    loadingDescription: 'Vedo se nei movimenti c\'e qualcosa di buona o solo caos.',
  },
  {
    id: 'warning-recurring-risk',
    type: 'warning',
    focusHint: 'Segnala una spesa ricorrente, un pattern ripetuto o una disattenzione che va tagliata.',
    loadingTitle: 'Sto stanando la roba che ti rosicchia il conto',
    loadingDescription: 'Passo al setaccio i pattern ripetuti prima che il budget faccia una brutta fine.',
  },
];

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
  const didLoadInitialWeeklyDataRef = useRef(false);

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
  const [insightPopups, setInsightPopups] = useState<InsightPopupItem[]>([]);
  const latestInsightPopupsRef = useRef<InsightPopupItem[]>(insightPopups);
  const insightRequestVersionRef = useRef<Record<string, number>>(
    Object.fromEntries(INSIGHT_PLANS.map((plan) => [plan.id, 0])),
  );

  const buildLoadingInsight = (plan: InsightPlan): InsightPopupItem => ({
    planId: plan.id,
    type: plan.type,
    title: plan.loadingTitle,
    description: plan.loadingDescription,
    timestamp: null,
    status: 'loading',
  });

  const buildErrorInsight = (plan: InsightPlan, error: unknown): InsightPopupItem => ({
    planId: plan.id,
    type: plan.type,
    title: plan.type === 'warning' ? 'Insight inceppato' : 'Insight saltato per aria',
    description:
      error instanceof Error
        ? error.message
        : 'La generazione si e\' impiantata. Schiaccia la X e lo rigenero.',
    timestamp: new Date(),
    status: 'error',
  });

  const invalidateInsightRequests = () => {
    INSIGHT_PLANS.forEach((plan) => {
      insightRequestVersionRef.current[plan.id] = (insightRequestVersionRef.current[plan.id] ?? 0) + 1;
    });
  };

  const replaceAllInsights = (nextInsights: InsightPopupItem[]) => {
    latestInsightPopupsRef.current = nextInsights;
    setInsightPopups(nextInsights);
  };

  const replaceInsightSlot = (planId: string, nextInsight: InsightPopupItem) => {
    setInsightPopups((prev) => {
      const next = prev.map((item) => (item.planId === planId ? nextInsight : item));
      latestInsightPopupsRef.current = next;
      return next;
    });
  };

  const handleSessionError = (error: unknown) => {
    if (isAuthError(error)) {
      onSignOut();
      return true;
    }
    return false;
  };

  const loadProfile = async () => {
    try {
      const profile = await fetchUtente();
      setUtenteProfile(profile);
    } catch (error) {
      handleSessionError(error);
    }
  };

  const loadWeeklyOverview = async (startDate: Date = weeklyStartDate) => {
    try {
      const response = await fetchSpeseSettimanali(startDate);
      setWeeklyData(response.weeks);
    } catch (error) {
      handleSessionError(error);
    }
  };

  const generateInsightForPlan = async (plan: InsightPlan, options?: { setLoading?: boolean }) => {
    const requestVersion = (insightRequestVersionRef.current[plan.id] ?? 0) + 1;
    insightRequestVersionRef.current[plan.id] = requestVersion;

    if (options?.setLoading ?? true) {
      replaceInsightSlot(plan.id, buildLoadingInsight(plan));
    }

    const existingTitles = latestInsightPopupsRef.current
      .filter((item) => item.planId !== plan.id && item.type === plan.type && item.status === 'ready')
      .map((item) => item.title);

    try {
      const insight = await generateSingleInsight({
        type: plan.type,
        focus_hint: plan.focusHint,
        existing_titles: existingTitles,
      });

      if (insightRequestVersionRef.current[plan.id] !== requestVersion) {
        return;
      }

      replaceInsightSlot(plan.id, {
        planId: plan.id,
        type: insight.type,
        title: insight.title,
        description: insight.description,
        timestamp: new Date(insight.timestamp),
        status: 'ready',
      });
    } catch (error) {
      if (handleSessionError(error)) {
        return;
      }

      if (insightRequestVersionRef.current[plan.id] !== requestVersion) {
        return;
      }

      replaceInsightSlot(plan.id, buildErrorInsight(plan, error));
    }
  };

  const refreshAllInsights = async () => {
    invalidateInsightRequests();

    try {
      const status = await fetchInsightsStatus();
      if (!status.has_recent_records) {
        replaceAllInsights([]);
        return;
      }
    } catch (error) {
      if (handleSessionError(error)) {
        return;
      }

      replaceAllInsights(INSIGHT_PLANS.map((plan) => buildErrorInsight(plan, error)));
      return;
    }

    const loadingInsights = INSIGHT_PLANS.map((plan) => buildLoadingInsight(plan));
    replaceAllInsights(loadingInsights);

    void Promise.allSettled(
      INSIGHT_PLANS.map((plan) => generateInsightForPlan(plan, { setLoading: false })),
    );
  };

  const refreshDashboardState = async (options?: { refreshInsights?: boolean }) => {
    await Promise.allSettled([
      loadProfile(),
      loadWeeklyOverview(),
    ]);

    if (options?.refreshInsights ?? true) {
      await refreshAllInsights();
    }
  };

  useEffect(() => {
    void refreshDashboardState();

    return () => {
      invalidateInsightRequests();
    };
  }, []);

  useEffect(() => {
    if (!didLoadInitialWeeklyDataRef.current) {
      didLoadInitialWeeklyDataRef.current = true;
      return;
    }

    void loadWeeklyOverview(weeklyStartDate);
  }, [weeklyStartDate]);

  useEffect(() => {
    latestInsightPopupsRef.current = insightPopups;
  }, [insightPopups]);

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
  const fallbackDisponibileMensile = stipendio === null ? null : Math.round(stipendio * 70) / 100;
  const disponibile = stipendio === null
    ? null
    : (utenteProfile?.disponibile_mensile ?? fallbackDisponibileMensile);
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
      void refreshAllInsights();
    } catch (error) {
      handleSessionError(error);
    }
  };

  const handleSetUserGoal = async (value: string) => {
    try {
      const updated = await updateUtente({ obiettivo: value });
      setUtenteProfile(updated);
      void refreshAllInsights();
    } catch (error) {
      handleSessionError(error);
    }
  };

  const handleDeleteAllTransactions = async () => {
    setIsDeletingAllTransactions(true);

    try {
      await deleteAllTransactions();
      await refreshDashboardState({ refreshInsights: true });
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
          void refreshDashboardState({ refreshInsights: true });
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
    void refreshAllInsights();
  };

  const handleRemoveInsight = (planId: string) => {
    setInsightPopups((prev) => {
      const next = prev.filter((item) => item.planId !== planId);
      latestInsightPopupsRef.current = next;
      return next;
    });
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 text-gray-900 transition-colors dark:bg-slate-950 dark:text-slate-100">
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
        onDeleteAllTransactions={handleDeleteAllTransactions}
        isDeletingAllTransactions={isDeletingAllTransactions}
        themeMode={themeMode}
        onThemeChange={setThemeMode}
      />

      <div className="relative flex min-h-0 flex-1 min-w-0 overflow-hidden">
        <button
          onClick={() => setShowSidebar(true)}
          className="fixed left-4 top-4 z-30 rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:text-slate-500 dark:hover:bg-slate-900 dark:hover:text-slate-200"
          aria-label="Apri menu"
        >
          <Menu className="h-6 w-6" />
        </button>

        <div className="pointer-events-none fixed left-1/2 top-2 z-30 flex -translate-x-1/2 items-center gap-2 md:top-3">
          <img src="/logo.png" alt="Aurora" className="h-12 object-contain sm:h-14 md:h-16" />
        </div>

        <div className="fixed right-3 top-4 z-30 w-[min(22rem,calc(100vw-1.5rem))] md:right-4">
          <div className="flex items-center justify-between gap-3 rounded-[1.6rem] border border-white/70 bg-white/90 px-4 py-3 shadow-lg backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-orange-500">Sessione</p>
              <p className="truncate text-sm text-slate-700 dark:text-slate-200">
                {session.user.nome} {session.user.cognome}
              </p>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={handleNewConversation}
                className="flex items-center gap-2 rounded-full px-3 py-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
              >
                <PlusCircle className="h-5 w-5" />
                <span className="hidden text-sm font-medium md:inline">Nuova conversazione</span>
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
        </div>

        <div className="mx-auto flex h-full min-h-0 w-full max-w-5xl flex-col px-4 pb-6 pt-28 md:pt-32">
          <ChatArea messages={messages} onSuggestionClick={handleSuggestionClick} />

          <div className="mt-4">
            <div className="mx-auto w-full max-w-5xl">
              <InputArea onSendMessage={handleSendMessage} disabled={isStreaming} />
            </div>
          </div>

          <div className="mt-6">
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
        onTransactionsChanged={() => refreshDashboardState({ refreshInsights: true })}
      />

      <InsightPopups
        insights={insightPopups}
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
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-600">Aurora</p>
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
