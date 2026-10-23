import assert from 'node:assert/strict';

// Test suite for Retell Hosted Live Transcript normalization, fingerprinting, and listener mechanics
// We test the exact normalization and deduplication contracts implemented in interviewService.js

class TestRetellWebCallClient {
    constructor() {
        this._transcriptListeners = new Set();
        this._agentStartListeners = new Set();
        this._agentStopListeners = new Set();
        this._callEndedListeners = new Set();
        this._errorListeners = new Set();
        this._lastTranscriptFingerprint = null;
    }

    static _normalizeTranscript(transcript, turntaking) {
        let rawList = transcript;
        if (!Array.isArray(rawList)) {
            if (rawList && rawList.utterances && Array.isArray(rawList.utterances)) {
                rawList = rawList.utterances;
            } else {
                return [];
            }
        }

        const relevant = [];
        for (const u of rawList) {
            if (!u) continue;
            const rawRole = String(u.role || '').toLowerCase().trim();
            const role = (rawRole === 'agent' || rawRole === 'assistant' || rawRole === 'bot')
                ? 'agent'
                : (rawRole === 'user' || rawRole === 'candidate')
                    ? 'user'
                    : null;
            if (!role) continue;

            let content = '';
            if (typeof u.content === 'string') {
                content = u.content;
            } else if (typeof u.text === 'string') {
                content = u.text;
            } else if (Array.isArray(u.words)) {
                content = u.words
                    .map(w => (typeof w === 'string' ? w : w?.word || w?.content || ''))
                    .filter(Boolean)
                    .join(' ');
            }
            content = content.trim();
            if (!content) continue;

            relevant.push({
                role,
                content,
                metadata: u.metadata || {},
            });
        }

        return relevant.map((u, idx) => {
            const contentHash = u.content.split('').reduce((h, c) => Math.imul(31, h) + c.charCodeAt(0) | 0, 0) >>> 0;
            const utteranceId = `utt-${contentHash}-${idx}`;

            const isLast = (idx === relevant.length - 1);
            let isFinal = true;
            if (isLast) {
                if (u.role === 'user' && turntaking === 'user_turn') {
                    isFinal = false;
                } else if (u.role === 'agent' && turntaking === 'agent_turn') {
                    isFinal = false;
                }
            }

            return {
                role: u.role,
                content: u.content,
                is_final: isFinal,
                utterance_id: utteranceId,
                metadata: u.metadata,
            };
        });
    }

    static _computeFingerprint(transcript, turntaking) {
        let rawList = transcript;
        if (!Array.isArray(rawList)) {
            if (rawList && rawList.utterances && Array.isArray(rawList.utterances)) {
                rawList = rawList.utterances;
            } else {
                return 'empty';
            }
        }
        if (rawList.length === 0) {
            return 'empty';
        }

        let hash = 0;
        let count = 0;
        for (const u of rawList) {
            if (!u) continue;
            const rawRole = String(u.role || '').toLowerCase().trim();
            if (rawRole !== 'agent' && rawRole !== 'user' && rawRole !== 'assistant' && rawRole !== 'candidate' && rawRole !== 'bot') {
                continue;
            }
            let content = '';
            if (typeof u.content === 'string') content = u.content;
            else if (typeof u.text === 'string') content = u.text;
            else if (Array.isArray(u.words)) {
                content = u.words.map(w => (typeof w === 'string' ? w : w?.word || w?.content || '')).filter(Boolean).join(' ');
            }
            content = content.trim();
            if (!content) continue;

            count++;
            for (let i = 0; i < content.length; i++) {
                hash = Math.imul(31, hash) + content.charCodeAt(i) | 0;
            }
        }
        if (count === 0) {
            return 'empty';
        }
        return `${count}:${hash >>> 0}:${turntaking || ''}`;
    }

    onTranscript(callback) {
        if (typeof callback !== 'function') return () => {};
        this._transcriptListeners.add(callback);
        return () => {
            this._transcriptListeners.delete(callback);
        };
    }

    simulateUpdate(update) {
        const rawTranscript = update?.transcript;
        if (!rawTranscript) return;

        const fingerprint = TestRetellWebCallClient._computeFingerprint(rawTranscript, update.turntaking);
        if (fingerprint === this._lastTranscriptFingerprint && fingerprint !== 'empty') {
            return; // Deduplicated
        }
        this._lastTranscriptFingerprint = fingerprint;

        const normalized = TestRetellWebCallClient._normalizeTranscript(rawTranscript, update.turntaking);
        if (normalized.length > 0) {
            for (const listener of this._transcriptListeners) {
                listener(normalized, update.turntaking);
            }
        }
    }
}

