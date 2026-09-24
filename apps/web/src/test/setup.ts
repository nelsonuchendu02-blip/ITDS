import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// The Vitest config does not enable `test.globals`, so Testing Library's
// automatic per-test cleanup (which relies on detecting a global `afterEach`)
// never registers. Without this, DOM nodes from earlier tests in the same
// file remain mounted and later `getByRole`/`getByText` queries can match
// multiple elements across tests.
afterEach(() => {
  cleanup()
})
