const API_BASE = '/api';
const AUTH_STORAGE_KEY = 'punkagent-auth-session';

const SUPPORTED_MIME_TYPES = new Set([
  'application/pdf',
  'image/gif',
  'image/jpeg',
  'image/png',
  'image/webp',
]);

export interface ApiAttachment {
  filename: string;
  mime_type: string;
  base64_data: string;
}

export interface AuthUser {
  id: number;
  email: string;
  nome: string;
  cognome: string;
  eta: number;
}

export interface AuthSession {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface SignupPayload {
  email: string;
  nome: string;
  cognome: string;
  eta: number;
  password: string;
}

export interface SigninPayload {
  email: string;
  password: string;
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

export interface StatementBulkDeleteResponse {
  deleted: boolean;
  deleted_count: number;
}

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

export function getStoredAuthSession(): AuthSession | null {
  if (!isBrowser()) {
    return null;
  }

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as AuthSession;
    if (parsed?.access_token && parsed?.user) {
      return parsed;
    }
  } catch {
    // ignora sessione corrotta
  }

  return null;
}

export function storeAuthSession(session: AuthSession): void {
  if (!isBrowser()) {
    return;
  }
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

export function clearStoredAuthSession(): void {
  if (!isBrowser()) {
    return;
  }
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

function buildAuthHeaders(headers?: HeadersInit, options: { json?: boolean } = {}): Headers {
  const { json = false } = options;
  const merged = new Headers(headers);
  if (json && !merged.has('Content-Type')) {
    merged.set('Content-Type', 'application/json');
  }

  const session = getStoredAuthSession();
  if (session?.access_token) {
    merged.set('Authorization', `Bearer ${session.access_token}`);
  }

  return merged;
}

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string | Array<{ msg?: string; loc?: unknown[] }> };
    if (typeof payload.detail === 'string' && payload.detail.trim()) {
      return payload.detail;
    }
    if (Array.isArray(payload.detail) && payload.detail.length > 0) {
      return payload.detail
        .map((e) => e.msg ?? JSON.stringify(e))
        .join('; ');
    }
  } catch {
    // ignora body non JSON
  }
  return fallback;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: buildAuthHeaders(init?.headers),
  });
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, `${init?.method ?? 'GET'} ${path}: ${response.status}`));
  }
  return response.json() as Promise<T>;
}

function formatLocalDateForApi(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export async function signup(payload: SignupPayload): Promise<AuthSession> {
  return apiJson<AuthSession>('/auth/signup', {
    method: 'POST',
    headers: buildAuthHeaders(undefined, { json: true }),
    body: JSON.stringify(payload),
  });
}

export async function signin(payload: SigninPayload): Promise<AuthSession> {
  return apiJson<AuthSession>('/auth/signin', {
    method: 'POST',
    headers: buildAuthHeaders(undefined, { json: true }),
    body: JSON.stringify(payload),
  });
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return apiJson<AuthUser>('/auth/me');
}

export async function fetchUtente(): Promise<UtenteProfile> {
  return apiJson<UtenteProfile>('/utente');
}

export async function updateUtente(
  data: Partial<Pick<UtenteProfile, 'stipendio_mensile' | 'obiettivo'>>,
): Promise<UtenteProfile> {
  return apiJson<UtenteProfile>('/utente', {
    method: 'PATCH',
    headers: buildAuthHeaders(undefined, { json: true }),
    body: JSON.stringify(data),
  });
}

export async function fetchSpeseSettimanali(startDate?: Date): Promise<SpeseSettimanaliResponse> {
  let url = '/spese-settimanali';
  if (startDate) {
    url += `?start_date=${formatLocalDateForApi(startDate)}`;
  }
  return apiJson<SpeseSettimanaliResponse>(url);
}

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
  return apiJson<StatementPageResponse>(`/estratto-conto${suffix ? `?${suffix}` : ''}`);
}

export async function createStatementTransaction(
  payload: StatementTransactionPayload,
): Promise<StatementTransaction> {
  return apiJson<StatementTransaction>('/estratto-conto/movimenti', {
    method: 'POST',
    headers: buildAuthHeaders(undefined, { json: true }),
    body: JSON.stringify(payload),
  });
}

export async function updateStatementTransaction(
  movementId: string,
  payload: StatementTransactionPayload,
): Promise<StatementTransaction> {
  return apiJson<StatementTransaction>(`/estratto-conto/movimenti/${movementId}`, {
    method: 'PUT',
    headers: buildAuthHeaders(undefined, { json: true }),
    body: JSON.stringify(payload),
  });
}

export async function deleteStatementTransaction(movementId: string): Promise<void> {
  const response = await apiFetch(`/estratto-conto/movimenti/${movementId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, `DELETE /estratto-conto/movimenti/${movementId}: ${response.status}`));
  }
}

export async function deleteAllTransactions(): Promise<StatementBulkDeleteResponse> {
  return apiJson<StatementBulkDeleteResponse>('/estratto-conto/movimenti', {
    method: 'DELETE',
  });
}

export async function generateInsights(): Promise<InsightsResponse> {
  return apiJson<InsightsResponse>('/insights/generate', {
    method: 'POST',
  });
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(',')[1]);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export async function filesToAttachments(files: File[]): Promise<ApiAttachment[]> {
  const supported = files.filter((file) => SUPPORTED_MIME_TYPES.has(file.type));
  return Promise.all(
    supported.map(async (file) => ({
      filename: file.name,
      mime_type: file.type,
      base64_data: await readFileAsBase64(file),
    })),
  );
}

export async function streamChat(
  message: string,
  conversation: Record<string, unknown>[],
  attachments: ApiAttachment[],
  frontendContext: FrontendContext | null,
  onReasoning: (chunk: string) => void,
  onAnswer: (chunk: string) => void,
  onDone: (finalAnswer: string, updatedConversation: Record<string, unknown>[], reload: boolean) => void,
  onError: (error: string) => void,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: buildAuthHeaders(undefined, { json: true }),
      body: JSON.stringify({
        message,
        conversation,
        attachments,
        frontend_context: frontendContext ?? undefined,
      }),
    });
  } catch (error) {
    onError(String(error));
    return;
  }

  if (!response.ok) {
    onError(await readErrorDetail(response, `POST /chat/stream: ${response.status}`));
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    onError('Streaming non disponibile.');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() ?? '';

      for (const block of blocks) {
        if (!block.trim()) {
          continue;
        }

        let eventType = 'message';
        let dataStr = '';

        for (const line of block.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          }
          if (line.startsWith('data: ')) {
            dataStr = line.slice(6).trim();
          }
        }

        if (!dataStr) {
          continue;
        }

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
            Boolean(payload.reload),
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
