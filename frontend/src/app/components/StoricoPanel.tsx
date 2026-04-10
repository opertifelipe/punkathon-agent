import { useEffect, useState } from 'react';
import {
  ArrowLeft,
  CalendarRange,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import {
  createStatementTransaction,
  deleteStatementTransaction,
  fetchStatementPage,
  StatementClassificationSchema,
  StatementPageResponse,
  StatementTransaction,
  StatementTransactionPayload,
  updateStatementTransaction,
} from '../api/client';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from './ui/table';

interface StoricoPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

interface TransactionFormState {
  data: string;
  descrizione: string;
  note: string;
  importo: string;
  macrocategoria: string;
  categoria: string;
}

const MESI = [
  'Gennaio',
  'Febbraio',
  'Marzo',
  'Aprile',
  'Maggio',
  'Giugno',
  'Luglio',
  'Agosto',
  'Settembre',
  'Ottobre',
  'Novembre',
  'Dicembre',
];

function formatDate(dateString: string): string {
  const date = new Date(`${dateString}T00:00:00`);
  return date.toLocaleDateString('it-IT', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

function formatShortDate(dateString: string): string {
  const date = new Date(`${dateString}T00:00:00`);
  return date.toLocaleDateString('it-IT', {
    day: 'numeric',
    month: 'short',
  });
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('it-IT', {
    style: 'currency',
    currency: 'EUR',
  }).format(value);
}

function categoriesForMacro(
  schema: StatementClassificationSchema | null,
  macrocategoria: string,
): string[] {
  if (!schema) {
    return [];
  }
  return schema.categorie.filter(
    (categoria) => schema.mappa_categoria_macrocategoria[categoria] === macrocategoria,
  );
}

function buildInitialFormState(
  schema: StatementClassificationSchema | null,
  fallbackDate: string,
  transaction?: StatementTransaction | null,
): TransactionFormState {
  if (!schema) {
    return {
      data: transaction?.data ?? fallbackDate,
      descrizione: transaction?.descrizione ?? '',
      note: transaction?.note ?? '',
      importo: transaction ? String(transaction.importo) : '',
      macrocategoria: transaction?.macrocategoria ?? '',
      categoria: transaction?.categoria ?? '',
    };
  }

  const defaultMacro =
    transaction?.macrocategoria ??
    (transaction?.categoria
      ? schema.mappa_categoria_macrocategoria[transaction.categoria]
      : schema.macrocategorie[0]) ??
    '';
  const defaultCategories = categoriesForMacro(schema, defaultMacro);
  const defaultCategory = transaction?.categoria ?? defaultCategories[0] ?? schema.categorie[0] ?? '';
  const resolvedMacro = schema.mappa_categoria_macrocategoria[defaultCategory] ?? defaultMacro;

  return {
    data: transaction?.data ?? fallbackDate,
    descrizione: transaction?.descrizione ?? '',
    note: transaction?.note ?? '',
    importo: transaction ? String(transaction.importo) : '',
    macrocategoria: resolvedMacro,
    categoria: defaultCategory,
  };
}

export function StoricoPanel({ isOpen, onClose }: StoricoPanelProps) {
  const [pageData, setPageData] = useState<StatementPageResponse | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<StatementTransaction | null>(null);
  const [formState, setFormState] = useState<TransactionFormState>({
    data: '',
    descrizione: '',
    note: '',
    importo: '',
    macrocategoria: '',
    categoria: '',
  });

  const classificationSchema = pageData?.classification_schema ?? null;
  const availableCategories = categoriesForMacro(classificationSchema, formState.macrocategoria);
  const allCategories = classificationSchema?.categorie ?? [];

  const loadStatementPage = async (filters?: {
    year?: number;
    month?: number;
    week?: number;
  }) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetchStatementPage(filters);
      setPageData(response);
      setSelectedYear(response.filters.selected_year);
      setSelectedMonth(response.filters.selected_month);
      setSelectedWeek(response.filters.selected_week);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Impossibile caricare l'estratto conto.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    void loadStatementPage(
      selectedYear && selectedMonth && selectedWeek
        ? { year: selectedYear, month: selectedMonth, week: selectedWeek }
        : undefined,
    );
  }, [isOpen]);

  const refreshCurrentView = async () => {
    await loadStatementPage(
      selectedYear && selectedMonth && selectedWeek
        ? { year: selectedYear, month: selectedMonth, week: selectedWeek }
        : undefined,
    );
  };

  const openCreateDialog = () => {
    const fallbackDate = pageData?.filters.period_start ?? new Date().toISOString().slice(0, 10);
    setEditingTransaction(null);
    setFormError(null);
    setFormState(buildInitialFormState(classificationSchema, fallbackDate, null));
    setIsDialogOpen(true);
  };

  const openEditDialog = (transaction: StatementTransaction) => {
    setEditingTransaction(transaction);
    setFormError(null);
    setFormState(
      buildInitialFormState(
        classificationSchema,
        transaction.data,
        transaction,
      ),
    );
    setIsDialogOpen(true);
  };

  const handleMacroChange = (value: string) => {
    const nextCategories = categoriesForMacro(classificationSchema, value);
    setFormState((current) => ({
      ...current,
      macrocategoria: value,
      categoria: nextCategories.includes(current.categoria) ? current.categoria : (nextCategories[0] ?? ''),
    }));
  };

  const handleCategoryChange = (value: string) => {
    const nextMacro = classificationSchema?.mappa_categoria_macrocategoria[value] ?? formState.macrocategoria;
    setFormState((current) => ({
      ...current,
      categoria: value,
      macrocategoria: nextMacro,
    }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const importo = Number(formState.importo);
    if (!formState.data || !formState.descrizione.trim() || !formState.categoria || !formState.macrocategoria) {
      setFormError('Compila tutti i campi obbligatori prima di salvare.');
      return;
    }
    if (Number.isNaN(importo) || importo === 0) {
      setFormError('Inserisci un importo valido diverso da zero.');
      return;
    }

    const payload: StatementTransactionPayload = {
      data: formState.data,
      descrizione: formState.descrizione.trim(),
      note: formState.note.trim() || null,
      importo,
      macrocategoria: formState.macrocategoria,
      categoria: formState.categoria,
    };

    setIsSaving(true);
    setFormError(null);

    try {
      if (editingTransaction) {
        await updateStatementTransaction(editingTransaction.id, payload);
      } else {
        await createStatementTransaction(payload);
      }
      setIsDialogOpen(false);
      await refreshCurrentView();
    } catch (saveError) {
      setFormError(saveError instanceof Error ? saveError.message : 'Salvataggio non riuscito.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (transaction: StatementTransaction) => {
    if (!window.confirm(`Vuoi davvero cancellare "${transaction.descrizione}"?`)) {
      return;
    }

    setPendingDeleteId(transaction.id);
    setError(null);

    try {
      await deleteStatementTransaction(transaction.id);
      await refreshCurrentView();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Cancellazione non riuscita.');
    } finally {
      setPendingDeleteId(null);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 bg-gray-50 dark:bg-slate-950">
      <div className="flex h-screen flex-col">
        <div className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm dark:border-slate-800 dark:bg-slate-950 dark:shadow-none">
          <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <button
                onClick={onClose}
                className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-slate-500 dark:hover:bg-slate-900 dark:hover:text-slate-200"
                aria-label="Torna alla chat"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-slate-100">Estratto conto</h2>
                <p className="text-sm text-gray-500 dark:text-slate-400">
                  Modifica, cancella o aggiungi manualmente le operazioni del conto.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => void refreshCurrentView()}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                disabled={isLoading}
              >
                {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Aggiorna
              </button>
              <button
                onClick={openCreateDialog}
                disabled={isLoading || !pageData}
                className="inline-flex items-center gap-2 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800 dark:bg-emerald-500/85 dark:text-slate-950 dark:hover:bg-emerald-400"
              >
                <Plus className="h-4 w-4" />
                Nuova transazione
              </button>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
            <div className="grid gap-4 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm lg:grid-cols-[1.2fr_1fr_auto] lg:items-end dark:border-slate-800 dark:bg-slate-900/80 dark:shadow-none">
              <div className="grid gap-4 sm:grid-cols-3">
                <label className="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-slate-300">
                  <span>Anno</span>
                  <Select
                    value={selectedYear ? String(selectedYear) : undefined}
                    onValueChange={(value) => {
                      const nextYear = Number(value);
                      setSelectedYear(nextYear);
                      void loadStatementPage({
                        year: nextYear,
                        month: selectedMonth ?? pageData?.filters.selected_month,
                        week: selectedWeek ?? pageData?.filters.selected_week,
                      });
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleziona anno" />
                    </SelectTrigger>
                    <SelectContent>
                      {(pageData?.filters.available_years ?? []).map((year) => (
                        <SelectItem key={year} value={String(year)}>
                          {year}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </label>

                <label className="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-slate-300">
                  <span>Mese</span>
                  <Select
                    value={selectedMonth ? String(selectedMonth) : undefined}
                    onValueChange={(value) => {
                      const nextMonth = Number(value);
                      setSelectedMonth(nextMonth);
                      void loadStatementPage({
                        year: selectedYear ?? pageData?.filters.selected_year,
                        month: nextMonth,
                        week: selectedWeek ?? pageData?.filters.selected_week,
                      });
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleziona mese" />
                    </SelectTrigger>
                    <SelectContent>
                      {MESI.map((mese, index) => (
                        <SelectItem key={mese} value={String(index + 1)}>
                          {mese}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </label>

                <label className="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-slate-300">
                  <span>Settimana</span>
                  <Select
                    value={selectedWeek ? String(selectedWeek) : undefined}
                    onValueChange={(value) => {
                      const nextWeek = Number(value);
                      setSelectedWeek(nextWeek);
                      void loadStatementPage({
                        year: selectedYear ?? pageData?.filters.selected_year,
                        month: selectedMonth ?? pageData?.filters.selected_month,
                        week: nextWeek,
                      });
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleziona settimana" />
                    </SelectTrigger>
                    <SelectContent>
                      {(pageData?.filters.weeks ?? []).map((week) => (
                        <SelectItem key={week.index} value={String(week.index)}>
                          {week.label} · {formatShortDate(week.start)} - {formatShortDate(week.end)} · {formatCurrency(week.total)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </label>
              </div>

              <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                <div className="flex items-center gap-2 font-medium text-gray-800 dark:text-slate-100">
                  <CalendarRange className="h-4 w-4" />
                  {pageData?.filters.month_label ?? 'Caricamento periodo...'}
                </div>
                <div className="mt-1">
                  Periodo visibile: {pageData?.filters.period_start ? formatDate(pageData.filters.period_start) : '--'} - {pageData?.filters.period_end ? formatDate(pageData.filters.period_end) : '--'}
                </div>
              </div>

              <div className="text-right">
                <div className="text-sm text-gray-500 dark:text-slate-400">Operazioni mostrate</div>
                <div className="text-2xl font-semibold text-gray-900 dark:text-slate-100">{pageData?.total_transactions ?? 0}</div>
              </div>
            </div>

            {error ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            ) : null}

            <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900/80 dark:shadow-none">
              {isLoading && !pageData ? (
                <div className="flex min-h-64 items-center justify-center gap-3 text-sm text-gray-500 dark:text-slate-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Caricamento estratto conto...
                </div>
              ) : pageData && pageData.transactions.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-50/80 hover:bg-gray-50/80 dark:bg-slate-950/70 dark:hover:bg-slate-950/70">
                      <TableHead className="px-4">Data</TableHead>
                      <TableHead className="px-4">Descrizione</TableHead>
                      <TableHead className="px-4">Importo</TableHead>
                      <TableHead className="px-4">Macrocategoria</TableHead>
                      <TableHead className="px-4">Categoria</TableHead>
                      <TableHead className="px-4 text-right">Azioni</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pageData.transactions.map((transaction) => (
                      <TableRow key={transaction.id}>
                        <TableCell className="px-4 font-medium text-gray-700 dark:text-slate-200">
                          {formatDate(transaction.data)}
                        </TableCell>
                        <TableCell className="px-4 align-top">
                          <div className="max-w-md whitespace-normal">
                            <div className="font-medium text-gray-900 dark:text-slate-100">{transaction.descrizione}</div>
                            {transaction.note ? (
                              <div className="mt-1 text-xs leading-5 text-gray-500 dark:text-slate-400">{transaction.note}</div>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="px-4">
                          <span className={`font-semibold ${transaction.importo >= 0 ? 'text-emerald-600 dark:text-emerald-300' : 'text-gray-800 dark:text-slate-100'}`}>
                            {formatCurrency(transaction.importo)}
                          </span>
                        </TableCell>
                        <TableCell className="px-4 text-gray-700 dark:text-slate-300">
                          {transaction.macrocategoria ?? 'Non assegnata'}
                        </TableCell>
                        <TableCell className="px-4 text-gray-700 dark:text-slate-300">
                          {transaction.categoria ?? 'Non assegnata'}
                        </TableCell>
                        <TableCell className="px-4">
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => openEditDialog(transaction)}
                              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-950"
                            >
                              <Pencil className="h-4 w-4" />
                              Modifica
                            </button>
                            <button
                              onClick={() => void handleDelete(transaction)}
                              disabled={pendingDeleteId === transaction.id}
                              className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {pendingDeleteId === transaction.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                              Elimina
                            </button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="flex min-h-72 flex-col items-center justify-center gap-4 px-6 text-center">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Nessuna operazione nel periodo selezionato</h3>
                    <p className="mt-2 text-sm text-gray-500 dark:text-slate-400">
                      Cambia mese, anno o settimana, oppure aggiungi una nuova transazione manuale.
                    </p>
                  </div>
                  <button
                    onClick={openCreateDialog}
                    className="inline-flex items-center gap-2 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800 dark:bg-emerald-500/85 dark:text-slate-950 dark:hover:bg-emerald-400"
                  >
                    <Plus className="h-4 w-4" />
                    Aggiungi transazione
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <Dialog
        open={isDialogOpen}
        onOpenChange={(open) => {
          setIsDialogOpen(open);
          if (!open) {
            setFormError(null);
          }
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingTransaction ? 'Modifica transazione' : 'Nuova transazione'}
            </DialogTitle>
            <DialogDescription>
              Inserisci data, descrizione, nota, importo, macrocategoria e categoria dalle opzioni predefinite.
            </DialogDescription>
          </DialogHeader>

          <form className="grid gap-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-slate-300">
                <span>Data</span>
                <input
                  type="date"
                  value={formState.data}
                  onChange={(event) => setFormState((current) => ({ ...current, data: event.target.value }))}
                  className="h-10 rounded-md border border-gray-200 px-3 text-sm outline-none transition-colors focus:border-gray-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-slate-500"
                  required
                />
              </label>

              <label className="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-slate-300">
                <span>Importo</span>
                <input
                  type="number"
                  step="0.01"
                  value={formState.importo}
                  onChange={(event) => setFormState((current) => ({ ...current, importo: event.target.value }))}
                  className="h-10 rounded-md border border-gray-200 px-3 text-sm outline-none transition-colors focus:border-gray-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-slate-500"
                  placeholder="Usa negativo per una spesa, positivo per un'entrata"
                  required
                />
              </label>
            </div>

            <label className="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-slate-300">
              <span>Descrizione</span>
              <input
                type="text"
                value={formState.descrizione}
                onChange={(event) => setFormState((current) => ({ ...current, descrizione: event.target.value }))}
                className="h-10 rounded-md border border-gray-200 px-3 text-sm outline-none transition-colors focus:border-gray-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-slate-500"
                placeholder="Es: Spesa supermercato"
                required
              />
            </label>

            <label className="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-slate-300">
              <span>Nota</span>
              <textarea
                value={formState.note}
                onChange={(event) => setFormState((current) => ({ ...current, note: event.target.value }))}
                className="min-h-24 rounded-md border border-gray-200 px-3 py-2 text-sm outline-none transition-colors focus:border-gray-400 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-slate-500"
                placeholder="Aggiungi un contesto opzionale"
              />
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-slate-300">
                <span>Macrocategoria</span>
                <Select value={formState.macrocategoria} onValueChange={handleMacroChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Seleziona macrocategoria" />
                  </SelectTrigger>
                  <SelectContent>
                    {(classificationSchema?.macrocategorie ?? []).map((macrocategoria) => (
                      <SelectItem key={macrocategoria} value={macrocategoria}>
                        {macrocategoria}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>

              <label className="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-slate-300">
                <span>Categoria</span>
                <Select value={formState.categoria} onValueChange={handleCategoryChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Seleziona categoria" />
                  </SelectTrigger>
                  <SelectContent>
                    {allCategories.map((categoria) => (
                      <SelectItem key={categoria} value={categoria}>
                        {categoria}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
            </div>

            {formError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {formError}
              </div>
            ) : null}

            <DialogFooter>
              <button
                type="button"
                onClick={() => setIsDialogOpen(false)}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-900"
              >
                Annulla
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-emerald-500/85 dark:text-slate-950 dark:hover:bg-emerald-400"
              >
                {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {editingTransaction ? 'Salva modifiche' : 'Crea transazione'}
              </button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}