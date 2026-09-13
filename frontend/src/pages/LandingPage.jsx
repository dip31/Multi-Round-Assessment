import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowUpRight,
  Brain,
  Code2,
  FileBarChart,
  GraduationCap,
  Mic,
  ShieldCheck,
  Users,
} from 'lucide-react';

/**
 * Landing page.
 *
 * DESIGN NOTE — why this looks like a trading terminal:
 * placement readiness behaves like a traded instrument. It is a single number
 * that moves on every attempt, carries a history that explains it, and has a
 * direction. So the page presents it that way: a live panel, a drawn sparkline,
 * a delta in points, a ticker of companies with their cutoffs.
 *
 * Two rules keep that metaphor honest:
 *   - Emerald/rose encode DIRECTION ONLY (up/down). They are never brand
 *     colours and never appear on a button. Brand is the violet->cyan pair
 *     inherited from the existing Login/Register pages.
 *   - JetBrains Mono is used for NUMERALS ONLY, where digits must align.
 *     Labels stay in Inter.
 *
 * Motion is one orchestrated open (sparkline draws, score counts up, ticker
 * starts) plus the continuously running ticker. Sections deliberately do NOT
 * fade in on scroll — that would dilute the single moment that matters.
 * Everything respects prefers-reduced-motion.
 *
 * Styles are scoped to `.edi-landing` in a component-level <style> tag so that
 * `index.css` stays untouched and nothing here can leak into the dashboards.
 */

/* ── Content ─────────────────────────────────────────────────────────── */

// Campus recruiters and the readiness cutoff each expects. Mirrors the
// eligibility framing students actually see on the dashboard.
const TICKER = [
  { name: 'Infosys', cutoff: 70, move: 2 },
  { name: 'TCS NQT', cutoff: 65, move: -1 },
  { name: 'Wipro', cutoff: 62, move: 3 },
  { name: 'Accenture', cutoff: 68, move: 1 },
  { name: 'Cognizant', cutoff: 64, move: -2 },
  { name: 'Capgemini', cutoff: 60, move: 0 },
  { name: 'Deloitte', cutoff: 74, move: 4 },
  { name: 'Zoho', cutoff: 72, move: -1 },
];

// The same six-month trend the student dashboard renders, so the marketing
// surface and the product agree on the story.
const TREND = [46, 52, 56, 61, 65, 71];

const ROUNDS = [
  {
    n: '01',
    title: 'Aptitude',
    icon: Brain,
    body:
      'Adaptive by design. Answer well and the next question gets harder; struggle and it steps back to rebuild accuracy. Twenty questions, thirty minutes.',
  },
  {
    n: '02',
    title: 'Coding',
    icon: Code2,
    body:
      'Write real code in the editor and run it against real test cases. Correctness, logic and time taken all feed the score.',
  },
  {
    n: '03',
    title: 'Interview',
    icon: Mic,
    body:
      'A voice interview that has read your resume. It asks follow-up questions based on what you just said, not from a fixed list.',
  },
  {
    n: '04',
    title: 'Report',
    icon: FileBarChart,
    body:
      'Round-wise scores, the topics that cost you marks, and a ranked list of what to practise before the next attempt.',
  },
];

const ROLES = [
  {
    id: 'student',
    label: 'Student',
    icon: GraduationCap,
    body: 'Track your readiness, practise the topics holding it down, and see which drives you qualify for.',
    points: ['Readiness score and trend', 'Practice recommendations', 'Upcoming drives'],
  },
  {
    id: 'faculty',
    label: 'Faculty',
    icon: Users,
    body: 'Follow your cohort round by round and reach students who are slipping while there is still time.',
    points: ['Cohort analytics', 'At-risk students', 'Intervention tracking'],
  },
  {
    id: 'tpo',
    label: 'Placement officer',
    icon: FileBarChart,
    body: 'Run the pipeline end to end — companies, eligibility, candidates and offers in one place.',
    points: ['Placement pipeline', 'Company and drive records', 'Offer reporting'],
  },
];

/* ── Motion helpers ──────────────────────────────────────────────────── */

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);

    const onChange = (e) => setReduced(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  return reduced;
}

/** Counts to `target` once `start` flips true. Skips straight to the value
 *  when motion is reduced, so the number is never withheld. */
