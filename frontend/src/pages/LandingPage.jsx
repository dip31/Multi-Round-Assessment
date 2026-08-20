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
    `relative z-10 transition-colors ${
      highlightedSection === sectionId
        ? 'text-zinc-100 font-semibold'
        : 'text-zinc-400 hover:text-zinc-100'
    }`
  );

  useEffect(() => {
    // Add dynamic styles for animations
    const style = document.createElement('style');
    style.innerHTML = `
      @keyframes aurora {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
      }

      @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-20px); }
      }

      @keyframes pulse-glow {
        0%, 100% { box-shadow: 0 0 20px rgba(186, 158, 255, 0.1); }
        50% { box-shadow: 0 0 50px rgba(186, 158, 255, 0.3); }
      }

      .reveal {
        opacity: 0;
        transform: translateY(30px);
        transition: all 0.8s cubic-bezier(0.2, 1, 0.3, 1);
      }

      .reveal.active {
        opacity: 1;
        transform: translateY(0);
      }

      .aurora-bg {
        background: linear-gradient(-45deg, #0e0e10, #1a0b2e, #0e0e10, #051a24);
        background-size: 400% 400%;
        animation: aurora 20s ease infinite;
      }

      .animate-float {
        animation: float 6s ease-in-out infinite;
      }

      .animate-pulse-glow {
        animation: pulse-glow 4s ease-in-out infinite;
      }

      .stagger-item { 
        opacity: 0; 
        transform: translateY(20px); 
      }
      
      .active .stagger-item {
        opacity: 1;
        transform: translateY(0);
        transition: all 0.6s cubic-bezier(0.2, 1, 0.3, 1);
      }

      .card-hover:hover {
        transform: translateY(-8px) scale(1.02);
        border-color: rgba(186, 158, 255, 0.4);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 20px rgba(186, 158, 255, 0.1);
      }

      .step-line-container {
        position: absolute;
        top: 48px;
        left: 0;
        width: 100%;
        height: 2px;
        background: rgba(72, 71, 74, 0.2);
        z-index: 0;
      }

      .step-line-progress {
        height: 100%;
        background: linear-gradient(to right, #ba9eff, #2db7f2);
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

    // Intersection Observer for reveal animations
    const observerOptions = {
      threshold: 0.15,
      rootMargin: "0px 0px -50px 0px"
    };

    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('active');
          
          // Special handling for the How It Works line
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

    // Initial Hero Trigger
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
    <div className="bg-background text-on-surface font-body selection:bg-primary/30 antialiased min-h-screen flex flex-col aurora-bg">
      {/* Top Navigation Bar */}
      <nav className="fixed top-0 w-full z-50 bg-zinc-950/60 backdrop-blur-xl border-b border-zinc-800/20 shadow-2xl shadow-violet-900/10 font-['Inter'] antialiased tracking-tight">
        <div className="flex justify-between items-center px-6 py-4 max-w-7xl mx-auto">
          <div className="text-2xl font-black tracking-tighter text-zinc-100">AIPlacement</div>
          <div className="hidden md:block w-[25rem]">
            <div
              className="relative grid grid-cols-3 items-center"
              onMouseLeave={() => setHoveredSection('')}
            >
              <div
                className="absolute bottom-[-8px] left-0 h-[2px] bg-primary rounded-full transition-all duration-300 ease-out"
                style={{
                  width: '33.3333%',
                  transform: `translateX(${Math.max(highlightedNavIndex, 0) * 100}%)`,
                  opacity: highlightedNavIndex === -1 ? 0 : 1
                }}
              />
              {navItems.map((item) => (
                <a
                  key={item.id}
                  className={`${navLinkClass(item.id)} text-center py-1`}
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
            className="bg-primary text-on-primary-container px-6 py-2 rounded-full font-semibold hover:bg-primary-container active:scale-95 transition-all duration-200"
          >
            Start Assessment
          </Link>
        </div>
      </nav>

      <main className="pt-24 flex-grow">
        {/* Hero Section */}
        <section className="relative overflow-hidden px-6 pt-16 pb-24 md:pt-32 md:pb-48">
          {/* Background Glows */}
          <div className="absolute top-[-10%] right-[-10%] w-[500px] h-[500px] bg-primary/20 rounded-full blur-[120px] pointer-events-none"></div>
          <div className="absolute bottom-[-10%] left-[-10%] w-[500px] h-[500px] bg-secondary/10 rounded-full blur-[120px] pointer-events-none"></div>
          <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-16 items-center flex-grow">
            <div className="lg:col-span-6 z-10">
              <h1 className="reveal text-5xl md:text-7xl font-headline font-black tracking-tighter text-on-surface leading-[1.1] mb-6">
                AI-Driven Placement Assessment Platform
              </h1>
              <p className="reveal text-lg md:text-xl text-on-surface-variant max-w-xl mb-10 leading-relaxed">
                Simulate real placement rounds with adaptive testing powered by reinforcement learning. Elevate your potential with data-backed insights.
              </p>
              <div className="reveal flex flex-wrap gap-4">
                <Link
                  to="/login"
                  className="hero-gradient px-8 py-4 rounded-full text-on-primary font-bold shadow-lg shadow-primary/20 active:scale-95 transition-all duration-300 hover:shadow-[0_0_25px_rgba(186,158,255,0.4)]"
                >
                  Start Assessment
                </Link>
                <a
                  href="#features"
                  className="bg-transparent border border-outline-variant/30 hover:bg-surface-container-high px-8 py-4 rounded-full text-on-surface font-semibold transition-all duration-300 inline-block text-center hover:border-primary/50"
                >
                  Learn More
                </a>
              </div>
            </div>
            
            <div className="lg:col-span-6 relative group reveal">
              <div className="absolute -inset-1 bg-gradient-to-r from-primary/30 to-secondary/30 rounded-xl blur opacity-25 group-hover:opacity-50 transition duration-1000"></div>
              <div className="relative rounded-xl overflow-hidden glass-panel border border-outline-variant/20 shadow-2xl animate-float animate-pulse-glow">
                <img
                  className="w-full aspect-video object-cover"
                  alt="Modern dark dashboard interface displaying complex data visualization charts, neural network graphs, and clean software assessment UI"
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuA42fU8GCOlbjWyBhmhmsj9ps3V9j9BisRD2psOw-4LUJK8tFkW6SHjTENtRr9Se5i6uzuVf5MDxE9R9wtt2nobnm3DOjuKVrj4KoaV7hlW8eyXOOIh1eZtEDF0IXTxdiwNf92no8Y46yvmSXT466djCrj4w6AAKLfwr-C26QCZynSDjE_6ThQMsq3T-yFkeDlQ7VnFHgw6LZAGUK3LGNTG7YpD_MdrmUym8D8aUcSRpYt3EclC1wh3wE94PwuzRAweY_XmmnsDKYCY"
                />
              </div>
            </div>
          </div>
        </section>

        {/* Features Section (Bento Grid) */}
        <section id="features" className="py-24 px-6 bg-surface-container-low reveal scroll-mt-28">
          <div className="max-w-7xl mx-auto">
            <div className="mb-16 stagger-item">
              <span className="text-secondary font-label tracking-[0.2em] uppercase text-sm mb-4 block">Capabilities</span>
              <h2 className="text-4xl font-headline font-bold text-on-surface">Powerful Assessment Engine</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 md:grid-rows-2 gap-6">
              {/* Feature 1: Large */}
              <div className="md:col-span-2 bg-surface-container p-10 rounded-xl transition-all duration-500 card-hover border border-transparent stagger-item">
                <span className="material-symbols-outlined text-primary text-4xl mb-6">psychology</span>
                <h3 className="text-2xl font-bold mb-4">Adaptive Testing</h3>
                <p className="text-on-surface-variant text-lg leading-relaxed max-w-lg">
                  Every answer changes what comes next. If you solve quickly and correctly, the next questions become more challenging. If you struggle, the platform gives foundational questions to recover confidence and accuracy.
                </p>
              </div>
              
              {/* Feature 2: Tall */}
              <div className="md:row-span-2 bg-surface-container p-10 rounded-xl transition-all duration-500 card-hover border border-transparent stagger-item">
                <span className="material-symbols-outlined text-secondary text-4xl mb-6">analytics</span>
                <h3 className="text-2xl font-bold mb-4">Performance Analytics</h3>
                <p className="text-on-surface-variant leading-relaxed">
                  Get round-wise insights for aptitude, coding, and interview stages. Track accuracy, response speed, confidence trend, and time allocation so you know exactly where to improve before real placements.
                </p>
                <div className="mt-8 space-y-4">
                  <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden">
                    <div className="h-full bg-primary progress-fill" style={{ '--final-width': '75%' }}></div>
                  </div>
                  <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden">
                    <div className="h-full bg-secondary progress-fill" style={{ '--final-width': '50%' }}></div>
                  </div>
                </div>
              </div>
              
              {/* Feature 3 */}
              <div className="bg-surface-container p-10 rounded-xl transition-all duration-500 card-hover border border-transparent stagger-item">
                <span className="material-symbols-outlined text-tertiary text-4xl mb-6">layers</span>
                <h3 className="text-xl font-bold mb-3">Multi-Round Assessment</h3>
                <p className="text-on-surface-variant text-sm">Follow a complete hiring simulation from aptitude to coding to AI interview. Each stage has realistic constraints and scoring logic aligned with placement processes.</p>
              </div>
              
              {/* Feature 4 */}
              <div className="bg-surface-container p-10 rounded-xl transition-all duration-500 card-hover border border-transparent stagger-item">
                <span className="material-symbols-outlined text-error text-4xl mb-6">security</span>
                <h3 className="text-xl font-bold mb-3">Proctoring System</h3>
                <p className="text-on-surface-variant text-sm">Camera, tab-switch, and activity checks protect test integrity. You receive clear warnings in-session so you can stay compliant and complete the test smoothly.</p>
              </div>
            </div>
          </div>
        </section>

        {/* How It Works Section */}
        <section id="how-it-works" className="py-24 px-6 bg-surface reveal scroll-mt-28">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-20 stagger-item">
              <h2 className="text-4xl font-headline font-bold text-on-surface mb-4">Your Path to Success</h2>
              <p className="text-on-surface-variant max-w-2xl mx-auto">The complete project flow: Test Round first, then Coding Round, then Interview Round, followed by your final evaluation report.</p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-12 relative">
              {/* Connecting Line */}
              <div className="hidden md:block step-line-container">
                <div className="step-line-progress" id="scroll-line"></div>
              </div>
              
              {/* Step 1 */}
              <div className="relative z-10 flex flex-col items-center text-center stagger-item">
                <div className="w-24 h-24 rounded-full bg-surface-container border border-primary/30 flex items-center justify-center mb-6 shadow-xl shadow-primary/5">
                  <span className="text-2xl font-bold text-primary">01</span>
                </div>
                <h4 className="font-bold mb-3">Test Round (Aptitude)</h4>
                <p className="text-sm text-on-surface-variant leading-relaxed">Start with the aptitude test round. Solve objective questions within time limits; this stage evaluates fundamentals, speed, and accuracy.</p>
              </div>
              
              {/* Step 2 */}
              <div className="relative z-10 flex flex-col items-center text-center stagger-item">
                <div className="w-24 h-24 rounded-full bg-surface-container border border-secondary/30 flex items-center justify-center mb-6 shadow-xl shadow-secondary/5">
                  <span className="text-2xl font-bold text-secondary">02</span>
                </div>
                <h4 className="font-bold mb-3">Coding Round</h4>
                <p className="text-sm text-on-surface-variant leading-relaxed">Move to the coding round and solve programming problems in the editor. Your logic, correctness, and code quality are assessed here.</p>
              </div>
              
              {/* Step 3 */}
              <div className="relative z-10 flex flex-col items-center text-center stagger-item">
                <div className="w-24 h-24 rounded-full bg-surface-container border border-tertiary/30 flex items-center justify-center mb-6 shadow-xl shadow-tertiary/5">
                  <span className="text-2xl font-bold text-tertiary">03</span>
                </div>
                <h4 className="font-bold mb-3">Interview Round</h4>
                <p className="text-sm text-on-surface-variant leading-relaxed">Enter the AI interview round with role-based technical and behavioral prompts. Follow-up questions adapt to your responses.</p>
              </div>
              
              {/* Step 4 */}
              <div className="relative z-10 flex flex-col items-center text-center stagger-item">
                <div className="w-24 h-24 rounded-full bg-surface-container border border-primary-dim/30 flex items-center justify-center mb-6 shadow-xl shadow-primary-dim/5">
                  <span className="text-2xl font-bold text-primary-dim">04</span>
                </div>
                <h4 className="font-bold mb-3">Final Report</h4>
                <p className="text-sm text-on-surface-variant leading-relaxed">Receive your consolidated performance report with round-wise scores, strengths, weaknesses, and recommended next steps.</p>
              </div>
            </div>

            <div className="mt-14 flex flex-wrap justify-center gap-4 stagger-item">
              <a
                href="#test-flow"
                className="bg-primary text-on-primary-container px-8 py-3 rounded-full font-semibold hover:bg-primary-container active:scale-95 transition-all duration-200"
              >
                View Full Test Flow
              </a>
              <Link
                to="/login"
                className="border border-outline-variant/40 text-on-surface px-8 py-3 rounded-full font-semibold hover:border-primary/50 hover:bg-surface-container-high active:scale-95 transition-all duration-200"
              >
                Start Assessment
              </Link>
            </div>
          </div>
        </section>

        {/* Test Flow Section */}
        <section id="test-flow" className="py-24 px-6 bg-surface-container-low reveal scroll-mt-28">
          <div className="max-w-5xl mx-auto">
            <div className="mb-12 text-center stagger-item">
              <h2 className="text-4xl font-headline font-bold text-on-surface mb-4">How to Give the Test</h2>
              <p className="text-on-surface-variant max-w-3xl mx-auto">
                Use this exact sequence on test day so you can complete every round without confusion.
              </p>
            </div>

            <div className="space-y-5">
              <div className="stagger-item bg-surface-container rounded-xl border border-outline-variant/30 p-6">
                <h3 className="text-lg font-semibold mb-2 text-on-surface">1. Login and open your assessment slot</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">Sign in with your registered account, open the active test from dashboard, and read round instructions carefully before clicking begin.</p>
              </div>
              <div className="stagger-item bg-surface-container rounded-xl border border-outline-variant/30 p-6">
                <h3 className="text-lg font-semibold mb-2 text-on-surface">2. Complete system checks</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">Allow camera and microphone access, keep your face visible, and avoid tab switching so proctoring can verify your session properly.</p>
              </div>
              <div className="stagger-item bg-surface-container rounded-xl border border-outline-variant/30 p-6">
                <h3 className="text-lg font-semibold mb-2 text-on-surface">3. Attempt aptitude round</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">Answer objective questions within the timer. Focus on both correctness and speed because both impact your score profile.</p>
              </div>
              <div className="stagger-item bg-surface-container rounded-xl border border-outline-variant/30 p-6">
                <h3 className="text-lg font-semibold mb-2 text-on-surface">4. Attempt coding round</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">Solve coding tasks in the editor, run checks, and submit final solutions. Difficulty adjusts based on prior performance and code quality.</p>
              </div>
              <div className="stagger-item bg-surface-container rounded-xl border border-outline-variant/30 p-6">
                <h3 className="text-lg font-semibold mb-2 text-on-surface">5. Attend AI interview round</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">Respond to role-specific interview prompts clearly and concisely. The interview engine asks follow-up questions from your previous answers.</p>
              </div>
              <div className="stagger-item bg-surface-container rounded-xl border border-outline-variant/30 p-6">
                <h3 className="text-lg font-semibold mb-2 text-on-surface">6. Review results and next actions</h3>
                <p className="text-on-surface-variant text-sm leading-relaxed">Download your report, review weak topics, and use recommendations to plan your next practice attempt.</p>
              </div>
            </div>

            <div className="mt-10 text-center stagger-item">
              <Link
                to="/login"
                className="hero-gradient px-10 py-4 rounded-full text-on-primary font-bold shadow-lg shadow-primary/20 active:scale-95 transition-all duration-300 hover:shadow-[0_0_25px_rgba(186,158,255,0.4)] inline-block"
              >
                Go to Login and Start
              </Link>
            </div>
          </div>
        </section>

        {/* Product Preview Section */}
        <section className="py-24 px-6 bg-surface-container-lowest reveal">
          <div className="max-w-7xl mx-auto">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
              
              {/* Aptitude UI Panel */}
              <div className="glass-panel rounded-2xl p-8 border border-outline-variant/20 flex flex-col h-[500px] stagger-item">
                <div className="flex items-center justify-between mb-10">
                  <div className="flex gap-2">
                    <div className="w-3 h-3 rounded-full bg-error/50"></div>
                    <div className="w-3 h-3 rounded-full bg-primary/50"></div>
                    <div className="w-3 h-3 rounded-full bg-secondary/50"></div>
                  </div>
                  <span className="text-xs font-label text-on-surface-variant uppercase tracking-widest">Question 14 / 20</span>
                </div>
                
                <div className="flex-grow">
                  <h3 className="text-xl font-bold mb-8 text-on-surface">A train traveling at 60 km/h crosses a pole in 9 seconds. What is the length of the train in meters?</h3>
                  <div className="space-y-4">
                    <label className="flex items-center p-4 bg-surface-container-high rounded-lg cursor-pointer hover:bg-surface-variant transition-colors border border-transparent hover:border-primary/20">
                      <input className="w-4 h-4 text-primary bg-background border-outline-variant focus:ring-primary" name="aptitude" type="radio" />
                      <span className="ml-4 text-on-surface">120 meters</span>
                    </label>
                    <label className="flex items-center p-4 bg-surface-container-high rounded-lg cursor-pointer hover:bg-surface-variant transition-colors border border-transparent hover:border-primary/20">
                      <input className="w-4 h-4 text-primary bg-background border-outline-variant focus:ring-primary" name="aptitude" type="radio" />
                      <span className="ml-4 text-on-surface">150 meters</span>
                    </label>
                    <label className="flex items-center p-4 bg-surface-container-high rounded-lg cursor-pointer hover:bg-surface-variant transition-colors border border-transparent hover:border-primary/20">
                      <input className="w-4 h-4 text-primary bg-background border-outline-variant focus:ring-primary" name="aptitude" type="radio" />
                      <span className="ml-4 text-on-surface">180 meters</span>
                    </label>
                  </div>
                </div>
                
                <div className="mt-8 flex justify-end">
                  <Link
                    to="/login"
                    className="bg-primary text-on-primary px-8 py-2 rounded-full font-bold flex items-center gap-2 hover:bg-primary-container transition-colors"
                  >
                    Next <span className="material-symbols-outlined text-sm">arrow_forward</span>
                  </Link>
                </div>
              </div>
              
              {/* Results Dashboard Panel */}
              <div className="glass-panel rounded-2xl p-8 border border-outline-variant/20 h-[500px] flex flex-col stagger-item">
                <div className="flex items-center gap-3 mb-8">
                  <span className="material-symbols-outlined text-secondary">bar_chart</span>
                  <span className="font-bold text-on-surface">Real-time Analytics</span>
                </div>
                <div className="grid grid-cols-2 gap-4 mb-8">
                  <div className="bg-surface-container p-6 rounded-xl text-center hover:scale-105 transition-transform duration-300">
                    <div className="text-on-surface-variant text-xs uppercase tracking-tighter mb-1">Score</div>
                    <div className="text-3xl font-black text-primary">84%</div>
                  </div>
                  <div className="bg-surface-container p-6 rounded-xl text-center hover:scale-105 transition-transform duration-300">
                    <div className="text-on-surface-variant text-xs uppercase tracking-tighter mb-1">Accuracy</div>
                    <div className="text-3xl font-black text-secondary">92%</div>
                  </div>
                </div>
                <div className="flex-grow flex flex-col justify-end">
                  <div className="mb-4 flex justify-between items-end">
                    <span className="text-xs text-on-surface-variant">Difficulty Progression</span>
                    <span className="text-xs text-primary font-bold">Level 8 (Hard)</span>
                  </div>
                  <div className="h-40 flex items-end gap-2 px-2">
                    <div className="flex-grow bg-primary/20 chart-bar rounded-t-sm" style={{ height: '25%', transitionDelay: '0.1s' }}></div>
                    <div className="flex-grow bg-primary/40 chart-bar rounded-t-sm" style={{ height: '50%', transitionDelay: '0.2s' }}></div>
                    <div className="flex-grow bg-primary/60 chart-bar rounded-t-sm" style={{ height: '75%', transitionDelay: '0.3s' }}></div>
                    <div className="flex-grow bg-primary/80 chart-bar rounded-t-sm" style={{ height: '100%', transitionDelay: '0.4s' }}></div>
                    <div className="flex-grow bg-primary chart-bar rounded-t-sm" style={{ height: '85%', transitionDelay: '0.5s' }}></div>
                    <div className="flex-grow bg-secondary chart-bar rounded-t-sm shadow-[0_-10px_20px_rgba(45,183,242,0.3)]" style={{ height: '100%', transitionDelay: '0.6s' }}></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-24 px-6 relative overflow-hidden reveal">
          <div className="absolute inset-0 bg-primary/5 opacity-40 pointer-events-none"></div>
          <div className="max-w-4xl mx-auto text-center relative z-10">
            <h2 className="text-4xl md:text-5xl font-headline font-black mb-8 text-on-surface tracking-tight stagger-item">Ready to Test Your Skills?</h2>
            <p className="text-lg text-on-surface-variant mb-12 max-w-2xl mx-auto stagger-item">Join thousands of candidates who have already leveled up their placement preparation with our AI-driven platform.</p>
            <Link
              to="/login"
              className="hero-gradient px-12 py-5 rounded-full text-on-primary text-xl font-bold shadow-2xl shadow-primary/20 hover:scale-110 transition-transform duration-300 hover:shadow-[0_0_40px_rgba(186,158,255,0.4)] inline-block stagger-item"
            >
              Start Your Assessment
            </Link>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-zinc-950 w-full py-12 px-6 border-t border-zinc-900 font-['Inter'] text-sm text-zinc-500">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-7xl mx-auto">
          <div className="space-y-4">
            <div className="text-xl font-bold text-zinc-200">AIPlacement</div>
            <p className="max-w-xs leading-relaxed">Elevating candidate standards through intelligent, adaptive assessment technology.</p>
          </div>
          <div className="flex flex-col gap-3">
            <h5 className="text-zinc-200 font-bold mb-2">Platform</h5>
            <a className="text-zinc-500 hover:text-violet-400 transition-colors" href="#">Features</a>
            <a className="text-zinc-500 hover:text-violet-400 transition-colors" href="#">How It Works</a>
            <a className="text-zinc-500 hover:text-violet-400 transition-colors" href="#">About</a>
          </div>
          <div className="flex flex-col gap-3">
            <h5 className="text-zinc-200 font-bold mb-2">Company</h5>
            <a className="text-zinc-500 hover:text-violet-400 transition-colors" href="#">Contact</a>
            <a className="text-zinc-500 hover:text-violet-400 transition-colors" href="#">Privacy Policy</a>
            <div className="mt-4 text-zinc-600">
              © 2024 AIPlacement Assessment. All rights reserved.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
