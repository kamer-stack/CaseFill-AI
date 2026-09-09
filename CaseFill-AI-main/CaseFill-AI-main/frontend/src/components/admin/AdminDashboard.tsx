import React, { useState, useEffect } from 'react';
import { AppUser } from '../../types';
import { adminApi, casesApi } from '../../lib/api';
import { ReviewedByNote } from '../shared/ReviewedByNote';
import {
  ShieldCheck,
  Building,
  Users,
  MapPin,
  CheckCircle2,
  AlertCircle,
  Search,
  RefreshCw,
  PlusCircle,
  Edit3,
  X,
  Trash2,
  ChevronDown,
  ChevronUp,
  FileText,
  KeyRound,
  HeartHandshake,
  Save,
  AlertTriangle,
} from 'lucide-react';

interface AdminDashboardProps {
  user: AppUser;
  activeTab: string;
  onTabChange: (tab: string) => void;
  isDualLanguage: boolean;
}

type AdminTab = 'all_cases' | 'unassigned_queue' | 'regions' | 'fsos' | 'admin_profile';

const statusLabel = (s: string, dual: boolean) => {
  const map: Record<string, [string, string]> = {
    draft: ['Draft', 'مسودہ'],
    pending_verification: ['Pending FSO', 'زیرِ جانچ'],
    flagged: ['Flagged', 'نشان زد'],
    verified: ['Verified', 'تصدیق شدہ'],
    rejected: ['Rejected', 'مسترد'],
    unassigned: ['Unassigned', 'غیر مختص'],
  };
  const [en, ur] = map[s] || [s, s];
  return dual ? `${en} / ${ur}` : en;
};

const statusColor = (s: string) => {
  switch (s) {
    case 'pending_verification': return 'bg-blue-50 text-blue-700 border-blue-200';
    case 'verified': return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    case 'flagged': return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'rejected': return 'bg-rose-50 text-rose-700 border-rose-200';
    case 'unassigned': return 'bg-orange-50 text-orange-700 border-orange-200';
    default: return 'bg-slate-50 text-slate-600 border-slate-200';
  }
};

// Average extraction confidence tier: green / yellow / red
const confidencePill = (c: number) =>
  c >= 0.9
    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : c >= 0.7
    ? 'bg-amber-50 text-amber-700 border-amber-200'
    : 'bg-rose-50 text-rose-700 border-rose-200';

const confidenceDotColor = (c: number) =>
  c >= 0.9 ? 'bg-emerald-500' : c >= 0.7 ? 'bg-amber-500' : 'bg-rose-500';

