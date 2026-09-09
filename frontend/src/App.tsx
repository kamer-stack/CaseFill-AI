import React, { useState, useEffect, useCallback } from 'react';
import { AppUser, UserRole, INITIAL_DOCUMENT_SLOTS, DocumentSlotConfig, CrossCheckResult, DocType } from './types';
import { authApi, casesApi, setAuthToken, getAuthToken } from './lib/api';
import { LandingPage } from './components/public/LandingPage';
import { AuthModal } from './components/public/AuthModal';
import { Header } from './components/shared/Header';
import { HelpChatModal } from './components/shared/HelpChatModal';
import { UploadScreen } from './components/intake/UploadScreen';
import { ReviewScreen } from './components/intake/ReviewScreen';
import { SummaryScreen } from './components/intake/SummaryScreen';
import { FSOQueueScreen } from './components/fso/FSOQueueScreen';
import { FamilyPortal } from './components/family/FamilyPortal';
import { AdminDashboard } from './components/admin/AdminDashboard';
import { Sparkles } from 'lucide-react';

// ── Intake session persistence ──────────────────────────────────────────────
// Survives a browser/tab reload (device sleep, tab discard, accidental
// refresh, etc.) so an in-progress case is resumed instead of lost. Only a
// small pointer is stored here — the actual uploaded files and extracted
// data already live on the backend per case_documents row; on restore we
// refetch the case and rebuild slots/extractedData from that.
const INTAKE_SESSION_KEY = 'casefill_intake_session';

interface PersistedIntakeSession {
  currentTab: 'queue' | 'intake' | 'archive' | 'admin';
  intakeStep: 1 | 2 | 3;
  currentCaseId: string | null;
  targetChildName: string;
  targetChildRegNumber: string;
}

function loadIntakeSession(): PersistedIntakeSession | null {
  try {
    const raw = localStorage.getItem(INTAKE_SESSION_KEY);
    return raw ? (JSON.parse(raw) as PersistedIntakeSession) : null;
  } catch {
    return null;
  }
}

function saveIntakeSession(session: PersistedIntakeSession) {
  try {
    localStorage.setItem(INTAKE_SESSION_KEY, JSON.stringify(session));
  } catch {
    // storage unavailable (private mode, quota) — resume just won't work
  }
}

function clearIntakeSession() {
  try {
    localStorage.removeItem(INTAKE_SESSION_KEY);
  } catch {
    // ignore
  }
}

// Rebuild slots + extractedData for an in-progress case from the backend's
// own record of it, rather than trying to serialize File objects/blobs
// client-side (which can't survive a reload anyway).
function rebuildFromCase(caseRecord: any): { slots: DocumentSlotConfig[]; extractedData: Record<string, any> } {
  const documents = caseRecord.documents || {};
  const extractedData: Record<string, any> = {};

  const slots = INITIAL_DOCUMENT_SLOTS.map((base) => {
    const doc = documents[base.id];
    if (!doc) return { ...base };

    if (doc.extracted_json != null) {
      extractedData[base.id] = doc.extracted_json;
    }

    const status = doc.status as DocumentSlotConfig['status'];
    // In-flight statuses ('uploading' / 'extracting') can't be resumed —
    // the request died with the reload — so treat them as empty again
    // rather than stranding the slot in a spinner state forever.
    const resumedStatus: DocumentSlotConfig['status'] =
      status === 'uploading' || status === 'extracting' ? 'empty' : status || 'empty';

    return {
      ...base,
      status: resumedStatus,
      file: doc.imageUrl ? { name: doc.original_filename || base.title, previewUrl: doc.imageUrl } : undefined,
      notProvidedReason: doc.not_provided_reason || undefined,
      errorMessage: undefined,
    };
  });

  return { slots, extractedData };
}

