import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

export default function LandingPage() {
  const [activeSection, setActiveSection] = useState('');
  const [hoveredSection, setHoveredSection] = useState('');
  const navItems = [
    { id: 'features', label: 'Features' },
    { id: 'how-it-works', label: 'How It Works' },
    { id: 'test-flow', label: 'Test Flow' }
  ];
  const activeNavIndex = navItems.findIndex((item) => item.id === activeSection);
  const highlightedSection = hoveredSection || activeSection;
  const highlightedNavIndex = navItems.findIndex((item) => item.id === highlightedSection);

  const navLinkClass = (sectionId) => (
    `relative z-10 transition-colors text-xs font-bold uppercase tracking-wider py-2 px-3 ${
      highlightedSection === sectionId
        ? 'text-indigo-600'
        : 'text-slate-600 hover:text-indigo-600'
    }`
  );

  useEffect(() => {
    const style = document.createElement('style');
    style.innerHTML = `
      .reveal {
        opacity: 0;
        transform: translateY(20px);
        transition: all 0.7s cubic-bezier(0.2, 1, 0.3, 1);
      }

      .reveal.active {
        opacity: 1;
        transform: translateY(0);
      }

      .stagger-item { 
        opacity: 0; 
        transform: translateY(15px); 
      }
      
      .active .stagger-item {
        opacity: 1;
        transform: translateY(0);
        transition: all 0.5s cubic-bezier(0.2, 1, 0.3, 1);
      }

      .card-hover:hover {
        transform: translateY(-4px);
        border-color: #cbd5e1;
        box-shadow: 0 12px 24px -10px rgba(15, 23, 42, 0.08);
      }

      .step-line-container {
        position: absolute;
        top: 48px;
        left: 0;
        width: 100%;
        height: 2px;
        background: #e2e8f0;
        z-index: 0;
      }

      .step-line-progress {
        height: 100%;
        background: #4f46e5;
        width: 0;
        transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1);
      }

      .chart-bar {
        transform-origin: bottom;
        transform: scaleY(0);
        transition: transform 1.2s cubic-bezier(0.34, 1.56, 0.64, 1);
      }
      
      .active .chart-bar {
        transform: scaleY(1);
      }

      .progress-fill {
        width: 0;
        transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1);
      }
      
      .active .progress-fill {
        width: var(--final-width);
      }
    `;
    document.head.appendChild(style);

    const observerOptions = {
      threshold: 0.15,
      rootMargin: "0px 0px -50px 0px"
    };

    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('active');
          
          if (entry.target.id === 'how-it-works') {
            const lineElement = entry.target.querySelector('.step-line-progress');
            if (lineElement) {
              lineElement.style.width = '100%';
            }
          }
        }
      });
    }, observerOptions);

    document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));

    const sectionIds = ['features', 'how-it-works', 'test-flow'];
    const sectionObserver = new IntersectionObserver((entries) => {
      const visibleSection = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

      if (visibleSection?.target?.id) {
        setActiveSection(visibleSection.target.id);
      }
    }, {
      threshold: [0.2, 0.35, 0.5, 0.65],
      rootMargin: '-20% 0px -55% 0px'
    });

    sectionIds.forEach((id) => {
      const section = document.getElementById(id);
      if (section) {
        sectionObserver.observe(section);
      }
    });

    const handleWindowLoad = () => {
      document.querySelectorAll('section').forEach((section, index) => {
        if (index === 0) {
          section.querySelectorAll('.reveal').forEach(el => el.classList.add('active'));
        }
      });
    };

    window.addEventListener('load', handleWindowLoad);

    return () => {
      revealObserver.disconnect();
      sectionObserver.disconnect();
      window.removeEventListener('load', handleWindowLoad);
      document.head.removeChild(style);
    };
  }, []);

  return (
    <div className="bg-slate-50 text-slate-900 font-['Inter'] antialiased min-h-screen flex flex-col">
      {/* Top Navigation Bar */}
      <nav className="fixed top-0 w-full z-50 bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-xs tracking-tight">
        <div className="flex justify-between items-center px-8 py-3.5 max-w-7xl mx-auto">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-black text-sm shadow-sm">
              AI
            </div>
            <span className="text-xl font-black tracking-tight text-slate-900">AIPlacement</span>
          </div>

          <div className="hidden md:block w-[24rem]">
            <div
              className="relative grid grid-cols-3 items-center text-center"
              onMouseLeave={() => setHoveredSection('')}
            >
              <div
                className="absolute bottom-[-6px] left-0 h-[2.5px] bg-indigo-600 rounded-full transition-all duration-300 ease-out"
                style={{
                  width: '33.3333%',
                  transform: `translateX(${Math.max(highlightedNavIndex, 0) * 100}%)`,
                  opacity: highlightedNavIndex === -1 ? 0 : 1
                }}
              />
              {navItems.map((item) => (
                <a
                  key={item.id}
                  className={navLinkClass(item.id)}
                  href={`#${item.id}`}
                  onMouseEnter={() => setHoveredSection(item.id)}
                >
                  {item.label}
                </a>
              ))}
            </div>
          </div>

          <Link
            to="/login"
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-xl text-xs font-bold shadow-sm hover:shadow-md transition-all uppercase tracking-wider"
          >
            Start Assessment
          </Link>
        </div>
      </nav>

      <main className="pt-20 flex-grow">
        {/* Hero Section */}
        <section className="relative overflow-hidden px-6 pt-16 pb-20 md:pt-24 md:pb-32 bg-gradient-to-b from-white via-slate-50 to-slate-100/50">
          <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            <div className="lg:col-span-6 z-10">
              <div className="reveal inline-block px-3.5 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-bold uppercase tracking-wider mb-5">
                Next-Gen Multi-Round Assessment Engine
              </div>
              <h1 className="reveal text-4xl md:text-6xl font-black tracking-tight text-slate-900 leading-[1.15] mb-6">
                AI-Driven Placement Assessment Platform
              </h1>
              <p className="reveal text-base md:text-lg text-slate-600 max-w-xl mb-8 leading-relaxed">
                Simulate real campus placement rounds with adaptive testing powered by reinforcement learning. Elevate candidate standards with verifiable, data-backed insights.
              </p>
              <div className="reveal flex flex-wrap gap-4">
                <Link
                  to="/login"
                  className="px-8 py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs uppercase tracking-wider shadow-md shadow-indigo-600/20 active:scale-95 transition-all inline-flex items-center gap-2"
                >
                  Start Assessment →
                </Link>
                <a
                  href="#features"
                  className="bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 px-8 py-3.5 rounded-xl font-bold text-xs uppercase tracking-wider shadow-xs transition-all inline-block"
                >
                  Learn More
                </a>
              </div>
            </div>
            
            <div className="lg:col-span-6 relative group reveal">
              <div className="relative rounded-3xl overflow-hidden bg-white border border-slate-200 shadow-xl p-3">
                <div className="rounded-2xl overflow-hidden bg-slate-900">
                  <img
                    className="w-full aspect-video object-cover"
                    alt="Assessment interface and analytics"
                    src="https://lh3.googleusercontent.com/aida-public/AB6AXuA42fU8GCOlbjWyBhmhmsj9ps3V9j9BisRD2psOw-4LUJK8tFkW6SHjTENtRr9Se5i6uzuVf5MDxE9R9wtt2nobnm3DOjuKVrj4KoaV7hlW8eyXOOIh1eZtEDF0IXTxdiwNf92no8Y46yvmSXT466djCrj4w6AAKLfwr-C26QCZynSDjE_6ThQMsq3T-yFkeDlQ7VnFHgw6LZAGUK3LGNTG7YpD_MdrmUym8D8aUcSRpYt3EclC1wh3wE94PwuzRAweY_XmmnsDKYCY"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section (Bento Grid) */}
        <section id="features" className="py-20 px-6 bg-white border-y border-slate-200 reveal scroll-mt-20">
          <div className="max-w-7xl mx-auto">
            <div className="mb-14 stagger-item">
              <span className="text-indigo-600 font-bold tracking-widest uppercase text-xs mb-2 block">Capabilities</span>
              <h2 className="text-3xl md:text-4xl font-black text-slate-900 tracking-tight">Powerful Assessment Engine</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 md:grid-rows-2 gap-6">
              {/* Feature 1: Large */}
              <div className="md:col-span-2 bg-slate-50 border border-slate-200 p-8 rounded-3xl transition-all card-hover stagger-item shadow-xs">
                <div className="w-12 h-12 rounded-2xl bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold text-2xl mb-5">
                  🧠
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3">Adaptive Testing Engine</h3>
                <p className="text-slate-600 text-sm leading-relaxed max-w-xl">
                  Every answer dynamically influences upcoming questions. Correct and rapid answers unlock higher difficulty tiers, while foundational recovery questions are served if a candidate needs reinforcement.
                </p>
              </div>
              
              {/* Feature 2: Tall */}
              <div className="md:row-span-2 bg-slate-50 border border-slate-200 p-8 rounded-3xl transition-all card-hover stagger-item shadow-xs flex flex-col justify-between">
                <div>
                  <div className="w-12 h-12 rounded-2xl bg-sky-100 text-sky-600 flex items-center justify-center font-bold text-2xl mb-5">
                    📊
                  </div>
                  <h3 className="text-xl font-bold text-slate-900 mb-3">Performance Analytics</h3>
                  <p className="text-slate-600 text-sm leading-relaxed mb-6">
                    Multi-stage round breakdowns for aptitude, coding, and AI interviews. Track accuracy, response latency, and benchmark percentiles before real campus drives.
                  </p>
                </div>
                <div className="space-y-3 pt-4 border-t border-slate-200">
                  <div>
                    <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                      <span>Quantitative Aptitude</span>
                      <span className="text-indigo-600 font-bold">84%</span>
                    </div>
                    <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                      <div className="h-full bg-indigo-600 progress-fill rounded-full" style={{ '--final-width': '84%' }}></div>
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                      <span>Code Quality & Correctness</span>
                      <span className="text-sky-600 font-bold">76%</span>
                    </div>
                    <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                      <div className="h-full bg-sky-500 progress-fill rounded-full" style={{ '--final-width': '76%' }}></div>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Feature 3 */}
              <div className="bg-slate-50 border border-slate-200 p-8 rounded-3xl transition-all card-hover stagger-item shadow-xs">
                <div className="w-12 h-12 rounded-2xl bg-violet-100 text-violet-600 flex items-center justify-center font-bold text-2xl mb-5">
                  📑
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">Multi-Round Simulation</h3>
                <p className="text-slate-600 text-xs leading-relaxed">
                  Mirror full corporate hiring cycles: timed aptitude screening, interactive live coding, and customized AI technical interviews.
                </p>
              </div>
              
              {/* Feature 4 */}
              <div className="bg-slate-50 border border-slate-200 p-8 rounded-3xl transition-all card-hover stagger-item shadow-xs">
                <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center font-bold text-2xl mb-5">
                  🛡️
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">Automated Proctoring</h3>
                <p className="text-slate-600 text-xs leading-relaxed">
                  Real-time face verification, tab-switch monitoring, and device tracking guarantee session integrity for institutional credibility.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* How It Works Section */}
        <section id="how-it-works" className="py-20 px-6 bg-slate-50 reveal scroll-mt-20">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16 stagger-item">
              <span className="text-indigo-600 font-bold tracking-widest uppercase text-xs mb-2 block">Workflow</span>
              <h2 className="text-3xl md:text-4xl font-black text-slate-900 tracking-tight mb-3">Your Path to Placement Success</h2>
              <p className="text-slate-600 text-sm max-w-2xl mx-auto">
                Follow the 3-round standard sequence: Aptitude Screening, Coding Challenge, and AI Technical Interview.
              </p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8 relative">
              {/* Step 1 */}
              <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs text-center stagger-item">
                <div className="w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center mx-auto mb-4 font-black text-lg">
                  01
                </div>
                <h4 className="font-bold text-slate-900 text-sm mb-2">Round 1: Aptitude Test</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Solve quantitative, logical, and verbal objective questions within adaptive time limits.
                </p>
              </div>
              
              {/* Step 2 */}
              <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs text-center stagger-item">
                <div className="w-14 h-14 rounded-2xl bg-sky-50 border border-sky-200 text-sky-600 flex items-center justify-center mx-auto mb-4 font-black text-lg">
                  02
                </div>
                <h4 className="font-bold text-slate-900 text-sm mb-2">Round 2: Coding Arena</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Write, run, and submit code against test cases with real-time execution feedback.
                </p>
              </div>
              
              {/* Step 3 */}
              <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs text-center stagger-item">
                <div className="w-14 h-14 rounded-2xl bg-purple-50 border border-purple-200 text-purple-600 flex items-center justify-center mx-auto mb-4 font-black text-lg">
                  03
                </div>
                <h4 className="font-bold text-slate-900 text-sm mb-2">Round 3: AI Interview</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Attend role-specific interview rounds using your uploaded profile resume with conversational AI.
                </p>
              </div>
              
              {/* Step 4 */}
              <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs text-center stagger-item">
                <div className="w-14 h-14 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-600 flex items-center justify-center mx-auto mb-4 font-black text-lg">
                  04
                </div>
                <h4 className="font-bold text-slate-900 text-sm mb-2">Comprehensive Report</h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Receive detailed scorecards, competency benchmarks, and actionable placement recommendations.
                </p>
              </div>
            </div>

            <div className="mt-12 flex justify-center gap-4 stagger-item">
              <a
                href="#test-flow"
                className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-3 rounded-xl font-bold text-xs uppercase tracking-wider shadow-sm transition-all"
              >
                View Full Test Flow
              </a>
              <Link
                to="/login"
                className="bg-white hover:bg-slate-100 border border-slate-300 text-slate-700 px-8 py-3 rounded-xl font-bold text-xs uppercase tracking-wider shadow-xs transition-all"
              >
                Go to Login
              </Link>
            </div>
          </div>
        </section>

        {/* Test Flow Section */}
        <section id="test-flow" className="py-20 px-6 bg-white border-t border-slate-200 reveal scroll-mt-20">
          <div className="max-w-4xl mx-auto">
            <div className="mb-12 text-center stagger-item">
              <span className="text-indigo-600 font-bold tracking-widest uppercase text-xs mb-2 block">Step-by-Step Guide</span>
              <h2 className="text-3xl md:text-4xl font-black text-slate-900 tracking-tight mb-2">How to Take the Assessment</h2>
              <p className="text-slate-500 text-xs">Recommended flow for candidates on testing day</p>
            </div>

            <div className="space-y-4">
              {[
                { title: '1. Sign in to your candidate account', desc: 'Log in with your institution credentials and review your student profile details.' },
                { title: '2. Perform device and camera checks', desc: 'Enable camera permissions and ensure proper lighting for proctoring compliance.' },
                { title: '3. Complete Round 1: Aptitude Screening', desc: 'Answer questions within the time limit. Accuracy and speed both influence your score.' },
                { title: '4. Solve Round 2: Coding Challenges', desc: 'Write and test your algorithms in the live multi-language code editor.' },
                { title: '5. Select Resume & Complete AI Interview', desc: 'Pick your tailored CV from your profile and answer targeted technical and behavioral prompts.' },
                { title: '6. Review Consolidated Scorecard', desc: 'Inspect round scores, benchmark percentiles, and improvement pointers.' }
              ].map((step, idx) => (
                <div key={idx} className="stagger-item bg-slate-50 rounded-2xl border border-slate-200 p-5 flex items-start gap-4">
                  <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                    {idx + 1}
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 text-sm mb-1">{step.title}</h4>
                    <p className="text-slate-600 text-xs leading-relaxed">{step.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-10 text-center stagger-item">
              <Link
                to="/login"
                className="px-10 py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs uppercase tracking-wider shadow-md shadow-indigo-600/20 inline-block"
              >
                Sign In & Get Started →
              </Link>
            </div>
          </div>
        </section>

        {/* Product Preview Section */}
        <section className="py-20 px-6 bg-slate-50 border-t border-slate-200 reveal">
          <div className="max-w-6xl mx-auto">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Aptitude Question Card */}
              <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm flex flex-col justify-between stagger-item">
                <div>
                  <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
                    <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full border border-indigo-200">
                      Sample Question 14 of 20
                    </span>
                    <span className="text-xs font-semibold text-slate-400">Timer: 01:45</span>
                  </div>
                  
                  <h3 className="text-base font-bold text-slate-900 mb-6 leading-relaxed">
                    A train traveling at 60 km/h crosses a pole in 9 seconds. What is the length of the train in meters?
                  </h3>
                  
                  <div className="space-y-3">
                    {['120 meters', '150 meters', '180 meters'].map((option, idx) => (
                      <label
                        key={idx}
                        className={`flex items-center p-3.5 rounded-xl border transition-all cursor-pointer ${
                          idx === 1
                            ? 'bg-indigo-50/70 border-indigo-300 font-bold text-indigo-900'
                            : 'bg-slate-50 hover:bg-slate-100 border-slate-200 text-slate-700'
                        }`}
                      >
                        <input
                          type="radio"
                          name="sample-apt"
                          defaultChecked={idx === 1}
                          className="w-4 h-4 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="ml-3 text-xs">{option}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="mt-8 pt-4 border-t border-slate-100 flex justify-end">
                  <Link
                    to="/login"
                    className="px-6 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs transition-colors"
                  >
                    Next Question →
                  </Link>
                </div>
              </div>

              {/* Real-time Analytics Preview */}
              <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm flex flex-col justify-between stagger-item">
                <div>
                  <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
                    <span className="text-xs font-bold text-sky-600 bg-sky-50 px-3 py-1 rounded-full border border-sky-200">
                      Real-time Round Scorecard
                    </span>
                    <span className="text-xs font-bold text-emerald-600">✓ Proctor Active</span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-center">
                      <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Score</div>
                      <div className="text-3xl font-black text-indigo-600">84%</div>
                    </div>
                    <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-center">
                      <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Accuracy</div>
                      <div className="text-3xl font-black text-emerald-600">92%</div>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between items-center text-xs mb-3">
                      <span className="font-semibold text-slate-500">Adaptive Difficulty Curve</span>
                      <span className="font-bold text-indigo-600">Tier 8 (Hard)</span>
                    </div>
                    <div className="h-28 flex items-end gap-2.5 px-2 bg-slate-50 rounded-2xl p-3 border border-slate-200">
                      {[25, 45, 65, 90, 85, 100].map((h, i) => (
                        <div
                          key={i}
                          className={`flex-grow rounded-t-lg transition-all ${
                            i === 5 ? 'bg-indigo-600 shadow-sm' : 'bg-indigo-300'
                          }`}
                          style={{ height: `${h}%` }}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                  <span>Standard Benchmark: 70%</span>
                  <span className="font-bold text-indigo-600">+14% Over Benchmark</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Ready to Test CTA */}
        <section className="py-20 px-6 bg-gradient-to-r from-indigo-50 via-white to-sky-50 border-t border-slate-200 reveal text-center">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-3xl md:text-4xl font-black text-slate-900 tracking-tight mb-4">
              Ready to Test Your Placement Readiness?
            </h2>
            <p className="text-slate-600 text-sm mb-8 max-w-xl mx-auto leading-relaxed">
              Experience the integrated multi-round assessment ecosystem with realistic testing and AI-driven feedback.
            </p>
            <Link
              to="/login"
              className="px-10 py-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs uppercase tracking-wider shadow-lg shadow-indigo-600/25 transition-all inline-block"
            >
              Start Your Assessment
            </Link>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-white w-full py-10 px-8 border-t border-slate-200 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold text-xs">
              AI
            </div>
            <span className="font-bold text-slate-900">AIPlacement Assessment Platform</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#features" className="hover:text-indigo-600 transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-indigo-600 transition-colors">How It Works</a>
            <a href="#test-flow" className="hover:text-indigo-600 transition-colors">Test Flow</a>
            <Link to="/login" className="hover:text-indigo-600 transition-colors">Sign In</Link>
          </div>
          <div>
            © 2026 AIPlacement Assessment. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
