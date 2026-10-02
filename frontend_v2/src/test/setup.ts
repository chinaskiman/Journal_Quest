import '@testing-library/jest-dom/vitest'

// jsdom does not implement matchMedia; the reduced-motion CSS and any future
// JS media queries need this shim.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}

// Tests run with fake timers off by default; keep real timers so TanStack
// Query retries and toast timeouts behave predictably.
