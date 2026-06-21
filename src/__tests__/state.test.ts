/**
 * RED tests for src/state.ts
 *
 * Covers: constant correctness (TYPES, WORKFLOW_MODES, SOURCES, API),
 * initial state shape.
 */

import { describe, it, expect } from 'vitest'
import { API, TYPES, WORKFLOW_MODES, SOURCES, state } from '../state'

// ---------------------------------------------------------------------------
// API base URL
// ---------------------------------------------------------------------------

describe('API constant', () => {
  it('is an empty string by default', () => {
    expect(API).toBe('')
  })
})

// ---------------------------------------------------------------------------
// TYPES
// ---------------------------------------------------------------------------

describe('TYPES constant', () => {
  it('contains exactly 7 type entries', () => {
    expect(TYPES).toHaveLength(7)
  })

  it('contains all expected type keys in order', () => {
    const keys = TYPES.map(([k]) => k)
    expect(keys).toEqual(['skill', 'agent', 'command', 'rule', 'mcp', 'tool', 'hook'])
  })

  it('contains all expected type labels', () => {
    const labels = TYPES.map(([, v]) => v)
    expect(labels).toEqual(['Skills', 'Agents', 'Commands', 'Rules', 'MCP', 'Tools', 'Hooks'])
  })

  it('every entry is a [string, string] tuple', () => {
    for (const entry of TYPES) {
      expect(entry).toHaveLength(2)
      expect(typeof entry[0]).toBe('string')
      expect(typeof entry[1]).toBe('string')
    }
  })
})

// ---------------------------------------------------------------------------
// WORKFLOW_MODES
// ---------------------------------------------------------------------------

describe('WORKFLOW_MODES constant', () => {
  it('contains exactly 2 mode entries', () => {
    expect(WORKFLOW_MODES).toHaveLength(2)
  })

  it('contains auto and step modes', () => {
    const keys = WORKFLOW_MODES.map(([k]) => k)
    expect(keys).toContain('auto')
    expect(keys).toContain('step')
  })
})

// ---------------------------------------------------------------------------
// SOURCES
// ---------------------------------------------------------------------------

describe('SOURCES constant', () => {
  it('contains all expected sources', () => {
    const keys = SOURCES.map(([k]) => k)
    expect(keys).toContain('ecc')
    expect(keys).toContain('gstack')
    expect(keys).toContain('superpowers')
    expect(keys).toContain('claude-mem')
    expect(keys).toContain('example-skills')
    expect(keys).toContain('standalone')
    expect(keys).toContain('unknown')
  })

  it('every entry is a [string, string] tuple', () => {
    for (const entry of SOURCES) {
      expect(entry).toHaveLength(2)
      expect(typeof entry[0]).toBe('string')
      expect(typeof entry[1]).toBe('string')
    }
  })
})

// ---------------------------------------------------------------------------
// state — initial values
// ---------------------------------------------------------------------------

describe('initial state', () => {
  it('defaults type to empty string', () => {
    expect(state.type).toBe('')
  })

  it('defaults source to empty string', () => {
    expect(state.source).toBe('')
  })

  it('defaults status to active', () => {
    expect(state.status).toBe('active')
  })

  it('defaults search to empty string', () => {
    expect(state.search).toBe('')
  })

  it('defaults selected to null', () => {
    expect(state.selected).toBeNull()
  })

  it('defaults items to empty array', () => {
    expect(state.items).toEqual([])
  })

  it('defaults stats to null', () => {
    expect(state.stats).toBeNull()
  })

  it('defaults projects to empty object', () => {
    expect(state.projects).toEqual({})
  })

  it('defaults project to empty string', () => {
    expect(state.project).toBe('')
  })

  it('defaults packs to empty object', () => {
    expect(state.packs).toEqual({})
  })

  it('defaults pack to empty string', () => {
    expect(state.pack).toBe('')
  })

  it('defaults wfMode to empty string', () => {
    expect(state.wfMode).toBe('')
  })

  it('defaults timer to null', () => {
    expect(state.timer).toBeNull()
  })
})
