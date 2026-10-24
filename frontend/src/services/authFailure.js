export function isExpiredBearerSession(error) {
    if (error?.response?.status !== 401) return false;
    const headers = error.response.headers;
    const challenge = headers?.['www-authenticate'] ?? headers?.get?.('www-authenticate');
    return typeof challenge === 'string' && challenge.toLowerCase().includes('bearer');
}
