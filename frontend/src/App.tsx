import React, { useState, useEffect, useCallback } from 'react';
import { AppUser, UserRole, INITIAL_DOCUMENT_SLOTS, DocumentSlotConfig, CrossCheckResult } from './types';
import { authApi, setAuthToken, getAuthToken } from './lib/api';
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
  const [currentCaseId, setCurrentCaseId] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isTimerRunning, setIsTimerRunning] = useState(false);

  // Admin tab
  const [adminTab, setAdminTab] = useState<string>('all_cases');

  // Check stored session on mount
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      authApi.getMe()
        .then(({ user }) => setCurrentUser(user))
        .catch(() => setAuthToken(null));
    }
  }, []);

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

  return (
    <div className="min-h-screen bg-slate-100">
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