function useCountUp(target, start, { duration = 1100, reduced = false } = {}) {
  const [value, setValue] = useState(reduced ? target : 0);
  const frameRef = useRef(0);

  useEffect(() => {
    if (reduced) {
      setValue(target);
      return undefined;
    }
    if (!start) return undefined;

    const startedAt = performance.now();

    const tick = (now) => {
      const t = Math.min(1, (now - startedAt) / duration);
      // easeOutCubic — fast then settling, like a figure locking in.
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(target * eased));
      if (t < 1) frameRef.current = requestAnimationFrame(tick);
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, start, duration, reduced]);

  return value;
}

/* ── Sparkline ───────────────────────────────────────────────────────── */

const CHART = { w: 320, h: 120, padX: 20, top: 20, bottom: 110, min: 40, max: 80 };

function buildSparkline(values) {
  const { w, padX, top, bottom, min, max } = CHART;
  const span = (w - padX * 2) / (values.length - 1);

  const points = values.map((v, i) => {
    const x = padX + i * span;
    const ratio = (v - min) / (max - min);
    const y = bottom - ratio * (bottom - top);
    return { x, y: Number(y.toFixed(2)), v };
  });

  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
  const area = `${line} L${points[points.length - 1].x},${bottom} L${points[0].x},${bottom} Z`;

  return { points, line, area };
}

/* ── Page ────────────────────────────────────────────────────────────── */

