import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getProblems, startRound, runCode, submitCode, finishRound } from '../services/codingService';
import { getSessionStatus } from '../services/sessionService';
import useAdvancedProctoring from '../hooks/useAdvancedProctoring';
import { useTimer } from '../hooks/useTimer';
import CodingHeader from '../components/coding/CodingHeader';
import ProblemPanel from '../components/coding/ProblemPanel';
import EditorPanel from '../components/coding/EditorPanel';
import ResizablePanel from '../components/coding/ResizablePanel';
import ProctoringWarning from '../components/ProctoringWarning';
import { STARTER_TEMPLATES, DEFAULT_STARTER } from '../constants/starterTemplates';

export default function CodingRoundV2() {
  const navigate = useNavigate();
  const location = useLocation();
  
  const [problems, setProblems] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  // Per-problem code buffers; the parent owns the editor state so a problem's
  // code survives switching to another problem and back.
  const [codes, setCodes] = useState({});
  const [language, setLanguage] = useState('python');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyAction, setBusyAction] = useState('');
  const [saveStatus, setSaveStatus] = useState('idle');
  const [activeResultTab, setActiveResultTab] = useState('testcases');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [panelSize, setPanelSize] = useState(35);
  const [proctoringWarnings, setProctoringWarnings] = useState([]);
  const [testTerminated, setTestTerminated] = useState(false);
  const [isFinishing, setIsFinishing] = useState(false);

  const storedSessionId = location.state?.sessionId 
    || parseInt(localStorage.getItem('coding_round_id') || '0', 10) 
    || null;
  // sessionId is resolved separately so we only pass a real id to proctoring.
  const [sessionId, setSessionId] = useState(null); // Don't use stale localStorage value

  const { startMonitoring, stopMonitoring, isMonitoring, videoRef } = useAdvancedProctoring(sessionId, (violation) => {
    if (violation.terminate) {
      setTestTerminated(true);
      return;
    }
    const type = String(violation.eventType || '');
    const warning = {
      type,
      message: `Proctoring violation detected: ${violation.eventType}`,
      count: violation.violationCount,
      severity: 'high',
    };
    if (type === 'FACE_NOT_VISIBLE') {
      warning.message = 'Face not detected. Keep your face visible in the camera to continue.';
      warning.blocking = true;
    }
    if (type === 'TAB_SWITCH') {
      warning.message = 'Tab switching is not allowed during the coding round.';
    }
    if (type === 'FULLSCREEN_EXIT') {
      warning.message = 'Fullscreen mode is required for the coding round.';
    }
    setProctoringWarnings((prev) => [...prev, warning]);
    setTimeout(() => {
      setProctoringWarnings((prev) => prev.filter((w) => w !== warning));
    }, 5000);
  });

  // Only auto-submit/navigate once the round is actually loaded. The useTimer hook
  // never fires while timeRemaining is null, so no premature navigation.
  const handleTimeExpired = useCallback(async () => {
    const currentProblem = problems[selectedIndex];
    if (!currentProblem) return;
    const currentCode = codes[currentProblem.id] || '';
    try {
      await submitCode({ problem_id: currentProblem.id, code: currentCode, language });
    } catch (e) {
      console.error('Auto-submit failed:', e);
    }
    navigate('/coding/result');
  }, [problems, selectedIndex, codes, language, navigate]);

  // Timer starts as unresolved (null) and is populated from the real session.
  const { timeRemaining, setTimeRemaining } = useTimer(null, handleTimeExpired);

  // Only start monitoring once we have a confirmed real sessionId.
  // This prevents the stale-localStorage-id mismatch warning where proctoring
  // fires with an old id before getSessionStatus() resolves the current one.
  useEffect(() => {
    if (!sessionId) return;
    startMonitoring?.();
    return () => stopMonitoring?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const loadProblems = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const started = await startRound();
      // Backend returns {round, assigned, problems}
      if (started && started.problems && started.problems.length > 0) {
        setProblems(started.problems);
        
        if (started.round?.session_id) {
          localStorage.setItem('coding_round_id', started.round.session_id.toString());
          setSessionId(started.round.session_id);
        }
      } else {
        const fallback = await getProblems();
        setProblems(Array.isArray(fallback) ? fallback : []);
      }
    } catch (e) {
      console.error('[CodingRoundV2] startRound error:', e);
      try {
        const fallback = await getProblems();
        setProblems(Array.isArray(fallback) ? fallback : []);
      } catch (err) {
        console.error('[CodingRoundV2] getProblems also failed:', err);
        setError('Unable to load coding problems. Please return to the dashboard and try again.');
        setProblems([]);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProblems();
  }, [loadProblems]);

  // After problems load (and session/round is active server-side), pull the real
  // remaining time + session id from the existing session API. Timer stays null
  // (loading) until then, so it can never fire prematurely.
  useEffect(() => {
    if (loading || problems.length === 0) return;
    let cancelled = false;
    getSessionStatus()
      .then((data) => {
        if (cancelled) return;
        if (data?.id && data.id !== sessionId) {
          setSessionId(data.id);
          localStorage.setItem('coding_round_id', data.id.toString());
        }
        const remaining = data?.time_remaining_seconds;
        if (typeof remaining === 'number' && Number.isFinite(remaining) && remaining >= 0) {
          setTimeRemaining(remaining);
        }
      })
      .catch((e) => {
        console.warn('[CodingRoundV2] Failed to load session time:', e);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, problems.length]);

  useEffect(() => {
    if (selectedIndex >= problems.length) {
      setSelectedIndex(0);
    }
  }, [problems, selectedIndex]);

  const current = problems[selectedIndex] || null;

  // Track which (problem, language) combination we have already primed so
  // switching problems OR languages loads the correct starter/draft once and
  // never overwrites user code afterwards.
  const starterInitializedRef = useRef({});

  useEffect(() => {
    if (!current) return;
    const initKey = `${current.id}:${language}`;
    if (starterInitializedRef.current[initKey]) return;

    starterInitializedRef.current[initKey] = true;

    const savedDraft = localStorage.getItem(`coding-draft-${current.id}-${language}`);
    if (savedDraft !== null) {
      setCodes((prev) => ({ ...prev, [current.id]: savedDraft }));
      return;
    }

    const starterCode = current.starterCode?.[language] || STARTER_TEMPLATES[language] || DEFAULT_STARTER;
    setCodes((prev) => ({ ...prev, [current.id]: starterCode }));
  }, [current, language]);

  // Persist the buffer under the current language's draft before switching so
  // work is never lost and each language gets the correct starter on its first load.
  const handleLanguageChange = (newLanguage) => {
    if (!current || newLanguage === language) return;
    try {
      localStorage.setItem(`coding-draft-${current.id}-${language}`, codes[current.id] || '');
    } catch {
      // ignore localStorage quota/security errors
    }
    setLanguage(newLanguage);
  };

  const currentCode = current ? codes[current.id] || '' : '';

  const handleRun = async () => {
    if (!current) return;
    setBusyAction('run');
    setResult({ heading: 'Running visible test cases...', raw: null });
    try {
      const res = await runCode({ 
        problem_id: current.id, 
        code: currentCode, 
        language,
      });
      setResult({ heading: 'Run complete', raw: res });
      setActiveResultTab('testcases');
    } catch (e) {
      setResult({ heading: 'Run failed', raw: e.response?.data || { detail: 'Error running code', status: 'internal_error' } });
      setActiveResultTab('errors');
    } finally {
      setBusyAction('');
    }
  };

  const handleSubmit = async () => {
    if (!current) return;
    setBusyAction('submit');
    setResult({ heading: 'Submitting solution...', raw: null });
    try {
      const res = await submitCode({ problem_id: current.id, code: currentCode, language });
      setResult({ heading: 'Submission complete', raw: res });
      setActiveResultTab('testcases');
    } catch (e) {
      setResult({ heading: 'Submission failed', raw: e.response?.data || { detail: 'Error submitting code', status: 'internal_error' } });
      setActiveResultTab('errors');
    } finally {
      setBusyAction('');
    }
  };

  const handleFinish = async () => {
    setIsFinishing(true);
    try {
      const res = await finishRound();
      navigate('/coding/result');
    } catch (e) {
      console.error('Finish round failed:', e);
      setIsFinishing(false);
    }
  };

  const handleSave = useCallback(async () => {
    if (!current) return;
    const toSave = codes[current.id] || '';
    setSaveStatus('saving');
    try {
      localStorage.setItem(`coding-draft-${current.id}-${language}`, toSave);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch {
      setSaveStatus('idle');
    }
  }, [current, language, codes]);

  useEffect(() => {
    const timer = setTimeout(() => {
      handleSave();
    }, 1000);
    return () => clearTimeout(timer);
  }, [codes, handleSave]);

  const toggleFullscreen = async () => {
    if (!isFullscreen) {
      try {
        await document.documentElement.requestFullscreen();
        setIsFullscreen(true);
      } catch (e) {
        console.warn('Fullscreen failed:', e);
      }
    } else {
      try {
        await document.exitFullscreen();
        setIsFullscreen(false);
      } catch (e) {
        console.warn('Exit fullscreen failed:', e);
      }
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const questionNumbers = problems.map((_, i) => i + 1);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="animate-pulse space-y-4 p-4 max-w-[1600px] mx-auto">
          <div className="h-16 rounded-xl bg-white/5 border border-white/10" />
          <div className="grid gap-4 lg:grid-cols-[35%_1fr] h-[calc(100vh-8rem)]">
            <div className="h-full rounded-xl bg-white/5 border border-white/10" />
            <div className="h-full rounded-xl bg-white/5 border border-white/10 flex flex-col">
              <div className="h-16 bg-white/5 border-b border-white/10" />
              <div className="flex-1 bg-slate-950" />
              <div className="h-64 bg-white/5 border-t border-white/10" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!current) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-400/10 border border-red-400/30 flex items-center justify-center">
            <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-2xl font-semibold mb-2">Coding Round</h2>
          <p className="text-slate-400">{error || 'No coding problems are available right now.'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen bg-slate-950 text-slate-100 ${isFullscreen ? 'fixed inset-0 z-50' : ''}`}>
      {proctoringWarnings.length > 0 && !testTerminated && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[200] w-full max-w-xl px-4 space-y-2">
          {proctoringWarnings.map((warning, index) => (
            <ProctoringWarning
              key={index}
              warning={warning}
              onDismiss={() => setProctoringWarnings((prev) => prev.filter((_, i) => i !== index))}
              onRetry={() => setProctoringWarnings((prev) => prev.filter((_, i) => i !== index))}
            />
          ))}
        </div>
      )}

      {testTerminated && (
        <div className="fixed inset-0 z-[300] bg-black/95 flex items-center justify-center">
          <div className="bg-white rounded-3xl p-8 max-w-lg mx-4 text-center shadow-2xl">
            <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-red-100 text-red-600 mb-6">
              <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 className="text-3xl font-black tracking-tight mb-4 text-red-600">Test Terminated</h3>
            <p className="text-slate-600 text-base mb-6 leading-relaxed">
              You have exceeded the maximum limit for proctoring violations. Your coding session has been halted.
            </p>
            <button
              onClick={() => navigate('/dashboard')}
              className="px-6 py-3 bg-red-600 hover:bg-red-700 rounded-xl font-bold text-white transition-colors"
            >
              Return to Dashboard
            </button>
          </div>
        </div>
      )}

      {/* Proctoring video feed - always rendered but hidden when not monitoring */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`fixed bottom-4 right-4 w-32 h-24 rounded-lg border border-white/20 bg-black/50 object-cover z-40 transition-opacity ${
          sessionId && isMonitoring ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      />

      <CodingHeader
        currentQuestion={selectedIndex + 1}
        totalQuestions={problems.length}
        timeRemaining={timeRemaining}
        onFullscreenToggle={toggleFullscreen}
        isFullscreen={isFullscreen}
        proctoringStatus={isMonitoring ? 'active' : 'inactive'}
        questionNumbers={questionNumbers}
        onQuestionSelect={setSelectedIndex}
        canNavigate={true}
        onFinish={handleFinish}
        isFinishing={isFinishing}
      />

      <div className="flex-1 overflow-hidden" style={{ height: 'calc(100vh - 64px)' }}>
        <ResizablePanel
          defaultSize={panelSize}
          minSize={25}
          maxSize={50}
          onSizeChange={setPanelSize}
          left={
            <ProblemPanel
              problem={current}
            />
          }
          right={
            <EditorPanel
              problem={current}
              language={language}
              onLanguageChange={handleLanguageChange}
              code={currentCode}
              onCodeChange={(value) =>
                setCodes((prev) => ({ ...prev, [current.id]: value ?? '' }))
              }
              onRun={handleRun}
              onSubmit={handleSubmit}
              onSave={handleSave}
              isRunning={busyAction === 'run'}
              isSubmitting={busyAction === 'submit'}
              saveStatus={saveStatus}
              result={result}
              activeResultTab={activeResultTab}
              onResultTabChange={setActiveResultTab}
            />
          }
        />
      </div>
    </div>
  );
}