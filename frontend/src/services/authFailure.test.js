import test from 'node:test';
import assert from 'node:assert/strict';
import { isExpiredBearerSession } from './authFailure.js';

test('recognizes the backend Bearer challenge used for an expired or invalid session', () => {
    assert.equal(isExpiredBearerSession({
        response: { status: 401, headers: { 'www-authenticate': 'Bearer' } },
    }), true);
});

test('does not treat endpoint-level unauthorized responses as session expiry without a Bearer challenge', () => {
    assert.equal(isExpiredBearerSession({ response: { status: 401, headers: {} } }), false);
    assert.equal(isExpiredBearerSession({ response: { status: 403, headers: { 'www-authenticate': 'Bearer' } } }), false);
    assert.equal(isExpiredBearerSession({ response: { status: 429, headers: {} } }), false);
    assert.equal(isExpiredBearerSession({ response: { status: 500, headers: {} } }), false);
});

test('supports Fetch-style response headers', () => {
    const headers = new Headers({ 'www-authenticate': 'Bearer realm="api"' });
    assert.equal(isExpiredBearerSession({ response: { status: 401, headers } }), true);
});
