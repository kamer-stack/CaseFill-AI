/**
 * API client for CaseFill-AI backend.
 */

const BASE = '';

let authToken: string | null = localStorage.getItem('casefill_token');

export function setAuthToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem('casefill_token', token);
  } else {
    localStorage.removeItem('casefill_token');
  }
}

export function getAuthToken(): string | null {
  return authToken;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || data.error || `HTTP ${res.status}`);
  }
  return data as T;
}

// ─── Auth API ──────────────────────────────────────────────────────────────────

export const authApi = {
  signin: (data: { cnic: string; password: string; expected_account_type?: string }) =>
    request<{ success: boolean; user: any; token: string }>('/api/auth/signin', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  signout: () =>
    request('/api/auth/signout', { method: 'POST' }),

  getMe: () => request<{ user: any }>('/api/auth/me'),
};

// ─── Cases API ─────────────────────────────────────────────────────────────────

export const casesApi = {
  list: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<{ cases: any[] }>(`/api/cases${qs}`);
  },

  create: (submissionSource = 'fso_manual') =>
    request<{ case_id: string; case_number: string }>('/api/cases', {
      method: 'POST',
      body: JSON.stringify({ submission_source: submissionSource }),
    }),

  get: (caseId: string) => request<any>(`/api/cases/${caseId}`),

  uploadDocument: (caseId: string, docType: string, file: File) => {
    const formData = new FormData();
    formData.append('doc_type', docType);
    formData.append('file', file);
    return request<{ doc_type: string; image_url: string }>(
      `/api/cases/${caseId}/documents`,
      { method: 'POST', body: formData }
    );
  },

  extract: (
    caseId: string,
    docType: string,
    targetChildSerial?: number,
    cnicFormat?: 'old' | 'new',
    targetChildRegistrationNumber?: string
  ) =>
    request<{ doc_type: string; extracted: any; model: string; duration_ms: number }>(
      `/api/cases/${caseId}/extract`,
      {
        method: 'POST',
        body: JSON.stringify({
          doc_type: docType,
          target_child_serial_number: targetChildSerial,
          target_child_registration_number: targetChildRegistrationNumber,
          cnic_format: cnicFormat,
        }),
      }
    ),

  updateField: (caseId: string, docType: string, fieldPath: string, newValue: string) =>
    request('/api/cases/' + caseId + '/fields', {
      method: 'PUT',
      body: JSON.stringify({ doc_type: docType, field_path: fieldPath, new_value: newValue }),
    }),

  markNotProvided: (caseId: string, docType: string, reason: string) => {
    const formData = new FormData();
    formData.append('reason', reason);
    return request(`/api/cases/${caseId}/documents/${docType}/not-provided`, {
      method: 'PUT',
      body: formData,
    });
  },

  deleteDocument: (caseId: string, docType: string) =>
    request<{ success: boolean; doc_type: string; status: string }>(
      `/api/cases/${caseId}/documents/${docType}`,
      { method: 'DELETE' }
    ),

  generateLogin: (caseId: string) =>
    request<{
      success: boolean;
      case_number: string;
      username: string;
      password: string;
      generated_at: string;
      reset: boolean;
    }>(`/api/cases/${caseId}/generate-login`, { method: 'POST' }),

  setDonorStatus: (caseId: string, donorArranged: boolean) =>
    request<{ success: boolean; donor_arranged: boolean }>(
      `/api/cases/${caseId}/donor-status`,
      {
        method: 'PATCH',
        body: JSON.stringify({ donor_arranged: donorArranged }),
      }
    ),

  addAidTransfer: (caseId: string, entry: { date: string; amount: number }) =>
    request<{ success: boolean; aid_transfer_log: any[] }>(
      `/api/cases/${caseId}/aid-transfers`,
      {
        method: 'POST',
        body: JSON.stringify(entry),
      }
    ),

  removeAidTransfer: (caseId: string, index: number) =>
    request<{ success: boolean; aid_transfer_log: any[] }>(
      `/api/cases/${caseId}/aid-transfers/${index}`,
      { method: 'DELETE' }
    ),

  crossCheck: (caseId: string) =>
    request<{ checks: any[] }>(`/api/cases/${caseId}/cross-check`, { method: 'POST' }),

  checkDuplicate: (params: { child_crc?: string; mother_cnic?: string; father_cnic?: string; current_case_id?: string }) =>
    request<{ isDuplicate: boolean; matches: any[] }>('/api/cases/check-duplicate', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  submit: (caseId: string, acknowledgment: string) =>
    request<{ success: boolean; case_number: string; status: string; routing: any }>(
      `/api/cases/${caseId}/submit`,
      { method: 'POST', body: JSON.stringify({ acknowledgment, status: 'approved' }) }
    ),

  verify: (caseId: string, status: string, notes?: string, flagReason?: string) =>
    request(`/api/cases/${caseId}/verify`, {
      method: 'PATCH',
      body: JSON.stringify({
        status,
        fso_review_notes: notes || '',
        flag_reason: flagReason || '',
      }),
    }),

  assign: (caseId: string, data: { region_id: string; region_name: string; assigned_fso_id: string; assigned_fso_name: string; admin_notes?: string }) =>
    request(`/api/cases/${caseId}/assign`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  delete: (caseId: string) =>
    request(`/api/cases/${caseId}`, { method: 'DELETE' }),
};

// ─── Admin API ─────────────────────────────────────────────────────────────────

export const adminApi = {
  getRegions: () => request<{ regions: any[] }>('/api/regions'),

  createRegion: (data: any) =>
    request('/api/regions', { method: 'POST', body: JSON.stringify(data) }),

  updateRegion: (regionId: string, data: any) =>
    request(`/api/regions/${regionId}`, { method: 'PUT', body: JSON.stringify(data) }),

  getFsos: () => request<{ fsos: any[] }>('/api/fsos'),

  createFso: (data: any) =>
    request('/api/fsos', { method: 'POST', body: JSON.stringify(data) }),

  updateFso: (fsoId: string, data: any) =>
    request(`/api/fsos/${fsoId}`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteFso: (fsoId: string) =>
    request(`/api/fsos/${fsoId}`, { method: 'DELETE' }),

  updateCredentials: (data: any) =>
    request('/api/admin/credentials', { method: 'PATCH', body: JSON.stringify(data) }),
};

// ─── AI Services API ──────────────────────────────────────────────────────────

export const aiApi = {
  routeRegion: (address: string) =>
    request<any>('/api/route-region', {
      method: 'POST',
      body: JSON.stringify({ address }),
    }),

  helpChat: (data: {
    message: string;
    history?: { role: string; text: string }[];
    current_role?: string;
    current_task?: string;
    task_label?: string;
    active_step?: string;
    case_context?: any;
  }) =>
    request<{ reply: string }>('/api/help-chat', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ─── Stats API ─────────────────────────────────────────────────────────────────

export const statsApi = {
  get: () => request<any>('/api/stats'),
};
