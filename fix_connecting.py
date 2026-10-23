with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

old = """retell_hosted: show transcript during CONNECTING if we have live updates */}
                        {voiceMode === 'retell_hosted' && roomState === STATES.CONNECTING && liveTranscript.length > 0 && (
                            <div 
                                ref={transcriptContainerRef}
                                onScroll={handleTranscriptScroll}
                                className="mb-6 p-4 bg-slate-800/50 rounded-xl border border-slate-700"
                            >
                                <div className="flex items-center justify-between mb-3">
                                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Live Conversation</p>
                                    <span className="text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">
                                        {liveTranscript.length} messages
                                    </span>
                                </div>
                                <div className="space-y-2 max-h-60 overflow-y-auto">
                                    {liveTranscript.map((utt, idx) => {
                                        const isUser = utt.speaker === 'candidate';
                                        const isFinal = utt.is_final !== false;
                                        return (
                                            <div 
                                                key={`${utt.turn_id || idx}-${utt.speaker}`}
                                                className={`flex gap-3 animate-slide-in ${!isFinal ? 'opacity-70' : ''}`}
                                            >
                                                <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                                                    isUser 
                                                        ? 'bg-blue-600/20 border border-blue-500/30' 
                                                        : 'bg-purple-600/20 border border-purple-500/30'
                                                }`}>
                                                    {isUser ? (
                                                        <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                        </svg>
                                                    ) : (
                                                        <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 002-2H5a2 2 0 002 2v10a2 2 0 002 2z" />
                                                        </svg>
                                                    )}
                                                </div>
                                                
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-baseline gap-2 mb-1">
                                                        <span className={`text-xs font-semibold ${isUser ? 'text-blue-300' : 'text-purple-300'}`}>
                                                            {isUser ? 'You' : 'Interviewer'}
                                                        </span>
                                                        <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                                                            {utt.message_type || (isUser ? 'ANSWER' : 'QUESTION')}
                                                        </span>
                                                        {!isFinal && (
                                                            <span className="text-[10px] text-amber-400 animate-pulse flex items-center gap-1">
                                                                <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                                                                Transcribing...
                                                            </span>
                                                        )}
                                                    </div>
                                                    <p className={`text-sm leading-relaxed ${isUser ? 'text-blue-200' : 'text-purple-200'} break-words`}>
                                                        {utt.text}
                                                    </p>
                                                </div>
                                            </div>
                                        );
                                    })}}
                                </div>
                            </div>
                        )}"""

new = """retell_hosted: show transcript during CONNECTING if we have live updates or are waiting */}
                        {voiceMode === 'retell_hosted' && roomState === STATES.CONNECTING && (
                            <div 
                                ref={transcriptContainerRef}
                                onScroll={handleTranscriptScroll}
                                className="mb-6 p-4 bg-slate-800/50 rounded-xl border border-slate-700"
                            >
                                <div className="flex items-center justify-between mb-3">
                                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Live Conversation</p>
                                    <span className="text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">
                                        {liveTranscript.length} messages
                                    </span>
                                </div>
                                <div className="space-y-2 max-h-60 overflow-y-auto">
                                    {liveTranscript.length > 0 ? (
                                        liveTranscript.map((utt, idx) => {
                                            const isUser = utt.speaker === 'candidate';
                                            const isFinal = utt.is_final !== false;
                                            const stableKey = utt.turn_id || `${utt.speaker}-${idx}`;
                                            return (
                                                <div 
                                                    key={stableKey}
                                                    className={`flex gap-3 animate-slide-in ${!isFinal ? 'opacity-70' : ''}`}
                                                >
                                                    <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                                                        isUser 
                                                            ? 'bg-blue-600/20 border border-blue-500/30' 
                                                            : 'bg-purple-600/20 border border-purple-500/30'
                                                    }`}>
                                                        {isUser ? (
                                                            <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                            </svg>
                                                        ) : (
                                                            <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 002-2H5a2 2 0 002 2v10a2 2 0 002 2z" />
                                                            </svg>
                                                        )}
                                                    </div>
                                                    
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-baseline gap-2 mb-1">
                                                            <span className={`text-xs font-semibold ${isUser ? 'text-blue-300' : 'text-purple-300'}`}>
                                                                {isUser ? 'You' : 'Interviewer'}
                                                            </span>
                                                            <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                                                                {utt.message_type || (isUser ? 'ANSWER' : 'QUESTION')}
                                                            </span>
                                                            {!isFinal && (
                                                                <span className="text-[10px] text-amber-400 animate-pulse flex items-center gap-1">
                                                                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                                                                    Transcribing...
                                                                </span>
                                                            )}
                                                        </div>
                                                        <p className={`text-sm leading-relaxed ${isUser ? 'text-blue-200' : 'text-purple-200'} break-words`}>
                                                            {utt.text}
                                                        </p>
                                                    </div>
                                                </div>
                                            );
                                        })
                                    ) : (
                                        <div className="text-center text-slate-500 py-8">
                                            <svg className="w-10 h-10 mx-auto text-slate-700 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                            </svg>
                                            <p className="text-sm">Connecting to interviewer...</p>
                                            <p className="text-[11px] text-slate-600 mt-1">Transcript will appear here once the conversation starts.</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}"""

if old in content:
    content = content.replace(old, new)
    with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS: Replaced content')
else:
    print('FAILED: Old content not found')
    for i, (o, n) in enumerate(zip(old, new)):
        if o != n:
            print(f'First diff at {i}: old={repr(o)}, new={repr(n)}')
            print('Old context:', repr(old[max(0,i-20):i+20]))
            print('New context:', repr(new[max(0,i-20):i+20]))
            break