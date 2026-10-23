with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find('                        {/* retell_hosted: show transcript during CONNECTING')
end = content.find('                        )}\n                        \n                        {roomState === STATES.COMPLETE', start)
old_block = content[start:end]

new_block = (
    "                        {/* retell_hosted: show transcript during CONNECTING if we have live updates or are waiting */}\n"
    "                        {voiceMode === 'retell_hosted' && roomState === STATES.CONNECTING && (\n"
    "                            <div \n"
    "                                ref={transcriptContainerRef}\n"
    "                                onScroll={handleTranscriptScroll}\n"
    "                                className=\"mb-6 p-4 bg-slate-800/50 rounded-xl border border-slate-700\"\n"
    "                            >\n"
    "                                <div className=\"flex items-center justify-between mb-3\">\n"
    "                                    <p className=\"text-xs font-bold text-slate-500 uppercase tracking-wider\">Live Conversation</p>\n"
    "                                    <span className=\"text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded\">\n"
    "                                        {liveTranscript.length} messages\n"
    "                                    </span>\n"
    "                                </div>\n"
    "                                <div className=\"space-y-2 max-h-60 overflow-y-auto\">\n"
    "                                    {liveTranscript.length > 0 ? (\n"
    "                                        liveTranscript.map((utt, idx) => {\n"
    "                                            const isUser = utt.speaker === 'candidate';\n"
    "                                            const isFinal = utt.is_final !== false;\n"
    "                                            const stableKey = utt.turn_id || `${utt.speaker}-${idx}`;\n"
    "                                            return (\n"
    "                                                <div \n"
    "                                                    key={stableKey}\n"
    "                                                    className={`flex gap-3 animate-slide-in ${!isFinal ? 'opacity-70' : ''}`}\n"
    "                                                >\n"
    "                                                    <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${\n"
    "                                                        isUser \n"
    "                                                            ? 'bg-blue-600/20 border border-blue-500/30' \n"
    "                                                            : 'bg-purple-600/20 border border-purple-500/30'\n"
    "                                                    }`}>\n"
    "                                                        {isUser ? (\n"
    "                                                            <svg className=\"w-4 h-4 text-blue-400\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">\n"
    "                                                                <path strokeLinecap=\"round\" strokeLinejoin=\"round\" strokeWidth={2} d=\"M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z\" />\n"
    "                                                            </svg>\n"
    "                                                        ) : (\n"
    "                                                            <svg className=\"w-4 h-4 text-purple-400\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">\n"
    "                                                                <path strokeLinecap=\"round\" strokeLinejoin=\"round\" strokeWidth={2} d=\"M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 002-2H5a2 2 0 002 2v10a2 2 0 002 2z\" />\n"
    "                                                            </svg>\n"
    "                                                        )}\n"
    "                                                    </div>\n"
    "                                                    \n"
    "                                                    <div className=\"flex-1 min-w-0\">\n"
    "                                                        <div className=\"flex items-baseline gap-2 mb-1\">\n"
    "                                                            <span className={`text-xs font-semibold ${isUser ? 'text-blue-300' : 'text-purple-300'`}>\n"
    "                                                                {isUser ? 'You' : 'Interviewer'}\n"
    "                                                            </span>\n"
    "                                                            <span className=\"text-[10px] text-slate-500 uppercase tracking-wider\">\n"
    "                                                                {utt.message_type || (isUser ? 'ANSWER' : 'QUESTION')}\n"
    "                                                            </span>\n"
    "                                                            {!isFinal && (\n"
    "                                                                <span className=\"text-[10px] text-amber-400 animate-pulse flex items-center gap-1\">\n"
    "                                                                    <span className=\"w-1.5 h-1.5 rounded-full bg-amber-400\"></span>\n"
    "                                                                    Transcribing...\n"
    "                                                                </span>\n"
    "                                                            )}\n"
    "                                                        </div>\n"
    "                                                        <p className={`text-sm leading-relaxed ${isUser ? 'text-blue-200' : 'text-purple-200'} break-words`}>\n"
    "                                                            {utt.text}\n"
    "                                                        </p>\n"
    "                                                    </div>\n"
    "                                                </div>\n"
    "                                            );\n"
    "                                        })\n"
    "                                    ) : (\n"
    "                                        <div className=\"text-center text-slate-500 py-8\">\n"
    "                                            <svg className=\"w-10 h-10 mx-auto text-slate-700 mb-2\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">\n"
    "                                                <path strokeLinecap=\"round\" strokeLinejoin=\"round\" strokeWidth={1.5} d=\"M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z\" />\n"
    "                                            </svg>\n"
    "                                            <p className=\"text-sm\">Connecting to interviewer...</p>\n"
    "                                            <p className=\"text-[11px] text-slate-600 mt-1\">Transcript will appear here once the conversation starts.</p>\n"
    "                                        </div>\n"
    "                                    )}\n"
    "                                </div>\n"
    "                            </div>\n"
    "                        )}"
)

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS: Replaced content')
else:
    print('FAILED: Old block not found exactly')
    print('Old block start:', repr(old_block[:100]))
    print('Expected start:', repr("                        {/* retell_hosted: show transcript during CONNECTING"))