async function runTests() {
    console.log('--- Starting Retell Live Transcript Unit Tests ---');

    // Test 1: Receiving SDK update with agent and user utterances
    {
        const payload = [
            { role: 'agent', content: 'Welcome to the interview. Could you tell me about yourself?' },
            { role: 'user', content: 'Hi, I am a software engineer with 3 years of experience in React and Python.' }
        ];
        const normalized = TestRetellWebCallClient._normalizeTranscript(payload, 'agent_turn');
        assert.equal(normalized.length, 2);
        assert.equal(normalized[0].role, 'agent');
        assert.equal(normalized[0].is_final, true);
        assert.equal(normalized[1].role, 'user');
        assert.equal(normalized[1].is_final, true);
        console.log('✅ Test 1: Normalizes basic agent and user utterances correctly');
    }

    // Test 2: Handling interim speaker state via turntaking
    {
        const payload = [
            { role: 'agent', content: 'What is your experience with databases?' },
            { role: 'user', content: 'I have worked primarily with Postgres' }
        ];
        // User actively speaking (turntaking = 'user_turn')
        const normalizedUserSpeaking = TestRetellWebCallClient._normalizeTranscript(payload, 'user_turn');
        assert.equal(normalizedUserSpeaking[0].is_final, true);
        assert.equal(normalizedUserSpeaking[1].is_final, false); // Active speaker is interim

        // Agent actively speaking
        const agentTurnPayload = [
            { role: 'agent', content: 'Let me explain the next part' }
        ];
        const normalizedAgentSpeaking = TestRetellWebCallClient._normalizeTranscript(agentTurnPayload, 'agent_turn');
        assert.equal(normalizedAgentSpeaking[0].is_final, false); // Active agent is interim
        console.log('✅ Test 2: Derives is_final accurately from turn index and turntaking flag');
    }

    // Test 3: Normalizing wrapped payload { utterances: [...] } and words fallback
    {
        const wrapped = {
            utterances: [
                { role: 'Agent', words: [{ word: 'Hello' }, { word: 'there!' }] },
                { role: 'Candidate', text: 'Good morning.' }
            ]
        };
        const normalized = TestRetellWebCallClient._normalizeTranscript(wrapped, 'agent_turn');
        assert.equal(normalized.length, 2);
        assert.equal(normalized[0].role, 'agent');
        assert.equal(normalized[0].content, 'Hello there!');
        assert.equal(normalized[1].role, 'user');
        assert.equal(normalized[1].content, 'Good morning.');
        console.log('✅ Test 3: Handles wrapped object payloads, case-insensitive roles, and words array');
    }

    // Test 4: Deduplication of identical snapshots
    {
        const client = new TestRetellWebCallClient();
        let receivedUpdates = [];
        client.onTranscript((data) => {
            receivedUpdates.push(data);
        });

        const update1 = {
            event_type: 'update',
            transcript: [{ role: 'agent', content: 'Hello candidate' }],
            turntaking: 'agent_turn'
        };

        client.simulateUpdate(update1);
        assert.equal(receivedUpdates.length, 1);

        // Send exact duplicate
        client.simulateUpdate(update1);
        assert.equal(receivedUpdates.length, 1, 'Duplicate snapshot must be deduplicated');

        // Send mutated partial STT update (growth)
        const update2 = {
            event_type: 'update',
            transcript: [{ role: 'agent', content: 'Hello candidate, welcome to today\'s session.' }],
            turntaking: 'agent_turn'
        };
        client.simulateUpdate(update2);
        assert.equal(receivedUpdates.length, 2);
        assert.equal(receivedUpdates[1][0].content, 'Hello candidate, welcome to today\'s session.');
        console.log('✅ Test 4: Successfully deduplicates identical cumulative snapshots while allowing partial STT extensions');
    }

    // Test 5: Turntaking transition updates
    {
        const client = new TestRetellWebCallClient();
        let received = [];
        client.onTranscript((data) => {
            received.push(data);
        });

        const turn1 = {
            event_type: 'update',
            transcript: [
                { role: 'agent', content: 'Are you ready?' },
                { role: 'user', content: 'Yes I am ready' }
            ],
            turntaking: 'user_turn'
        };
        client.simulateUpdate(turn1);
        assert.equal(received.length, 1);
        assert.equal(received[0][1].is_final, false); // user speaking

        // Same text, but user finishes speaking and turntaking flips to agent_turn
        const turn2 = {
            event_type: 'update',
            transcript: [
                { role: 'agent', content: 'Are you ready?' },
                { role: 'user', content: 'Yes I am ready' }
            ],
            turntaking: 'agent_turn'
        };
        client.simulateUpdate(turn2);
        assert.equal(received.length, 2, 'Turntaking shift must not be dropped by fingerprint');
        assert.equal(received[1][1].is_final, true); // user turn finalized
        console.log('✅ Test 5: Emits update when turntaking flips from interim to final without dropping');
    }

    // Test 6: Callback subscription and cleanup (prevents memory leak and remount stale listeners)
    {
        const client = new TestRetellWebCallClient();
        let count1 = 0;
        let count2 = 0;

        const unsub1 = client.onTranscript(() => { count1++; });
        const unsub2 = client.onTranscript(() => { count2++; });
        assert.equal(client._transcriptListeners.size, 2);

        client.simulateUpdate({
            event_type: 'update',
            transcript: [{ role: 'agent', content: 'Testing listeners 1' }],
            turntaking: 'agent_turn'
        });
        assert.equal(count1, 1);
        assert.equal(count2, 1);

        // Unsubscribe listener 1 (simulate component unmount)
        unsub1();
        assert.equal(client._transcriptListeners.size, 1);

        client.simulateUpdate({
            event_type: 'update',
            transcript: [{ role: 'agent', content: 'Testing listeners 2' }],
            turntaking: 'agent_turn'
        });
        assert.equal(count1, 1, 'Unsubscribed listener must not be called');
        assert.equal(count2, 2, 'Active listener must continue receiving updates');

        unsub2();
        assert.equal(client._transcriptListeners.size, 0);
        console.log('✅ Test 6: Listener registration and unsubscribe functions work cleanly');
    }

    console.log('🎉 ALL UNIT TESTS PASSED SUCCESSFULLY!');
}

runTests().catch(err => {
    console.error('❌ Test failed:', err);
    process.exit(1);
});
