/**
 * RED tests for src/utils.ts
 *
 * Covers: esc, escAttr, escJs, trunc, sourceStyle, fetchJSON
 *
 * Edge cases: null/undefined input, empty strings, special characters,
 * unicode/emoji, negative trunc values, missing DOM elements
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { esc, escAttr, escJs, trunc, sourceStyle, applySourceStyles, fetchJSON, showToast } from '../utils'

// ---------------------------------------------------------------------------
// esc() — HTML-entity encoding
// ---------------------------------------------------------------------------

describe('esc', () => {
  it('encodes & < > "', () => {
    expect(esc('<script>alert("x&y")</script>')).toBe(
      '&lt;script&gt;alert(&quot;x&amp;y&quot;)&lt;/script&gt;',
    )
  })

  it('returns empty string for null input', () => {
    expect(esc(null)).toBe('')
  })

  it('returns empty string for undefined input', () => {
    expect(esc(undefined)).toBe('')
  })

  it('passes through plain text unchanged', () => {
    expect(esc('hello world')).toBe('hello world')
  })

  it('handles empty string', () => {
    expect(esc('')).toBe('')
  })

  it('handles numbers', () => {
    expect(esc(42)).toBe('42')
  })

  it('handles unicode and emoji', () => {
    expect(esc('中文 🌍')).toBe('中文 🌍')
  })
})

// ---------------------------------------------------------------------------
// escAttr() — attribute-value encoding
// ---------------------------------------------------------------------------

describe('escAttr', () => {
  it('encodes & " < >', () => {
    expect(escAttr('a&b"c<d>e')).toBe('a&amp;b&quot;c&lt;d&gt;e')
  })

  it('returns empty string for null', () => {
    expect(escAttr(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(escAttr(undefined)).toBe('')
  })

  it('handles empty string', () => {
    expect(escAttr('')).toBe('')
  })
})

// ---------------------------------------------------------------------------
// escJs() — JavaScript string escaping
// ---------------------------------------------------------------------------

describe('escJs', () => {
  it('escapes backslash, single quote, double quote, newline', () => {
    const result = escJs("it's a \"test\"\nwith\\backslash")
    expect(result).toContain("\\'")
    expect(result).toContain('\\"')
    expect(result).toContain('\\n')
    expect(result).toContain('\\\\')
  })

  it('returns empty string for null', () => {
    expect(escJs(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(escJs(undefined)).toBe('')
  })

  it('handles empty string', () => {
    expect(escJs('')).toBe('')
  })
})

// ---------------------------------------------------------------------------
// trunc() — string truncation
// ---------------------------------------------------------------------------

describe('trunc', () => {
  it('truncates strings longer than max', () => {
    expect(trunc('hello world', 5)).toBe('hello…')
  })

  it('does not truncate strings shorter than max', () => {
    expect(trunc('hello', 10)).toBe('hello')
  })

  it('returns exact string when length equals max', () => {
    expect(trunc('hello', 5)).toBe('hello')
  })

  it('handles null', () => {
    expect(trunc(null, 5)).toBe('')
  })

  it('handles undefined', () => {
    expect(trunc(undefined, 5)).toBe('')
  })

  it('handles empty string', () => {
    expect(trunc('', 5)).toBe('')
  })

  it('handles zero max', () => {
    expect(trunc('hello', 0)).toBe('…')
  })

  it('handles negative max', () => {
    expect(trunc('hello', -1)).toBe('…')
  })
})

// ---------------------------------------------------------------------------
// sourceStyle() — hash-based color assignment
// ---------------------------------------------------------------------------

describe('sourceStyle', () => {
  it('returns a CSS style string with background and color', () => {
    const style = sourceStyle('ecc')
    expect(style).toMatch(/^background:/)
    expect(style).toMatch(/;color:/)
  })

  it('returns consistent colors for the same source', () => {
    expect(sourceStyle('ecc')).toBe(sourceStyle('ecc'))
  })

  it('returns different colors for different sources (likely, not guaranteed)', () => {
    const colors = new Set(Array.from({ length: 20 }, (_, i) => sourceStyle(`source-${i}`)))
    expect(colors.size).toBeGreaterThan(1)
  })

  it('handles empty string', () => {
    const style = sourceStyle('')
    expect(style).toMatch(/^background:/)
  })

  it('handles unicode source names', () => {
    const style = sourceStyle('中文源')
    expect(style).toMatch(/^background:/)
  })
})

// ---------------------------------------------------------------------------
// applySourceStyles()
// ---------------------------------------------------------------------------

describe('applySourceStyles', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('sets style attributes on .source-tag elements', () => {
    document.body.innerHTML = '<span class="source-tag ecc">ecc</span>'
    applySourceStyles()
    const el = document.querySelector('.source-tag') as HTMLElement
    expect(el.getAttribute('style')).toMatch(/^background:/)
  })

  it('does nothing when no .source-tag elements exist', () => {
    expect(() => applySourceStyles()).not.toThrow()
  })

  it('works with a custom root element', () => {
    const root = document.createElement('div')
    root.innerHTML = '<span class="source-tag custom">custom</span>'
    applySourceStyles(root)
    const el = root.querySelector('.source-tag') as HTMLElement
    expect(el.getAttribute('style')).toMatch(/^background:/)
  })
})

// ---------------------------------------------------------------------------
// fetchJSON()
// ---------------------------------------------------------------------------

describe('fetchJSON', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('returns parsed JSON on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: 'hello' }),
    } as Response)

    const result = await fetchJSON('/api/test')
    expect(result).toEqual({ data: 'hello' })
  })

  it('throws on non-ok response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    } as Response)

    await expect(fetchJSON('/api/test')).rejects.toThrow('404')
  })

  it('throws on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Network failure'))
    await expect(fetchJSON('/api/test')).rejects.toThrow('Network failure')
  })
})

// ---------------------------------------------------------------------------
// showToast()
// ---------------------------------------------------------------------------

describe('showToast', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('sets toast text and class when #toast exists', () => {
    document.body.innerHTML = '<div id="toast"></div>'
    showToast('Test message', 'success')
    const t = document.getElementById('toast')!
    expect(t.textContent).toBe('Test message')
    expect(t.className).toContain('success')
    expect(t.className).toContain('show')
  })

  it('does not throw when #toast is missing', () => {
    expect(() => showToast('msg', 'error')).not.toThrow()
  })

  it('clears previous timer and sets new one', () => {
    document.body.innerHTML = '<div id="toast"></div>'
    showToast('first', 'success')
    showToast('second', 'error')
    const t = document.getElementById('toast')!
    expect(t.textContent).toBe('second')
  })
})
