import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// The sign-in page probes the API before enabling sign-in.  In unit tests the
// server "answers" unless a test says otherwise (see app.test.jsx).
vi.mock('../api/health', () => ({ healthApi: { ping: vi.fn(async () => true) } }));

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
});

// jsdom does not implement these browser APIs.
if (!window.matchMedia) {
  window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} });
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