export const AdminDashboard: React.FC<AdminDashboardProps> = ({
  user,
  activeTab: externalTab,
  onTabChange,
  isDualLanguage,
}) => {
  const tab = externalTab as AdminTab;
  const setTab = (t: AdminTab) => onTabChange(t);

  // Data
  const [cases, setCases] = useState<any[]>([]);
  const [regions, setRegions] = useState<any[]>([]);
  const [fsos, setFsos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [regionFilter, setRegionFilter] = useState('all');

  // Assign modal
  const [assignCase, setAssignCase] = useState<any>(null);
  const [assignRegionId, setAssignRegionId] = useState('');
  const [assignFsoId, setAssignFsoId] = useState('');
  const [assignNotes, setAssignNotes] = useState('');
  const [isAssigning, setIsAssigning] = useState(false);

  // Region modal
  const [regionModal, setRegionModal] = useState<any>(null); // null | 'new' | region obj
  const [regionName, setRegionName] = useState('');
  const [regionUrdu, setRegionUrdu] = useState('');
  const [regionFsoId, setRegionFsoId] = useState('');
  const [regionKeywords, setRegionKeywords] = useState('');

  // FSO modal
  const [fsoModal, setFsoModal] = useState<any>(null); // null | 'new' | fso obj
  const [fsoName, setFsoName] = useState('');
  const [fsoCnic, setFsoCnic] = useState('');
  const [fsoPhone, setFsoPhone] = useState('');
  const [fsoEmail, setFsoEmail] = useState('');
  const [fsoRegionId, setFsoRegionId] = useState('');
  const [fsoPassword, setFsoPassword] = useState('password123');
  const [fsoError, setFsoError] = useState<string | null>(null);
  const [isSavingFso, setIsSavingFso] = useState(false);

  // Delete FSO confirm
  const [deleteFso, setDeleteFso] = useState<any>(null);

  // Expanded case detail (reads the same case records — no cached copy)
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);
  const [caseDetail, setCaseDetail] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Admin profile
  const [adminName, setAdminName] = useState(user.name || '');
  const [adminPhone, setAdminPhone] = useState(user.phone || '');
  const [adminEmail, setAdminEmail] = useState(user.email || '');
  const [adminCurrentPw, setAdminCurrentPw] = useState('');
  const [adminNewPw, setAdminNewPw] = useState('');
  const [adminConfirmPw, setAdminConfirmPw] = useState('');
  const [adminSaving, setAdminSaving] = useState(false);
  const [adminMsg, setAdminMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  // ── Load data ────────────────────────────────────────────────────────────
  const loadData = async () => {
    setLoading(true);
    try {
      const [c, r, f] = await Promise.all([
        casesApi.list(),
        adminApi.getRegions(),
        adminApi.getFsos(),
      ]);
      setCases(c.cases || []);
      setRegions(r.regions || []);
      setFsos(f.fsos || []);
    } catch (e) {
      console.error('Admin load error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  // ── Filtered lists ───────────────────────────────────────────────────────
  const unassigned = cases.filter(c => c.status === 'unassigned' || (!c.assigned_fso_id && c.status !== 'verified'));
  const pending = cases.filter(c => c.status === 'pending_verification');
  const flagged = cases.filter(c => c.status === 'flagged');
  const verified = cases.filter(c => c.status === 'verified');

  const filteredCases = cases.filter(c => {
    if (statusFilter !== 'all' && c.status !== statusFilter) return false;
    if (regionFilter !== 'all' && regionFilter !== 'unassigned' && c.region_id !== regionFilter) return false;
    if (regionFilter === 'unassigned' && c.status !== 'unassigned' && c.assigned_fso_id) return false;
    const q = searchQuery.toLowerCase().trim();
    if (q) {
      const compiled = c.compiled_json ? JSON.parse(c.compiled_json) : {};
      const haystack = [
        c.case_number, c.child_crc, c.region_id, c.status,
        c.submitted_by_fso_name, c.assigned_fso_name,
        compiled.childDetails?.name, compiled.fatherDetails?.name,
        compiled.motherDetails?.name, compiled.residentialAddress,
      ].filter(Boolean).join(' ').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleAssign = async () => {
    if (!assignCase || !assignRegionId || !assignFsoId) return;
    setIsAssigning(true);
    try {
      const region = regions.find(r => r.id === assignRegionId);
      const fso = fsos.find(f => f.id === assignFsoId);
      await casesApi.assign(assignCase.id, {
        region_id: assignRegionId,
        region_name: region?.name || '',
        assigned_fso_id: assignFsoId,
        assigned_fso_name: fso?.name || '',
        admin_notes: assignNotes,
      });
      setAssignCase(null);
      await loadData();
    } catch (e: any) {
      alert('Assignment failed: ' + (e.message || e));
    } finally {
      setIsAssigning(false);
    }
  };

  const openRegionModal = (r?: any) => {
    if (r) {
      setRegionModal(r);
      setRegionName(r.name);
      setRegionUrdu(r.urdu_name || '');
      setRegionFsoId(r.assigned_fso_id || '');
      setRegionKeywords(r.keywords ? JSON.parse(r.keywords).join(', ') : '');
    } else {
      setRegionModal('new');
      setRegionName(''); setRegionUrdu(''); setRegionFsoId(''); setRegionKeywords('');
    }
  };

  const saveRegion = async () => {
    if (!regionName.trim()) return;
    const kw = regionKeywords.split(',').map(k => k.trim()).filter(Boolean);
    const payload = {
      name: regionName.trim(),
      urdu_name: regionUrdu.trim() || regionName.trim(),
      assigned_fso_id: regionFsoId || null,
      keywords: kw.length ? kw : [regionName.toLowerCase()],
      active: true,
    };
    try {
      if (regionModal === 'new') {
        await adminApi.createRegion(payload);
      } else {
        await adminApi.updateRegion(regionModal.id, payload);
      }
      setRegionModal(null);
      await loadData();
    } catch (e: any) {
      alert('Region save failed: ' + (e.message || e));
    }
  };

  const openFsoModal = (f?: any) => {
    setFsoError(null);
    if (f) {
      setFsoModal(f);
      setFsoName(f.name); setFsoCnic(f.cnic || ''); setFsoPhone(f.phone || '');
      setFsoEmail(f.email || '');
      const rids = f.assigned_region_ids ? JSON.parse(f.assigned_region_ids) : [];
      setFsoRegionId(rids[0] || '');
      setFsoPassword('');
    } else {
      setFsoModal('new');
      setFsoName(''); setFsoCnic(''); setFsoPhone(''); setFsoEmail('');
      setFsoRegionId(''); setFsoPassword('password123');
    }
  };

  const saveFso = async () => {
    setFsoError(null);
    if (!fsoName.trim()) { setFsoError('Name is required'); return; }
    setIsSavingFso(true);
    try {
      const regionIds = fsoRegionId ? [fsoRegionId] : [];
      if (fsoModal === 'new') {
        const digits = fsoCnic.replace(/\D/g, '');
        if (digits.length !== 13) { setFsoError('CNIC must be 13 digits'); setIsSavingFso(false); return; }
        await adminApi.createFso({
          name: fsoName.trim(), cnic: fsoCnic.trim(),
          phone: fsoPhone.trim(), email: fsoEmail.trim(),
          assigned_region_ids: regionIds,
          badge: `${fsoName.trim()} (${regions.find(r => r.id === fsoRegionId)?.name || 'Field Officer'})`,
          password: fsoPassword || 'password123',
        });
      } else {
        const payload: any = {
          name: fsoName.trim(), phone: fsoPhone.trim(), email: fsoEmail.trim(),
          assigned_region_ids: regionIds,
          badge: `${fsoName.trim()} (${regions.find(r => r.id === fsoRegionId)?.name || 'Field Officer'})`,
        };
        if (fsoPassword.trim()) payload.password = fsoPassword.trim();
        await adminApi.updateFso(fsoModal.id, payload);
      }
      setFsoModal(null);
      await loadData();
    } catch (e: any) {
      setFsoError(e.message || 'Failed to save officer');
    } finally {
      setIsSavingFso(false);
    }
  };

  const confirmDeleteFso = async () => {
    if (!deleteFso) return;
    try {
      await adminApi.deleteFso(deleteFso.id);
      setDeleteFso(null);
      await loadData();
    } catch (e: any) {
      alert('Delete failed: ' + (e.message || e));
    }
  };

  const toggleCaseDetail = async (caseId: string) => {
    if (expandedCaseId === caseId) {
      setExpandedCaseId(null);
      setCaseDetail(null);
      return;
    }
    setLoadingDetail(true);
    setExpandedCaseId(caseId);
    try {
      const detail = await casesApi.get(caseId);
      setCaseDetail(detail);
    } catch {
      setCaseDetail(null);
    }
    setLoadingDetail(false);
  };

  const saveAdminProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdminMsg(null);
    if (adminNewPw && adminNewPw !== adminConfirmPw) {
      setAdminMsg({ type: 'err', text: 'Passwords do not match' }); return;
    }
    if (adminNewPw && adminNewPw.length < 6) {
      setAdminMsg({ type: 'err', text: 'Password must be ≥ 6 characters' }); return;
    }
    setAdminSaving(true);
    try {
      await adminApi.updateCredentials({
        name: adminName.trim(),
        phone: adminPhone.trim(),
        email: adminEmail.trim(),
        currentPassword: adminCurrentPw || undefined,
        newPassword: adminNewPw.trim() || undefined,
      });
      setAdminMsg({ type: 'ok', text: 'Credentials updated successfully' });
      setAdminCurrentPw(''); setAdminNewPw(''); setAdminConfirmPw('');
    } catch (err: any) {
      setAdminMsg({ type: 'err', text: err.message || 'Update failed' });
    } finally {
      setAdminSaving(false);
    }
  };

  // ── Tab definitions ──────────────────────────────────────────────────────
  const tabs: { id: AdminTab; label: string; urdu: string; icon: React.ReactNode; count?: number }[] = [
    { id: 'all_cases', label: 'All Cases', urdu: 'تمام مقدمات', icon: <Search className="w-3.5 h-3.5" />, count: cases.length },
    { id: 'unassigned_queue', label: 'Unassigned', urdu: 'غیر مختص', icon: <AlertCircle className="w-3.5 h-3.5" />, count: unassigned.length },
    { id: 'regions', label: 'Regions', urdu: 'علاقے', icon: <Building className="w-3.5 h-3.5" />, count: regions.length },
    { id: 'fsos', label: 'Officers', urdu: 'افسران', icon: <Users className="w-3.5 h-3.5" />, count: fsos.length },
    { id: 'admin_profile', label: 'Admin', urdu: 'ایڈمن', icon: <ShieldCheck className="w-3.5 h-3.5" /> },
  ];

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* Title Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            Central Program Directorate
          </span>
          <h1 className="text-2xl font-bold text-slate-900 mt-1 tracking-tight">
            Program Control & Cluster Management
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {isDualLanguage ? 'Oversight of multi-region routing, FSO assignments, and intake queues.' : 'Oversight of multi-region routing, FSO assignments, and intake queues.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => openFsoModal()} className="px-3.5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold shadow-md flex items-center gap-1.5">
            <Users className="w-4 h-4 text-purple-300" /> + Provision FSO
          </button>
          <button onClick={() => openRegionModal()} className="px-3.5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold shadow-md flex items-center gap-1.5">
            <PlusCircle className="w-4 h-4" /> Add Cluster
          </button>
          <button onClick={loadData} className="p-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-600" title="Refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { label: 'Total Cases', val: cases.length, color: 'bg-white border-slate-200', action: () => { setTab('all_cases'); setStatusFilter('all'); } },
          { label: 'Unassigned', val: unassigned.length, color: unassigned.length ? 'bg-rose-50 border-rose-300 ring-2 ring-rose-500/20' : 'bg-white border-slate-200', action: () => setTab('unassigned_queue'), textColor: unassigned.length ? 'text-rose-700' : 'text-slate-900' },
          { label: 'Pending FSO', val: pending.length, color: 'bg-white border-slate-200', action: () => { setTab('all_cases'); setStatusFilter('pending_verification'); } },
          { label: 'Flagged', val: flagged.length, color: 'bg-white border-slate-200', action: () => { setTab('all_cases'); setStatusFilter('flagged'); } },
          { label: 'Verified', val: verified.length, color: 'bg-white border-slate-200', action: () => { setTab('all_cases'); setStatusFilter('verified'); } },
        ].map((m, i) => (
          <div key={i} onClick={m.action} className={`p-4 rounded-2xl border shadow-sm cursor-pointer hover:border-slate-300 transition-all ${m.color}`}>
            <span className="text-[11px] uppercase font-bold text-slate-400 block mb-1">{m.label}</span>
            <div className={`text-2xl font-black ${m.textColor || 'text-slate-900'}`}>{m.val}</div>
          </div>
        ))}
      </div>

      {/* Tab Bar */}
      <div className="flex border-b border-slate-200 gap-4 overflow-x-auto">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`pb-3 font-bold text-xs flex items-center gap-2 border-b-2 whitespace-nowrap transition-colors ${
              tab === t.id ? 'border-purple-600 text-purple-700' : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            {t.icon}
            <span>{isDualLanguage ? `${t.label} / ${t.urdu}` : t.label}</span>
            {t.count !== undefined && (
              <span className={`px-2 py-0.5 rounded-full text-[10px] ${
                t.id === 'unassigned_queue' && (t.count ?? 0) > 0 ? 'bg-rose-100 text-rose-800' : 'bg-slate-100 text-slate-700'
              }`}>{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── TAB: All Cases ────────────────────────────────────────────────── */}
      {tab === 'all_cases' && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm flex flex-col md:flex-row items-center gap-3">
            <div className="relative w-full md:w-72">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search cases..."
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
              />
            </div>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
              className="px-3 py-2 text-sm border border-slate-200 rounded-xl bg-white">
              <option value="all">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="pending_verification">Pending</option>
              <option value="flagged">Flagged</option>
              <option value="verified">Verified</option>
              <option value="unassigned">Unassigned</option>
              <option value="rejected">Rejected</option>
            </select>
            <select value={regionFilter} onChange={e => setRegionFilter(e.target.value)}
              className="px-3 py-2 text-sm border border-slate-200 rounded-xl bg-white">
              <option value="all">All Regions</option>
              <option value="unassigned">Unassigned</option>
              {regions.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
            <span className="text-xs text-slate-400 ml-auto">{filteredCases.length} cases</span>
          </div>

          <div className="space-y-2">
            {filteredCases.map(c => (
              <div key={c.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:border-slate-300 transition-colors">
                <div
                  onClick={() => toggleCaseDetail(c.id)}
                  className="p-4 flex items-center justify-between cursor-pointer"
                >
                  <div className="flex items-center gap-4 min-w-0">
                    <div>
                      <div className="font-bold text-sm text-slate-900 flex items-center gap-2">
                        {c.case_number}
                        {expandedCaseId === c.id
                          ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
                          : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        {c.child_crc ? `CRC: ${c.child_crc}` : 'No CRC'}
                        {c.region_id && ` · ${c.region_id}`}
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        Submitted by FSO: <strong className="text-slate-600">{c.submitted_by_fso_name || '—'}</strong>
                        {c.assigned_fso_name && (
                          <> · Assigned to: <strong className="text-slate-600">{c.assigned_fso_name}</strong></>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {c.average_confidence != null && (
                      <span
                        className={`inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full border font-bold ${confidencePill(c.average_confidence)}`}
                        title="Average AI extraction confidence"
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${confidenceDotColor(c.average_confidence)}`} />
                        {Math.round(c.average_confidence * 100)}%
                      </span>
                    )}
                    <span className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${statusColor(c.status)}`}>
                      {statusLabel(c.status, isDualLanguage)}
                    </span>
                    {c.status === 'unassigned' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); setAssignCase(c); setAssignRegionId(''); setAssignFsoId(''); setAssignNotes(''); }}
                        className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold"
                      >
                        Assign
                      </button>
                    )}
                  </div>
                </div>
                {expandedCaseId === c.id && (
                  <div className="border-t border-slate-100 px-4 py-4 bg-slate-50/50">
                    {loadingDetail ? (
                      <div className="flex items-center justify-center py-6">
                        <RefreshCw className="w-5 h-5 text-slate-400 animate-spin" />
                      </div>
                    ) : caseDetail ? (
                      <AdminCaseDetail detail={caseDetail} caseRecord={c} />
                    ) : (
                      <p className="text-sm text-slate-400 text-center py-4">Failed to load case details</p>
                    )}
                  </div>
                )}
              </div>
            ))}
            {filteredCases.length === 0 && (
              <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center animate-fade-in-up">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-50 to-slate-100 border border-purple-100 flex items-center justify-center mx-auto mb-4">
                  <Search className="w-8 h-8 text-purple-400" />
                </div>
                <p className="text-base font-bold text-slate-700">No cases match the current filters</p>
                <p className="text-sm text-slate-400 mt-1 max-w-sm mx-auto">
                  Try clearing the search box or switching the status and region filters above.
                </p>
                <button
                  onClick={() => { setSearchQuery(''); setStatusFilter('all'); setRegionFilter('all'); }}
                  className="mt-5 px-4 py-2 border border-slate-300 text-slate-600 rounded-xl hover:bg-slate-50 transition-colors text-xs font-bold cursor-pointer"
                >
                  Clear All Filters
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB: Unassigned Queue ─────────────────────────────────────────── */}
      {tab === 'unassigned_queue' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900">
              Unassigned Cases {isDualLanguage && <span className="text-slate-400 text-sm font-normal">/ غیر مختص مقدمات</span>}
            </h2>
            <span className="px-3 py-1 rounded-full bg-rose-100 text-rose-700 text-xs font-bold">{unassigned.length} awaiting</span>
          </div>
          {unassigned.length === 0 ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center animate-fade-in-up">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-50 to-slate-100 border border-emerald-100 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-8 h-8 text-emerald-500" />
              </div>
              <p className="text-base font-bold text-slate-700">All cases are assigned!</p>
              <p className="text-sm text-slate-400 mt-1 max-w-sm mx-auto">
                Every submitted case has a region and an officer. New submissions that cannot be auto-routed will appear here.
              </p>
            </div>
          ) : unassigned.map(c => {
            const compiled = c.compiled_json ? JSON.parse(c.compiled_json) : {};
            return (
              <div key={c.id} className="bg-white rounded-xl border border-rose-200 p-4 flex items-center justify-between">
                <div>
                  <div className="font-bold text-sm text-slate-900">{c.case_number}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {compiled.childDetails?.name || 'Unknown child'}
                    {compiled.residentialAddress && ` · ${compiled.residentialAddress.slice(0, 60)}`}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    Routing: {c.routing_reason || 'No address match'}
                    {c.submitted_by_fso_name && ` · Submitted by FSO: ${c.submitted_by_fso_name}`}
                  </div>
                </div>
                <button onClick={() => { setAssignCase(c); setAssignRegionId(''); setAssignFsoId(''); setAssignNotes(''); }}
                  className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold shadow">
                  Assign to FSO
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* ── TAB: Regions ──────────────────────────────────────────────────── */}
      {tab === 'regions' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900">
              Regional Clusters {isDualLanguage && <span className="text-slate-400 text-sm font-normal">/ علاقائی کلسٹر</span>}
            </h2>
            <button onClick={() => openRegionModal()} className="px-3 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold flex items-center gap-1.5">
              <PlusCircle className="w-4 h-4" /> New Cluster
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {regions.map(r => {
              const kw = r.keywords ? JSON.parse(r.keywords) : [];
              return (
                <div key={r.id} className="bg-white rounded-xl border border-slate-200 p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="font-bold text-slate-900">{r.name}</div>
                      {r.urdu_name && <div className="text-sm text-slate-500 font-urdu">{r.urdu_name}</div>}
                    </div>
                    <button onClick={() => openRegionModal(r)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500">
                      <Edit3 className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="mt-2 text-xs text-slate-500">
                    <span className="font-medium">FSO:</span> {r.assigned_fso_id || 'Unassigned'}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {kw.map((k: string, i: number) => (
                      <span key={i} className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-[10px]">{k}</span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          {regions.length === 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center animate-fade-in-up">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-50 to-slate-100 border border-purple-100 flex items-center justify-center mx-auto mb-4">
                <MapPin className="w-8 h-8 text-purple-400" />
              </div>
              <p className="text-base font-bold text-slate-700">No regions configured yet</p>
              <p className="text-sm text-slate-400 mt-1 max-w-sm mx-auto">
                Regional clusters route submitted cases to the right Field Support Officer. Create your first cluster to enable routing.
              </p>
              <button
                onClick={() => openRegionModal()}
                className="mt-5 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-xl shadow-md transition-colors text-xs font-bold flex items-center gap-1.5 mx-auto cursor-pointer"
              >
                <PlusCircle className="w-4 h-4" /> Create First Cluster
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── TAB: FSOs ─────────────────────────────────────────────────────── */}
      {tab === 'fsos' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900">
              Field Officers Roster {isDualLanguage && <span className="text-slate-400 text-sm font-normal">/ فیلڈ افسران</span>}
            </h2>
            <button onClick={() => openFsoModal()} className="px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold flex items-center gap-1.5">
              <PlusCircle className="w-4 h-4" /> Provision FSO
            </button>
          </div>
          <div className="space-y-2">
            {fsos.map(f => {
              const rids = f.assigned_region_ids ? JSON.parse(f.assigned_region_ids) : [];
              return (
                <div key={f.id} className="bg-white rounded-xl border border-slate-200 p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-indigo-100 text-indigo-700 font-bold text-sm flex items-center justify-center">
                      {f.name.charAt(0)}
                    </div>
                    <div>
                      <div className="font-bold text-sm text-slate-900">{f.name}</div>
                      <div className="text-xs text-slate-500">
                        {f.id} · {f.phone || 'No phone'} · {f.email || 'No email'}
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        Regions: {rids.length ? rids.join(', ') : 'None'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => openFsoModal(f)} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500" title="Edit">
                      <Edit3 className="w-4 h-4" />
                    </button>
                    <button onClick={() => setDeleteFso(f)} className="p-2 rounded-lg hover:bg-rose-50 text-rose-500" title="Delete">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
            {fsos.length === 0 && (
              <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center animate-fade-in-up">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-50 to-slate-100 border border-indigo-100 flex items-center justify-center mx-auto mb-4">
                  <Users className="w-8 h-8 text-indigo-400" />
                </div>
                <p className="text-base font-bold text-slate-700">No field officers provisioned yet</p>
                <p className="text-sm text-slate-400 mt-1 max-w-sm mx-auto">
                  FSO accounts can only be created by Central Admin. Provision an officer to start verifying cases in the field.
                </p>
                <button
                  onClick={() => openFsoModal()}
                  className="mt-5 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl shadow-md transition-colors text-xs font-bold flex items-center gap-1.5 mx-auto cursor-pointer"
                >
                  <PlusCircle className="w-4 h-4" /> Provision First Officer
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB: Admin Profile ────────────────────────────────────────────── */}
      {tab === 'admin_profile' && (
        <div className="max-w-xl mx-auto space-y-6">
          <h2 className="text-lg font-bold text-slate-900">
            Admin Credentials {isDualLanguage && <span className="text-slate-400 text-sm font-normal">/ ایڈمن اسناد</span>}
          </h2>
          <form onSubmit={saveAdminProfile} className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Name</label>
              <input value={adminName} onChange={e => setAdminName(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">Phone</label>
                <input value={adminPhone} onChange={e => setAdminPhone(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">Email</label>
                <input value={adminEmail} onChange={e => setAdminEmail(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
              </div>
            </div>
            <hr className="border-slate-100" />
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Current Password (required to change password)</label>
              <input type="password" value={adminCurrentPw} onChange={e => setAdminCurrentPw(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">New Password</label>
                <input type="password" value={adminNewPw} onChange={e => setAdminNewPw(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">Confirm Password</label>
                <input type="password" value={adminConfirmPw} onChange={e => setAdminConfirmPw(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
              </div>
            </div>
            {adminMsg && (
              <div className={`p-3 rounded-xl text-sm font-medium ${adminMsg.type === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                {adminMsg.text}
              </div>
            )}
            <button type="submit" disabled={adminSaving}
              className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold shadow disabled:opacity-50 flex items-center justify-center gap-2">
              <Save className="w-4 h-4" />
              {adminSaving ? 'Saving...' : 'Update Credentials'}
            </button>
          </form>
        </div>
      )}

      {/* ── MODAL: Assign Case ────────────────────────────────────────────── */}
      {assignCase && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900">Assign Case</h3>
              <button onClick={() => setAssignCase(null)} className="p-1 rounded-lg hover:bg-slate-100"><X className="w-5 h-5" /></button>
            </div>
            <p className="text-sm text-slate-600">Assign <strong>{assignCase.case_number}</strong> to a region and officer.</p>
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Region</label>
              <select value={assignRegionId} onChange={e => { setAssignRegionId(e.target.value); setAssignFsoId(''); }}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl">
                <option value="">Select region...</option>
                {regions.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Officer</label>
              <select value={assignFsoId} onChange={e => setAssignFsoId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl">
                <option value="">Select officer...</option>
                {fsos.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Admin Notes (optional)</label>
              <textarea value={assignNotes} onChange={e => setAssignNotes(e.target.value)} rows={2}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl" />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setAssignCase(null)} className="px-4 py-2 rounded-xl border border-slate-200 text-sm font-medium hover:bg-slate-50">Cancel</button>
              <button onClick={handleAssign} disabled={isAssigning || !assignRegionId || !assignFsoId}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold shadow disabled:opacity-50">
                {isAssigning ? 'Assigning...' : 'Confirm Assignment'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Region ─────────────────────────────────────────────────── */}
      {regionModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900">
                {regionModal === 'new' ? 'New Cluster' : 'Edit Cluster'}
              </h3>
              <button onClick={() => setRegionModal(null)} className="p-1 rounded-lg hover:bg-slate-100"><X className="w-5 h-5" /></button>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Name (English)</label>
              <input value={regionName} onChange={e => setRegionName(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Urdu Name</label>
              <input value={regionUrdu} onChange={e => setRegionUrdu(e.target.value)} dir="rtl"
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500 font-urdu" />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Assigned FSO</label>
              <select value={regionFsoId} onChange={e => setRegionFsoId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl">
                <option value="">None</option>
                {fsos.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Keywords (comma-separated)</label>
              <input value={regionKeywords} onChange={e => setRegionKeywords(e.target.value)}
                placeholder="e.g. lahore, model town, wapda town"
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setRegionModal(null)} className="px-4 py-2 rounded-xl border border-slate-200 text-sm font-medium hover:bg-slate-50">Cancel</button>
              <button onClick={saveRegion} disabled={!regionName.trim()}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-sm font-bold shadow disabled:opacity-50">
                Save Cluster
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: FSO Create/Edit ────────────────────────────────────────── */}
      {fsoModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900">
                {fsoModal === 'new' ? 'Provision Officer' : 'Edit Officer'}
              </h3>
              <button onClick={() => setFsoModal(null)} className="p-1 rounded-lg hover:bg-slate-100"><X className="w-5 h-5" /></button>
            </div>
            {fsoError && (
              <div className="p-3 rounded-xl bg-rose-50 text-rose-700 text-sm font-medium flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" /> {fsoError}
              </div>
            )}
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Full Name</label>
              <input value={fsoName} onChange={e => setFsoName(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
            </div>
            {fsoModal === 'new' && (
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">CNIC (XXXXX-XXXXXXX-X)</label>
                <input value={fsoCnic} onChange={e => setFsoCnic(e.target.value)}
                  placeholder="35202-1234567-1"
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">Phone</label>
                <input value={fsoPhone} onChange={e => setFsoPhone(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">Email</label>
                <input value={fsoEmail} onChange={e => setFsoEmail(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">Primary Region</label>
              <select value={fsoRegionId} onChange={e => setFsoRegionId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl">
                <option value="">None</option>
                {regions.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-500 mb-1">
                Password {fsoModal !== 'new' && '(leave blank to keep current)'}
              </label>
              <input type="password" value={fsoPassword} onChange={e => setFsoPassword(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-purple-500" />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setFsoModal(null)} className="px-4 py-2 rounded-xl border border-slate-200 text-sm font-medium hover:bg-slate-50">Cancel</button>
              <button onClick={saveFso} disabled={isSavingFso}
                className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-sm font-bold shadow disabled:opacity-50">
                {isSavingFso ? 'Saving...' : fsoModal === 'new' ? 'Provision Officer' : 'Update Officer'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Delete FSO Confirm ─────────────────────────────────────── */}
      {deleteFso && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900">Deactivate Officer</h3>
                <p className="text-sm text-slate-500">{deleteFso.name} ({deleteFso.id})</p>
              </div>
            </div>
            <p className="text-sm text-slate-600">
              This will deactivate the officer account, remove their login, and unassign their regions. Cases already assigned to them will remain unchanged.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteFso(null)} className="px-4 py-2 rounded-xl border border-slate-200 text-sm font-medium hover:bg-slate-50">Cancel</button>
              <button onClick={confirmDeleteFso}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-sm font-bold shadow">
                Confirm Deactivation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Admin Case Detail (same case records as FSO/child views — no cached copy) ─

function AdminCaseDetail({ detail, caseRecord }: { detail: Record<string, any>; caseRecord: any }) {
  const documents = Object.values(detail.documents || {});
  const compiled = detail.compiled_json ? JSON.parse(detail.compiled_json) : null;
  const donorArranged = !!detail.donor_arranged;
  const aidLog: { date: string; amount: number; recorded_by?: string }[] = Array.isArray(detail.aid_transfer_log)
    ? detail.aid_transfer_log
    : [];

  return (
    <div className="space-y-4">
      {/* Documents */}
      {documents.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {documents.map((doc: any) => (
            <div key={doc.doc_type} className="bg-white rounded-xl border border-slate-200 p-3 text-center">
              <p className="text-xs font-semibold text-slate-700 capitalize mb-1">
                {doc.doc_type.replace(/_/g, ' ')}
              </p>
              {doc.imageUrl ? (
                <img
                  src={doc.imageUrl}
                  alt={doc.doc_type}
                  className="w-full h-20 object-cover rounded-lg border border-slate-100"
                />
              ) : (
                <div className="w-full h-20 bg-slate-100 rounded-lg flex items-center justify-center">
                  <FileText className="w-5 h-5 text-slate-300" />
                </div>
              )}
              <p className="text-[10px] text-slate-400 mt-1">{doc.status}</p>
            </div>
          ))}
        </div>
      )}

      {/* Compiled info */}
      {compiled && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
          {compiled.childDetails?.name && (
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <span className="text-slate-400 block">Child Name</span>
              <span className="font-semibold text-slate-900">{compiled.childDetails.name}</span>
            </div>
          )}
          {compiled.childDetails?.crcOrRegNumber && (
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <span className="text-slate-400 block">CRC / B-Form No.</span>
              <span className="font-semibold text-slate-900">{compiled.childDetails.crcOrRegNumber}</span>
            </div>
          )}
          {compiled.childDetails?.schoolName && (
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <span className="text-slate-400 block">School</span>
              <span className="font-semibold text-slate-900">{compiled.childDetails.schoolName}</span>
            </div>
          )}
          {compiled.fatherDetails?.name && (
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <span className="text-slate-400 block">Father Name</span>
              <span className="font-semibold text-slate-900">{compiled.fatherDetails.name}</span>
            </div>
          )}
          {compiled.motherDetails?.name && (
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <span className="text-slate-400 block">Mother Name</span>
              <span className="font-semibold text-slate-900">{compiled.motherDetails.name}</span>
            </div>
          )}
          {compiled.residentialAddress && (
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <span className="text-slate-400 block">Address</span>
              <span className="font-semibold text-slate-900">{compiled.residentialAddress}</span>
            </div>
          )}
        </div>
      )}

      {/* Attribution & verification */}
      {caseRecord.status === 'verified' && (
        <ReviewedByNote
          name={detail.verified_by_fso_name || caseRecord.verified_by_fso_name || caseRecord.assigned_fso_name}
          date={caseRecord.verified_at || detail.verified_at}
        />
      )}
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-[11px] text-slate-500">
        <span>Submitted by FSO: <strong className="text-slate-700">{caseRecord.submitted_by_fso_name || '—'}</strong></span>
        <span>Assigned to: <strong className="text-slate-700">{caseRecord.assigned_fso_name || '—'}</strong></span>
        {caseRecord.submitted_at && <span>Submitted: {new Date(caseRecord.submitted_at).toLocaleString()}</span>}
        {caseRecord.verified_at && <span>Verified: {new Date(caseRecord.verified_at).toLocaleString()}</span>}
      </div>
      {caseRecord.fso_review_notes && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-xs text-emerald-800">
          <strong>FSO Review Notes:</strong> {caseRecord.fso_review_notes}
        </div>
      )}

      {/* Child login status */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
          <KeyRound className="w-3.5 h-3.5 text-indigo-500" />
          Child Login
        </span>
        {detail.child_username ? (
          <span className="text-xs text-slate-600">
            Generated · <span className="font-mono font-bold text-slate-900">{detail.child_username}</span>
            {detail.child_login_generated_at && (
              <span className="text-slate-400"> ({new Date(detail.child_login_generated_at).toLocaleDateString()})</span>
            )}
          </span>
        ) : (
          <span className="text-xs text-slate-400 italic">Not generated yet (available after verification)</span>
        )}
      </div>

      {/* Donor & aid transfers (maintained by the FSO — same record) */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 space-y-2">
        <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
          <HeartHandshake className="w-3.5 h-3.5 text-emerald-500" />
          Donor & Aid Transfers
        </span>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">Donor arranged:</span>
          <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
            donorArranged
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-slate-50 text-slate-500 border-slate-200'
          }`}>
            {donorArranged ? 'Yes' : 'No'}
          </span>
        </div>
        {aidLog.length > 0 ? (
          <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden">
            <div className="grid grid-cols-3 bg-slate-50 px-3 py-1.5 text-[10px] font-bold uppercase text-slate-400">
              <span>Date</span>
              <span>Amount (PKR)</span>
              <span>Recorded By</span>
            </div>
            {aidLog.map((t, i) => (
              <div key={i} className="grid grid-cols-3 px-3 py-1.5 text-xs bg-white">
                <span className="text-slate-700">{t.date}</span>
                <span className="font-bold text-slate-900">{t.amount.toLocaleString()}</span>
                <span className="text-slate-400">{t.recorded_by || '—'}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400 italic">No aid transfers recorded.</p>
        )}
      </div>
    </div>
  );
}
