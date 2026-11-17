// Run with: node --test frontend-web/src/lib/errors.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, describeError, safeRedirectPath } from './errors.js';

test('offline fetch failure says offline', () => {
  assert.equal(
    describeError(new TypeError('Failed to fetch')),
    "You appear to be offline or the server can't be reached. Check your connection and try again."
  );
});

test('timeout / abort says it took too long', () => {
  const abort = new DOMException('signal is aborted without reason', 'AbortError');
  assert.equal(describeError(abort), 'That took too long. Please try again.');
});

test('401 says signed out', () => {
  assert.equal(describeError(new ApiError(401, 'x')), "You've been signed out. Please sign in again.");
});

test('403 says not allowed', () => {
  assert.equal(describeError(new ApiError(403, 'x')), "You don't have permission to do that.");
});

test('404 says not found', () => {
  assert.equal(describeError(new ApiError(404, 'x')), "That couldn't be found. It may have been removed.");
});

test('408 and 429 say try again shortly', () => {
  assert.equal(describeError(new ApiError(429, 'x')), 'Too many requests. Wait a moment and try again.');
  assert.equal(describeError(new ApiError(408, 'x')), 'Too many requests. Wait a moment and try again.');
});

test('422 with a readable string detail shows it', () => {
  assert.equal(describeError(new ApiError(422, 'Name already exists')), 'Name already exists');
});

test('422 with a list of field errors shows the first message', () => {
  const detail = [{ loc: ['body', 'name'], msg: 'Field required' }];
  assert.equal(describeError(new ApiError(422, detail)), 'Field required');
});

test('422 with unreadable detail falls back', () => {
  assert.equal(describeError(new ApiError(422, { weird: true })), "Some of that wasn't accepted. Check what you entered and try again.");
});

test('400 behaves like 422', () => {
  assert.equal(describeError(new ApiError(400, 'Bad date')), 'Bad date');
});

test('5xx says server problem', () => {
  assert.equal(describeError(new ApiError(500, 'boom')), 'Something went wrong on the server. Please try again in a moment.');
  assert.equal(describeError(new ApiError(502, 'x')), 'Something went wrong on the server. Please try again in a moment.');
});

test('unknown things get a generic line and never leak raw text', () => {
  assert.equal(describeError(new Error('Traceback: secret stuff')), 'Something went wrong. Please try again.');
  assert.equal(describeError('weird'), 'Something went wrong. Please try again.');
  assert.equal(describeError(undefined), 'Something went wrong. Please try again.');
});

test('safeRedirectPath only allows the app\'s own paths', () => {
  assert.equal(safeRedirectPath('/mood-log?x=1'), '/mood-log?x=1');
  assert.equal(safeRedirectPath('//evil.example'), '/mood-entry');
  assert.equal(safeRedirectPath('https://evil.example'), '/mood-entry');
  assert.equal(safeRedirectPath('/\\evil.example'), '/mood-entry');
  assert.equal(safeRedirectPath(null), '/mood-entry');
  assert.equal(safeRedirectPath('/login'), '/mood-entry');
});
