with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\services\interviewService.js', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find the class definition and export position
class_start = content.find('class RetellWebCallClient {')
export_pos = content.find('export const retellClient = new RetellWebCallClient();')

if class_start != -1 and export_pos != -1:
    new_class = """class RetellWebCallClient {
    constructor() {
        this.client = null;
        this.onTranscriptCallback = null;
        this.onCallEndedCallback = null;
        this.onErrorCallback = null;
    }

    /**
     * Normalize transcript data to expected format:
     * [{ role: 'agent'|'user', content: string, is_final?: boolean, utterance_id?: string }]
     */
    static _normalizeTranscript(transcript) {
        // If already array of utterances with role/content, return as is
        if (Array.isArray(transcript)) {
            return transcript.map(u => ({
                role: u.role === 'assistant' ? 'agent' : u.role,
                content: u.content || u.text || '',
                is_final: u.is_final !== false,
                utterance_id: u.utterance_id || u.id
            }));
        }
        // If object with utterances property
        if (transcript && transcript.utterances && Array.isArray(transcript.utterances)) {
            return transcript.utterances.map(u => ({
                role: u.role === 'assistant' ? 'agent' : u.role,
                content: u.content || u.text || '',
                is_final: u.is_final !== false,
                utterance_id: u.utterance_id || u.id
            }));
        }
        // Fallback
        return [];
    }

    /**
     * Initialize a new Web Call with Retell
     */
    async initialize(callId, accessToken, iceServers) {
        // Create Retell Web Client (legacy, but works with access token)
        this.client = new RetellWebClient();

        // Set up event listeners on the client
        this.client.on('callReady', (analyzer) => {
            console.log('Retell call ready, analyzer:', !!analyzer);
        });

        // Legacy RetellWebClient emits 'transcript' events directly
        this.client.on('transcript', (transcript) => {
            console.log('Retell SDK transcript event:', transcript);
            if (this.onTranscriptCallback) {
                this.onTranscriptCallback(RetellWebCallClient._normalizeTranscript(transcript));
            }
        });

        // Also listen for update events (partial transcripts)
        this.client.on('update', (update) => {
            console.log('Retell SDK update event:', update);
            if (update.transcript && this.onTranscriptCallback) {
                this.onTranscriptCallback(RetellWebCallClient._normalizeTranscript(update.transcript));
            }
        });

        this.client.on('transcript_update', (transcript) => {
            console.log('Retell SDK transcript_update event:', transcript);
            if (this.onTranscriptCallback) {
                this.onTranscriptCallback(RetellWebCallClient._normalizeTranscript(transcript));
            }
        });

        this.client.on('data', (event) => {
            console.log('Retell SDK data event:', JSON.stringify(event).substring(0, 500));
            // Handle transcript updates - multiple possible event types
            if ((event.type === 'transcript' || event.type === 'update' || event.type === 'transcript_update') && event.transcript) {
                if (this.onTranscriptCallback) {
                    this.onTranscriptCallback(RetellWebCallClient._normalizeTranscript(event.transcript));
                }
            }
        });

        this.client.on('disconnected', () => {
            console.log('Retell SDK disconnected');
            if (this.onCallEndedCallback) this.onCallEndedCallback({});
        });

        this.client.on('error', (error) => {
            console.error('Retell SDK error:', error);
            if (this.onErrorCallback) this.onErrorCallback(error);
        });

        // Also listen for other possible events
        this.client.on('agent_start_talking', () => console.log('Agent started talking'));
        this.client.on('agent_stop_talking', () => console.log('Agent stopped talking'));
        this.client.on('metadata', (meta) => console.log('Metadata:', meta));
        this.client.on('call_ended', (data) => console.log('Call ended event:', JSON.stringify(data)));
        this.client.on('end', (data) => console.log('End event:', JSON.stringify(data)));

        // Store connection config for startCall
        // Backend returns transport: "gateway" - must specify explicitly
        this._callConfig = {
            accessToken,
            callId,
            transport: 'gateway',
            iceServers: iceServers || [{ urls: 'stun:stun.l.google.com:19302' }],
        };

        console.log('Retell SDK initialized for call:', callId);
        return this;
    }

    /**
     * Start the call (connects WebSocket, WebRTC, starts audio)
     */
    async startCall() {
        if (!this.client || !this._callConfig) {
            throw new Error('Client not initialized. Call initialize() first.');
        }

        try {
            await this.client.startCall(this._callConfig);
            console.log('Retell call started');
        } catch (error) {
            console.error('Failed to start Retell call:', error);
            throw error;
        }
    }

    /**
     * Stop and end the call
     */
    async endCall() {
        if (this.client) {
            try {
                this.client.stopCall();
                console.log('Retell call ended');
            } catch (error) {
                console.error('Error ending call:', error);
            }
        }
    }

    /**
     * Mute/unmute microphone
     */
    setMuted(muted) {
        if (this.client) {
            if (muted) {
                this.client.mute();
            } else {
                this.client.unmute();
            }
        }
    }

    // Event callbacks
    onTranscript(callback) { this.onTranscriptCallback = callback; }
    onCallEnded(callback) { this.onCallEndedCallback = callback; }
    onError(callback) { this.onErrorCallback = callback; }
}"""

# Find the class start and export position
class_start = content.find('class RetellWebCallClient {')
export_pos = content.find('export const retellClient = new RetellWebCallClient();')

if class_start != -1 and export_pos != -1:
    new_content = content[:class_start] + new_class + '\n\n' + content[export_pos:]
    with open(r'D:\\Projects\\EDI 4\\Multi-Round-Assesment-v8n\\frontend\\src\\services\\interviewService.js', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Replaced class definition')
else:
    print('Could not find class or export')