export default function LandingPage() {
  const reduced = usePrefersReducedMotion();
  const [open, setOpen] = useState(false);

  const { points, line, area } = useMemo(() => buildSparkline(TREND), []);
  const latest = TREND[TREND.length - 1];
  const delta = latest - TREND[TREND.length - 2];
  const score = useCountUp(latest, open, { reduced });

  // Trigger the open sequence on mount. One frame of delay lets the initial
  // paint land first so the draw animation is actually visible.
  useEffect(() => {
    const id = requestAnimationFrame(() => setOpen(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div className={`edi-landing light ${open ? 'is-open' : ''}`}>
      <style>{CSS}</style>

      {/* ── Nav ───────────────────────────────────────────────────────── */}
      <header className="nav">
        <div className="shell nav-inner">
          <Link to="/" className="brand" aria-label="AIPlacement home">
            <span className="brand-mark" aria-hidden="true" />
            AIPlacement
          </Link>

          <nav className="nav-links" aria-label="Primary">
            <a href="#rounds">Rounds</a>
            <a href="#roles">Who signs in</a>
            <a href="#integrity">Integrity</a>
          </nav>

          <div className="nav-actions">
            <Link to="/register" className="btn btn-ghost">
              Create account
            </Link>
            <Link to="/login" className="btn btn-solid">
              Sign in
            </Link>
          </div>
        </div>
      </header>

      {/* ── Ticker ────────────────────────────────────────────────────── */}
      <div className="ticker" aria-label="Recruiters currently hiring and their readiness cutoffs">
        <div className="ticker-track">
          {[0, 1].map((copy) => (
            <div className="ticker-group" key={copy} aria-hidden={copy === 1}>
              {TICKER.map((t) => (
                <span className="tick" key={`${copy}-${t.name}`}>
                  <span className="tick-name">{t.name}</span>
                  <span className="tick-cut">
                    cutoff <b>{t.cutoff}</b>
                  </span>
                  <span className={`tick-move ${t.move > 0 ? 'up' : t.move < 0 ? 'down' : 'flat'}`}>
                    {t.move > 0 ? '▲' : t.move < 0 ? '▼' : '—'}
                    {t.move !== 0 && Math.abs(t.move)}
                  </span>
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>

      <main>
        {/* ── Hero ────────────────────────────────────────────────────── */}
        <section className="hero">
          <div className="glow glow-a" aria-hidden="true" />
          <div className="glow glow-b" aria-hidden="true" />

          <div className="shell hero-grid">
            <div className="hero-copy">
              <h1>
                Know your placement readiness
                <br />
                before the drive does.
              </h1>

              <p className="lede">
                Three proctored rounds — aptitude, coding and an AI interview — resolve into one
                score that moves every time you attempt. Your faculty and placement officer see the
                same number you do.
              </p>

              <div className="hero-cta">
                <Link to="/login" className="btn btn-solid btn-lg">
                  Sign in
                </Link>
                <a href="#rounds" className="btn btn-outline btn-lg">
                  See how scoring works
                </a>
              </div>

              <dl className="hero-facts">
                <div>
                  <dt>Difficulty</dt>
                  <dd>Adapts per answer</dd>
                </div>
                <div>
                  <dt>Code</dt>
                  <dd>Runs against test cases</dd>
                </div>
                <div>
                  <dt>Interview</dt>
                  <dd>Reads your resume</dd>
                </div>
              </dl>
            </div>

            {/* The instrument panel — the one loud element on the page. */}
            <div className="panel" role="img"
              aria-label={`Placement readiness ${latest} out of 100, up ${delta} points versus last month. Aptitude 78, coding 64, interview not attempted.`}
            >
              <div className="panel-head">
                <span className="panel-label">Placement readiness</span>
                <span className="panel-live">
                  <i aria-hidden="true" />
                  Live
                </span>
              </div>

              <div className="panel-score">
                <span className="score">{score}</span>
                <span className="score-max">/100</span>
                <span className="score-delta up">
                  ▲ {delta} <small>vs last month</small>
                </span>
              </div>

              <svg className="spark" viewBox={`0 0 ${CHART.w} ${CHART.h}`} aria-hidden="true">
                <defs>
                  <linearGradient id="sparkStroke" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#2DB7F2" />
                    <stop offset="100%" stopColor="#BA9EFF" />
                  </linearGradient>
                  <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#BA9EFF" stopOpacity="0.28" />
                    <stop offset="100%" stopColor="#BA9EFF" stopOpacity="0" />
                  </linearGradient>
                </defs>

                {[40, 70, 100].map((y) => (
                  <line key={y} className="grid" x1="0" y1={y} x2={CHART.w} y2={y} />
                ))}

                <path className="spark-area" d={area} fill="url(#sparkFill)" />
                <path className="spark-line" d={line} />
                <circle className="spark-dot" cx={points[points.length - 1].x} cy={points[points.length - 1].y} r="4" />
              </svg>

              <ul className="panel-rounds">
                <li>
                  <span>Aptitude</span>
                  <b>78</b>
                </li>
                <li>
                  <span>Coding</span>
                  <b>64</b>
                </li>
                <li className="pending">
                  <span>Interview</span>
                  <b>—</b>
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* ── Rounds ──────────────────────────────────────────────────── */}
        <section id="rounds" className="band">
          <div className="shell">
            <div className="band-head">
              <h2>Three rounds. One score.</h2>
              <p>
                Each round is scored on its own, then weighted into readiness. Skip one and the
                score stays capped until you complete it.
              </p>
            </div>

            <ol className="rounds">
              {ROUNDS.map((r) => {
                const Icon = r.icon;
                return (
                  <li key={r.n}>
                    <span className="round-n">{r.n}</span>
                    <Icon className="round-icon" size={20} aria-hidden="true" />
                    <h3>{r.title}</h3>
                    <p>{r.body}</p>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>

        {/* ── Roles ───────────────────────────────────────────────────── */}
        <section id="roles" className="band band-alt">
          <div className="shell">
            <div className="band-head">
              <h2>Who signs in</h2>
              <p>
                One account per person. Your role decides what you see after sign-in — students
                reach their own dashboard, faculty and placement officers reach theirs.
              </p>
            </div>

            <div className="roles">
              {ROLES.map((role) => {
                const Icon = role.icon;
                return (
                  <article className="role" key={role.id}>
                    <Icon className="role-icon" size={22} aria-hidden="true" />
                    <h3>{role.label}</h3>
                    <p>{role.body}</p>
                    <ul>
                      {role.points.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                    <Link to="/login" className="role-link">
                      Sign in as {role.label.toLowerCase()}
                      <ArrowUpRight size={15} aria-hidden="true" />
                    </Link>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── Integrity ───────────────────────────────────────────────── */}
        <section id="integrity" className="band">
          <div className="shell integrity">
            <div>
              <ShieldCheck className="integrity-icon" size={26} aria-hidden="true" />
              <h2>Scores only mean something if the session was clean.</h2>
              <p>
                Every round runs proctored. The camera checks that one person is present, tab
                switches and window blur are recorded, and you get a visible warning before anything
                counts against the attempt — no silent strikes.
              </p>
            </div>

            <ul className="integrity-list">
              <li>Camera and microphone checks before the round starts</li>
              <li>Tab-switch and focus-loss recorded in the session log</li>
              <li>Warnings shown in-session, never applied retroactively</li>
              <li>Full session report available to you and your placement cell</li>
            </ul>
          </div>
        </section>

        {/* ── CTA ─────────────────────────────────────────────────────── */}
        <section className="cta">
          <div className="shell">
            <h2>Start with the aptitude round.</h2>
            <p>It takes thirty minutes and gives you a readiness score the same day.</p>
            <Link to="/login" className="btn btn-solid btn-lg">
              Sign in
            </Link>
          </div>
        </section>
      </main>

      <footer className="foot">
        <div className="shell foot-inner">
          <div>
            <span className="brand">
              <span className="brand-mark" aria-hidden="true" />
              AIPlacement
            </span>
            <p>Adaptive placement assessment for campus training and placement cells.</p>
          </div>
          <nav aria-label="Footer">
            <a href="#rounds">Rounds</a>
            <a href="#roles">Who signs in</a>
            <a href="#integrity">Integrity</a>
            <Link to="/login">Sign in</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}

/* ── Scoped styles ───────────────────────────────────────────────────── */

const CSS = `
.edi-landing {
  --canvas: #0B0B0E;
  --panel: #141418;
  --panel-2: #1A1A20;
  --line: #26262E;
  --violet: #BA9EFF;
  --cyan: #2DB7F2;
  --up: #34D399;
  --down: #FB7185;
  --text: #F5F3F7;
  --muted: #9E9BA6;

  background: var(--canvas);
  color: var(--text);
  font-family: var(--font-sans);
  min-height: 100vh;
  overflow-x: hidden;
}

/* Keep the marketing surface light while leaving the authenticated screens
   and shared application theme unchanged. */
.edi-landing.light {
  --canvas: #f8fafc;
  --panel: #ffffff;
  --panel-2: #f1f5f9;
  --line: #e2e8f0;
  --violet: #4f46e5;
  --cyan: #0891b2;
  --text: #0f172a;
  --muted: #64748b;
  --up: #059669;
  --down: #e11d48;
}

.edi-landing.light .nav {
  background: rgba(248, 250, 252, .86);
}
.edi-landing.light .ticker,
.edi-landing.light .band-alt,
.edi-landing.light .band-alt .rounds li,
.edi-landing.light .cta {
  background: #f1f5f9;
}
.edi-landing.light .panel {
  box-shadow: 0 30px 70px rgba(15, 23, 42, .12);
}
.edi-landing.light .btn-outline {
  color: var(--text);
  border-color: #cbd5e1;
}
.edi-landing.light .btn-ghost {
  color: var(--muted);
}
.edi-landing.light .tick-cut,
.edi-landing.light .hero-facts dt,
.edi-landing.light .score-delta small,
.edi-landing.light .panel-rounds span,
.edi-landing.light .foot p {
  color: #64748b;
}
.edi-landing.light .tick-cut b {
  color: #334155;
}
.edi-landing.light .score-max,
.edi-landing.light .round-n,
.edi-landing.light .panel-rounds .pending b {
  color: #94a3b8;
}
.edi-landing.light .rounds li,
.edi-landing.light .role {
  background: var(--panel);
}
.edi-landing.light .rounds li:hover {
  background: #eef2ff;
}
.edi-landing.light .role > p,
.edi-landing.light .band-head p,
.edi-landing.light .integrity > div > p,
.edi-landing.light .cta p {
  color: var(--muted);
}
.edi-landing.light .role ul li,
.edi-landing.light .integrity-list li {
  color: #475569;
}
.edi-landing.light .role:hover {
  border-color: #a5b4fc;
}
.edi-landing.light .foot nav a:hover,
.edi-landing.light .nav-links a:hover {
  color: var(--text);
}

.edi-landing ::selection { background: var(--violet); color: #1A0A3C; }

.edi-landing .shell {
  width: 100%;
  max-width: 1140px;
  margin: 0 auto;
  padding: 0 24px;
}

/* Focus: one visible treatment everywhere. */
.edi-landing a:focus-visible,
.edi-landing button:focus-visible {
  outline: 2px solid var(--violet);
  outline-offset: 3px;
  border-radius: 6px;
}

/* ── Buttons ── */
.edi-landing .btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  border-radius: 999px;
  padding: 10px 20px;
  text-decoration: none;
  transition: transform .15s ease, background-color .2s ease, border-color .2s ease;
  white-space: nowrap;
}
.edi-landing .btn-lg { padding: 14px 28px; font-size: 15px; }
.edi-landing .btn-solid {
  background: linear-gradient(135deg, var(--violet), #8455EF);
  color: #1A0A3C;
}
.edi-landing .btn-solid:hover { transform: translateY(-1px); }
.edi-landing .btn-outline {
  border: 1px solid var(--line);
  color: var(--text);
}
.edi-landing .btn-outline:hover { border-color: var(--violet); }
.edi-landing .btn-ghost { color: var(--muted); }
.edi-landing .btn-ghost:hover { color: var(--text); }

/* ── Nav ── */
.edi-landing .nav {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(11, 11, 14, .72);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--line);
}
.edi-landing .nav-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  gap: 24px;
}
.edi-landing .brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 19px;
  letter-spacing: -.02em;
  color: var(--text);
  text-decoration: none;
}
.edi-landing .brand-mark {
  width: 11px; height: 11px;
  border-radius: 3px;
  background: linear-gradient(135deg, var(--cyan), var(--violet));
}
.edi-landing .nav-links { display: none; gap: 28px; }
.edi-landing .nav-links a {
  color: var(--muted);
  text-decoration: none;
  font-size: 14px;
  transition: color .2s ease;
}
.edi-landing .nav-links a:hover { color: var(--text); }
.edi-landing .nav-actions { display: flex; align-items: center; gap: 8px; }
@media (min-width: 900px) { .edi-landing .nav-links { display: flex; } }

/* ── Ticker ── */
.edi-landing .ticker {
  border-bottom: 1px solid var(--line);
  background: #0E0E12;
  overflow: hidden;
  padding: 9px 0;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
          mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
}
.edi-landing .ticker-track {
  display: flex;
  width: max-content;
  animation: edi-marquee 42s linear infinite;
}
.edi-landing .ticker:hover .ticker-track { animation-play-state: paused; }
.edi-landing .ticker-group { display: flex; }
.edi-landing .tick {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 0 22px;
  border-right: 1px solid var(--line);
  font-size: 12.5px;
  white-space: nowrap;
}
.edi-landing .tick-name { color: var(--text); font-weight: 600; }
.edi-landing .tick-cut { color: var(--muted); }
/* Numerals in mono so the column of cutoffs stays aligned as it scrolls. */
.edi-landing .tick-cut b { font-family: var(--font-mono); font-weight: 500; color: #CFCBD6; }
.edi-landing .tick-move { font-family: var(--font-mono); font-size: 11.5px; }
.edi-landing .tick-move.up { color: var(--up); }
.edi-landing .tick-move.down { color: var(--down); }
.edi-landing .tick-move.flat { color: #5B5866; }

@keyframes edi-marquee {
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
}

/* ── Hero ── */
.edi-landing .hero { position: relative; padding: 84px 0 96px; }
.edi-landing .glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
  pointer-events: none;
}
.edi-landing .glow-a {
  width: 520px; height: 520px;
  top: -180px; right: -120px;
  background: rgba(186, 158, 255, .16);
}
.edi-landing .glow-b {
  width: 420px; height: 420px;
  bottom: -160px; left: -140px;
  background: rgba(45, 183, 242, .10);
}
.edi-landing .hero-grid {
  position: relative;
  display: grid;
  grid-template-columns: 1fr;
  gap: 56px;
  align-items: center;
}
@media (min-width: 980px) {
  .edi-landing .hero-grid { grid-template-columns: 1.05fr .95fr; gap: 64px; }
}
.edi-landing .hero-copy h1 {
  font-family: var(--font-display);
  font-weight: 800;
  font-size: clamp(38px, 6vw, 62px);
  line-height: 1.04;
  letter-spacing: -.035em;
  margin-bottom: 22px;
}
.edi-landing .lede {
  color: var(--muted);
  font-size: 17px;
  line-height: 1.65;
  max-width: 52ch;
  margin-bottom: 32px;
}
.edi-landing .hero-cta { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 44px; }
.edi-landing .hero-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
  border-top: 1px solid var(--line);
  padding-top: 22px;
  max-width: 520px;
}
.edi-landing .hero-facts dt { font-size: 12.5px; color: #6F6C7A; margin-bottom: 5px; }
.edi-landing .hero-facts dd { font-size: 14px; font-weight: 600; color: var(--text); line-height: 1.35; }

/* ── Instrument panel ── */
.edi-landing .panel {
  background: linear-gradient(180deg, var(--panel-2), var(--panel));
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 22px;
  box-shadow: 0 30px 70px rgba(0,0,0,.5);
}
.edi-landing .panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}
.edi-landing .panel-label { font-size: 13px; color: var(--muted); font-weight: 500; }
.edi-landing .panel-live {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11.5px; color: var(--up);
}
.edi-landing .panel-live i {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--up);
  animation: edi-pulse 2s ease-in-out infinite;
}
@keyframes edi-pulse { 0%,100% { opacity: 1; } 50% { opacity: .3; } }

.edi-landing .panel-score { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }
.edi-landing .score {
  font-family: var(--font-mono);
  font-size: 56px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -.03em;
  font-variant-numeric: tabular-nums;
}
.edi-landing .score-max { font-family: var(--font-mono); font-size: 17px; color: #5B5866; }
.edi-landing .score-delta {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 13px;
}
.edi-landing .score-delta.up { color: var(--up); }
.edi-landing .score-delta small { font-family: var(--font-sans); color: #6F6C7A; margin-left: 4px; }

.edi-landing .spark { width: 100%; height: 130px; display: block; margin: 10px 0 4px; }
.edi-landing .spark .grid { stroke: var(--line); stroke-width: 1; }
.edi-landing .spark-line {
  fill: none;
  stroke: url(#sparkStroke);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 420;
  stroke-dashoffset: 420;
}
.edi-landing.is-open .spark-line { animation: edi-draw 1.5s cubic-bezier(.4,0,.2,1) forwards; }
@keyframes edi-draw { to { stroke-dashoffset: 0; } }

.edi-landing .spark-area { opacity: 0; }
.edi-landing.is-open .spark-area { animation: edi-fade .7s ease .9s forwards; }
@keyframes edi-fade { to { opacity: 1; } }

.edi-landing .spark-dot { fill: var(--violet); opacity: 0; }
.edi-landing.is-open .spark-dot { animation: edi-fade .4s ease 1.4s forwards; }

.edi-landing .panel-rounds {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  list-style: none;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}
.edi-landing .panel-rounds li { display: flex; flex-direction: column; gap: 4px; }
.edi-landing .panel-rounds span { font-size: 12px; color: #6F6C7A; }
.edi-landing .panel-rounds b {
  font-family: var(--font-mono);
  font-size: 19px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.edi-landing .panel-rounds .pending b { color: #4E4B59; }

/* ── Bands ── */
.edi-landing .band { padding: 88px 0; border-top: 1px solid var(--line); }
.edi-landing .band-alt { background: #0E0E12; }
.edi-landing .band-head { max-width: 60ch; margin-bottom: 48px; }
.edi-landing .band-head h2 {
  font-family: var(--font-display);
  font-size: clamp(27px, 3.6vw, 38px);
  font-weight: 700;
  letter-spacing: -.025em;
  line-height: 1.15;
  margin-bottom: 14px;
}
.edi-landing .band-head p { color: var(--muted); font-size: 16px; line-height: 1.65; }

/* ── Rounds (a real sequence, hence numbered) ── */
.edi-landing .rounds {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  border-radius: 14px;
  overflow: hidden;
  list-style: none;
}
@media (min-width: 720px) { .edi-landing .rounds { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1040px) { .edi-landing .rounds { grid-template-columns: repeat(4, 1fr); } }
.edi-landing .rounds li {
  background: var(--canvas);
  padding: 26px 22px 28px;
  position: relative;
  transition: background-color .25s ease;
}
.edi-landing .band-alt .rounds li { background: #0E0E12; }
.edi-landing .rounds li:hover { background: var(--panel); }
.edi-landing .round-n {
  font-family: var(--font-mono);
  font-size: 12px;
  color: #4E4B59;
  display: block;
  margin-bottom: 18px;
}
.edi-landing .round-icon { color: var(--violet); margin-bottom: 12px; }
.edi-landing .rounds h3 {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 8px;
  letter-spacing: -.01em;
}
.edi-landing .rounds p { color: var(--muted); font-size: 13.5px; line-height: 1.6; }

/* ── Roles ── */
.edi-landing .roles {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
}
@media (min-width: 860px) { .edi-landing .roles { grid-template-columns: repeat(3, 1fr); } }
.edi-landing .role {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 26px 24px;
  display: flex;
  flex-direction: column;
  transition: border-color .25s ease;
}
.edi-landing .role:hover { border-color: #3A3746; }
.edi-landing .role-icon { color: var(--cyan); margin-bottom: 16px; }
.edi-landing .role h3 {
  font-family: var(--font-display);
  font-size: 19px;
  font-weight: 700;
  margin-bottom: 10px;
  letter-spacing: -.015em;
}
.edi-landing .role > p { color: var(--muted); font-size: 14px; line-height: 1.6; margin-bottom: 18px; }
.edi-landing .role ul { list-style: none; margin-bottom: 22px; }
.edi-landing .role ul li {
  font-size: 13.5px;
  color: #B9B5C2;
  padding: 7px 0 7px 18px;
  position: relative;
  border-top: 1px solid var(--line);
}
.edi-landing .role ul li::before {
  content: '';
  position: absolute;
  left: 0; top: 50%;
  width: 5px; height: 5px;
  margin-top: -2.5px;
  border-radius: 50%;
  background: var(--violet);
}
.edi-landing .role-link {
  margin-top: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--violet);
  text-decoration: none;
}
.edi-landing .role-link:hover { text-decoration: underline; }

/* ── Integrity ── */
.edi-landing .integrity {
  display: grid;
  grid-template-columns: 1fr;
  gap: 40px;
  align-items: start;
}
@media (min-width: 900px) { .edi-landing .integrity { grid-template-columns: 1.1fr .9fr; gap: 64px; } }
.edi-landing .integrity-icon { color: var(--cyan); margin-bottom: 18px; }
.edi-landing .integrity h2 {
  font-family: var(--font-display);
  font-size: clamp(25px, 3.2vw, 34px);
  font-weight: 700;
  letter-spacing: -.025em;
  line-height: 1.2;
  margin-bottom: 16px;
  max-width: 24ch;
}
.edi-landing .integrity > div > p { color: var(--muted); font-size: 16px; line-height: 1.7; max-width: 54ch; }
.edi-landing .integrity-list { list-style: none; }
.edi-landing .integrity-list li {
  padding: 15px 0;
  border-bottom: 1px solid var(--line);
  font-size: 14.5px;
  color: #C6C2CE;
  line-height: 1.5;
}
.edi-landing .integrity-list li:first-child { border-top: 1px solid var(--line); }

/* ── CTA ── */
.edi-landing .cta {
  padding: 96px 0;
  border-top: 1px solid var(--line);
  background:
    radial-gradient(700px 300px at 50% 0%, rgba(186,158,255,.12), transparent 70%),
    #0E0E12;
  text-align: center;
}
.edi-landing .cta h2 {
  font-family: var(--font-display);
  font-size: clamp(28px, 4vw, 42px);
  font-weight: 700;
  letter-spacing: -.03em;
  margin-bottom: 12px;
}
.edi-landing .cta p { color: var(--muted); font-size: 16px; margin-bottom: 30px; }

/* ── Footer ── */
.edi-landing .foot { border-top: 1px solid var(--line); padding: 44px 0; }
.edi-landing .foot-inner {
  display: flex;
  flex-direction: column;
  gap: 26px;
  justify-content: space-between;
}
@media (min-width: 760px) { .edi-landing .foot-inner { flex-direction: row; align-items: center; } }
.edi-landing .foot p { color: #6F6C7A; font-size: 13.5px; margin-top: 10px; max-width: 40ch; line-height: 1.6; }
.edi-landing .foot nav { display: flex; flex-wrap: wrap; gap: 22px; }
.edi-landing .foot nav a {
  color: var(--muted);
  font-size: 13.5px;
  text-decoration: none;
  transition: color .2s ease;
}
.edi-landing .foot nav a:hover { color: var(--text); }

/* ── Reduced motion: hold every final state, animate nothing. ── */
@media (prefers-reduced-motion: reduce) {
  .edi-landing .ticker-track { animation: none; }
  .edi-landing .panel-live i { animation: none; }
  .edi-landing .spark-line { stroke-dashoffset: 0; animation: none; }
  .edi-landing .spark-area,
  .edi-landing .spark-dot { opacity: 1; animation: none; }
  .edi-landing .btn,
  .edi-landing .rounds li,
  .edi-landing .role { transition: none; }
  .edi-landing .btn-solid:hover { transform: none; }
}
`;
