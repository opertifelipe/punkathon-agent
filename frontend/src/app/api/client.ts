const API_BASE = '/api';

// MIME type supportati dal backend
const SUPPORTED_MIME_TYPES = new Set([
  'application/pdf',
  'image/gif',
  'image/jpeg',
  'image/png',
  'image/webp',
]);

// ---------------------------------------------------------------------------
// Tipi
// ---------------------------------------------------------------------------

export interface ApiAttachment {
  filename: string;
  mime_type: string;
  base64_data: string; // base64 puro, senza prefisso "data:..."
}

export interface UtenteProfile {
  stipendio_mensile: number | null;
  spese_fisse_essenziali_mensili: number | null;
  disponibile_mensile: number | null;
  obiettivo: string | null;
  risparmio_mensile: number | null;
}

export interface WeekData {
  start: string;
  end: string;
  total: number;
}

export interface SpeseSettimanaliResponse {
  weeks: WeekData[];
}

export interface FrontendWeekBox {
  index: number;
  label: string;
  start: string;
  end: string;
  total: number;
  contains_today: boolean;
}

export interface FrontendWeeklyOverview {
  month_start: string;
  month_label: string;
  default_week_index: number | null;
  weeks: FrontendWeekBox[];
}

export interface FrontendContext {
  weekly_overview?: FrontendWeeklyOverview;
}

export interface GeneratedInsight {
  id: string;
  type: 'warning' | 'success';
  title: string;
  description: string;
  timestamp: string;
}

export interface InsightsResponse {
  generated_at: string;
  window_start: string;
  window_end: string;
  insights: GeneratedInsight[];
}

export interface StatementWeekOption {
  index: number;
  label: string;
  start: string;
  end: string;
  total: number;
  contains_today: boolean;
}

export interface StatementFilters {
  selected_year: number;
  selected_month: number;
  selected_week: number;
  month_label: string;
  period_start: string;
  period_end: string;
  available_years: number[];
  weeks: StatementWeekOption[];
}

export interface StatementClassificationSchema {
  macrocategorie: string[];
  categorie: string[];
  mappa_categoria_macrocategoria: Record<string, string>;
}

export interface StatementTransaction {
  id: string;
  data: string;
  descrizione: string;
  note: string | null;
  importo: number;
  macrocategoria: string | null;
  categoria: string | null;
}

export interface StatementPageResponse {
  filters: StatementFilters;
  classification_schema: StatementClassificationSchema;
  transactions: StatementTransaction[];
  total_transactions: number;
}

export interface StatementTransactionPayload {
  data: string;
  descrizione: string;
  note?: string | null;
  importo: number;
  macrocategoria: string;
  categoria: string;
}

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string };
    if (typeof payload.detail === 'string' && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    // ignora body non JSON
  }
  return fallback;
}

function formatLocalDateForApi(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// ---------------------------------------------------------------------------
// Utente
// ---------------------------------------------------------------------------

export async function fetchUtente(): Promise<UtenteProfile> {
  const res = await fetch(`${API_BASE}/utente`);
  if (!res.ok) throw new Error(`GET /utente: ${res.status}`);
  return res.json();
}

export async function updateUtente(
  data: Partial<Pick<UtenteProfile, 'stipendio_mensile' | 'obiettivo'>>,
): Promise<UtenteProfile> {
  const res = await fetch(`${API_BASE}/utente`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`PATCH /utente: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Spese settimanali
// ---------------------------------------------------------------------------

export async function fetchSpeseSettimanali(startDate?: Date): Promise<SpeseSettimanaliResponse> {
  let url = `${API_BASE}/spese-settimanali`;
  if (startDate) {
    const iso = formatLocalDateForApi(startDate);
    url += `?start_date=${iso}`;
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET /spese-settimanali: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Estratto conto
// ---------------------------------------------------------------------------

export async function fetchStatementPage(filters?: {
  year?: number;
  month?: number;
  week?: number;
}): Promise<StatementPageResponse> {
  const params = new URLSearchParams();
  if (filters?.year) params.set('year', String(filters.year));
  if (filters?.month) params.set('month', String(filters.month));
  if (filters?.week) params.set('week', String(filters.week));

  const suffix = params.toString();
  const url = `${API_BASE}/estratto-conto${suffix ? `?${suffix}` : ''}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, `GET /estratto-conto: ${res.status}`));
  }
  return res.json();
}

export async function createStatementTransaction(
  payload: StatementTransactionPayload,
): Promise<StatementTransaction> {
  const res = await fetch(`${API_BASE}/estratto-conto/movimenti`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, `POST /estratto-conto/movimenti: ${res.status}`));
  }
  return res.json();
}

export async function updateStatementTransaction(
  movementId: string,
  payload: StatementTransactionPayload,
): Promise<StatementTransaction> {
  const res = await fetch(`${API_BASE}/estratto-conto/movimenti/${movementId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, `PUT /estratto-conto/movimenti/${movementId}: ${res.status}`));
  }
  return res.json();
}

export async function deleteStatementTransaction(movementId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/estratto-conto/movimenti/${movementId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, `DELETE /estratto-conto/movimenti/${movementId}: ${res.status}`));
  }
}

// ---------------------------------------------------------------------------
// Insights AI
// ---------------------------------------------------------------------------

export async function generateInsights(): Promise<InsightsResponse> {
  const res = await fetch(`${API_BASE}/insights/generate`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, `POST /insights/generate: ${res.status}`));
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Conversione File → ApiAttachment
// ---------------------------------------------------------------------------

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // rimuove il prefisso "data:<mime>;base64,"
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export async function filesToAttachments(files: File[]): Promise<ApiAttachment[]> {
  const supported = files.filter((f) => SUPPORTED_MIME_TYPES.has(f.type));
  return Promise.all(
    supported.map(async (file) => ({
      filename: file.name,
      mime_type: file.type,
      base64_data: await readFileAsBase64(file),
    })),
  );
}

// ---------------------------------------------------------------------------
// Chat streaming
// ---------------------------------------------------------------------------

export async function streamChat(
  message: string,
  conversation: Record<string, unknown>[],
  attachments: ApiAttachment[],
  frontendContext: FrontendContext | null,
  onReasoning: (chunk: string) => void,
  onAnswer: (chunk: string) => void,
  onDone: (finalAnswer: string, updatedConversation: Record<string, unknown>[]) => void,
  onError: (error: string) => void,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        conversation,
        attachments,
        frontend_context: frontendContext ?? undefined,
      }),
    });
  } catch (err) {
    onError(String(err));
    return;
  }

  if (!response.ok) {
    onError(`HTTP ${response.status}`);
    return;
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() ?? '';

      for (const block of blocks) {
        if (!block.trim()) continue;

        let eventType = 'message';
        let dataStr = '';

        for (const line of block.split('\n')) {
          if (line.startsWith('event: ')) eventType = line.slice(7).trim();
          if (line.startsWith('data: ')) dataStr = line.slice(6).trim();
        }

        if (!dataStr) continue;

        let payload: Record<string, unknown>;
        try {
          payload = JSON.parse(dataStr);
        } catch {
          continue;
        }

        if (eventType === 'reasoning') {
          onReasoning((payload.content as string) ?? '');
        } else if (eventType === 'answer') {
          onAnswer((payload.content as string) ?? '');
        } else if (eventType === 'done') {
          onDone(
            (payload.answer as string) ?? '',
            (payload.conversation as Record<string, unknown>[]) ?? [],
          );
        } else if (eventType === 'error') {
          onError((payload.content as string) ?? 'Errore sconosciuto');
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