const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<AppUser | null>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isDualLanguage, setIsDualLanguage] = useState(true);

  // FSO intake state
  const [currentTab, setCurrentTab] = useState<'queue' | 'intake' | 'archive' | 'admin'>('queue');
  const [intakeStep, setIntakeStep] = useState<1 | 2 | 3>(1);
  const [slots, setSlots] = useState<DocumentSlotConfig[]>(INITIAL_DOCUMENT_SLOTS);
  const [extractedData, setExtractedData] = useState<Record<string, any>>({});
  const [crossChecks, setCrossChecks] = useState<CrossCheckResult[]>([]);
  const [reviewedDocs, setReviewedDocs] = useState<Set<DocType>>(new Set());
  const [targetChildName, setTargetChildName] = useState('');
  const [targetChildRegNumber, setTargetChildRegNumber] = useState('');
  const [currentCaseId, setCurrentCaseId] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isTimerRunning, setIsTimerRunning] = useState(false);
  const [isRestoringSession, setIsRestoringSession] = useState(false);

  // Admin tab
  const [adminTab, setAdminTab] = useState<string>('all_cases');

  // Check stored session on mount, then attempt to resume any in-progress
  // intake (see loadIntakeSession/rebuildFromCase above).
  useEffect(() => {
    const token = getAuthToken();
    if (!token) return;

    const persisted = loadIntakeSession();
    if (persisted?.currentTab === 'intake' && persisted.currentCaseId) {
      setIsRestoringSession(true);
    }

    authApi.getMe()
      .then(async ({ user }) => {
        setCurrentUser(user);

        if (persisted?.currentTab === 'intake' && persisted.currentCaseId && (user.role === 'fso' || user.role === 'admin')) {
          try {
            const caseRecord = await casesApi.get(persisted.currentCaseId);
            // Don't resume into a case that's already been submitted/verified —
            // that flow is done; send the FSO back to the queue instead.
            if (caseRecord.status === 'draft') {
              const { slots: rebuiltSlots, extractedData: rebuiltData } = rebuildFromCase(caseRecord);
              setSlots(rebuiltSlots);
              setExtractedData(rebuiltData);
              setCurrentCaseId(persisted.currentCaseId);
              setTargetChildName(persisted.targetChildName || '');
              setTargetChildRegNumber(persisted.targetChildRegNumber || '');
              setCurrentTab('intake');
              setIntakeStep(persisted.intakeStep || 1);
            } else {
              clearIntakeSession();
            }
          } catch {
            // Case no longer fetchable (deleted, network issue) — drop the
            // stale pointer rather than getting stuck retrying it forever.
            clearIntakeSession();
          }
        }
      })
      .catch(() => setAuthToken(null))
      .finally(() => setIsRestoringSession(false));
  }, []);

  // Persist the intake session pointer on every relevant change so a reload
  // can resume it. Only meaningful while actually in the intake flow.
  useEffect(() => {
    if (!currentUser) return;
    if (currentTab === 'intake') {
      saveIntakeSession({ currentTab, intakeStep, currentCaseId, targetChildName, targetChildRegNumber });
    } else {
      clearIntakeSession();
    }
  }, [currentUser, currentTab, intakeStep, currentCaseId, targetChildName, targetChildRegNumber]);

  // Timer
  useEffect(() => {
    if (!isTimerRunning) return;
    const interval = setInterval(() => setElapsedSeconds(s => s + 1), 1000);
    return () => clearInterval(interval);
  }, [isTimerRunning]);

  const handleAuthSuccess = (user: AppUser, token: string) => {
    setAuthToken(token);
    setCurrentUser(user);
    setIsAuthOpen(false);
    if (user.role === 'family') setCurrentTab('queue');
    else if (user.role === 'admin') setCurrentTab('admin');
    else setCurrentTab('queue');
  };

  const handleSignOut = () => {
    authApi.signout().catch(() => {});
    setAuthToken(null);
    setCurrentUser(null);
    setCurrentTab('queue');
    setIntakeStep(1);
    setSlots(INITIAL_DOCUMENT_SLOTS);
    setExtractedData({});
    setCrossChecks([]);
    setCurrentCaseId(null);
    setElapsedSeconds(0);
    setIsTimerRunning(false);
    clearIntakeSession();
  };

  const startIntake = () => {
    setSlots(INITIAL_DOCUMENT_SLOTS);
    setExtractedData({});
    setCrossChecks([]);
    setCurrentCaseId(null);
    setElapsedSeconds(0);
    setIsTimerRunning(false);
    setIntakeStep(1);
    setCurrentTab('intake');
  };

  const currentRole: UserRole = currentUser?.role || 'fso';

  // Public landing page
  if (!currentUser) {
    return (
      <>
        <LandingPage
          onOpenAuth={() => setIsAuthOpen(true)}
          isDualLanguage={isDualLanguage}
          setIsDualLanguage={setIsDualLanguage}
        />
        <AuthModal
          isOpen={isAuthOpen}
          onClose={() => setIsAuthOpen(false)}
          onSuccess={handleAuthSuccess}
          isDualLanguage={isDualLanguage}
        />
      </>
    );
  }

  // Briefly shown only when resuming an in-progress case after a reload,
  // instead of flashing the queue screen before the case data loads.
  if (isRestoringSession) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-500">Resuming your in-progress case...</p>
        </div>
      </div>
    );
  }

  return (
        <div className="min-h-screen bg-brand-surface font-app">
      <Header
        user={currentUser}
        onSignOut={handleSignOut}
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        isDualLanguage={isDualLanguage}
        setIsDualLanguage={setIsDualLanguage}
        intakeStep={intakeStep}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        {currentRole === 'family' ? (
          <FamilyPortal user={currentUser} isDualLanguage={isDualLanguage} />
        ) : currentRole === 'admin' ? (
          <AdminDashboard
            user={currentUser}
            activeTab={adminTab}
            onTabChange={setAdminTab}
            isDualLanguage={isDualLanguage}
          />
        ) : (
          <>
            {currentTab === 'queue' && (
              <FSOQueueScreen
                user={currentUser}
                onStartIntake={startIntake}
                isDualLanguage={isDualLanguage}
              />
            )}
            {currentTab === 'intake' && intakeStep === 1 && (
              <UploadScreen
                slots={slots}
                setSlots={setSlots}
                extractedData={extractedData}
                setExtractedData={setExtractedData}
                caseId={currentCaseId}
                setCaseId={setCurrentCaseId}
                onStartTimer={() => setIsTimerRunning(true)}
                onProceed={() => setIntakeStep(2)}
                isDualLanguage={isDualLanguage}
                targetChildName={targetChildName}
                setTargetChildName={setTargetChildName}
                targetChildRegNumber={targetChildRegNumber}
                setTargetChildRegNumber={setTargetChildRegNumber}
              />
            )}
            {currentTab === 'intake' && intakeStep === 2 && (
              <ReviewScreen
                slots={slots}
                extractedData={extractedData}
                setExtractedData={setExtractedData}
                crossChecks={crossChecks}
                setCrossChecks={setCrossChecks}
                caseId={currentCaseId!}
                onProceed={() => setIntakeStep(3)}
                onBack={() => setIntakeStep(1)}
                isDualLanguage={isDualLanguage}
                reviewedDocs={reviewedDocs}
                setReviewedDocs={setReviewedDocs}
              />
            )}
            {currentTab === 'intake' && intakeStep === 3 && (
              <SummaryScreen
                extractedData={extractedData}
                crossChecks={crossChecks}
                caseId={currentCaseId!}
                user={currentUser}
                elapsedSeconds={elapsedSeconds}
                onComplete={() => { setCurrentTab('queue'); setIntakeStep(1); setSlots(INITIAL_DOCUMENT_SLOTS); setExtractedData({}); setIsTimerRunning(false); setCurrentCaseId(null); }}
                onBack={() => setIntakeStep(2)}
                isDualLanguage={isDualLanguage}
              />
            )}
          </>
        )}
      </main>

      {/* Floating Help Button */}
      <button
        onClick={() => setIsHelpOpen(true)}
        className="fixed bottom-6 right-6 z-40 px-4 py-3 bg-slate-900 hover:bg-slate-800 text-white rounded-full shadow-xl flex items-center gap-2 transition-all hover:scale-105"
      >
        <div className="w-6 h-6 rounded-full bg-emerald-500 text-slate-950 flex items-center justify-center">
          <Sparkles className="w-3.5 h-3.5" />
        </div>
        <span className="text-xs font-bold">AI Help</span>
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
      </button>

      <HelpChatModal
        isOpen={isHelpOpen}
        onClose={() => setIsHelpOpen(false)}
        currentRole={currentRole}
        isDualLanguage={isDualLanguage}
      />
    </div>
  );
};

export default App;