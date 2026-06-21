/**
 * RED tests for src/api.ts
 *
 * All tests mock `globalThis.fetch` so no real HTTP requests are made.
 *
 * Covers: loadStats, loadItems, loadItem, saveItem, moveItem,
 *         loadProjects, createProject, deleteProject,
 *         addProjectItem, discoverProject,
 *         loadPacks, createPack, deletePack, addPackItem, removePackItem,
 *         batchLoadItems, createWorkflow, deleteWorkflow, copyWorkflow,
 *         importFile
 *
 * Edge cases: network failures, empty responses, missing DOM elements
 *             (showToast requires #toast)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  loadStats,
  loadItems,
  loadItem,
  saveItem,
  moveItem,
  loadProjects,
  createProject,
  deleteProject,
  addProjectItem,
  discoverProject,
  loadPacks,
  createPack,
  deletePack,
  addPackItem,
  removePackItem,
  batchLoadItems,
  createWorkflow,
  deleteWorkflow,
  copyWorkflow,
  importFile,
} from '../api'

// Re-import state after each test to reset it
import { state } from '../state'

// Helper: create a mock Response
function mockResponse(data: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: () => Promise.resolve(data),
  } as Response
}

beforeEach(() => {
  vi.restoreAllMocks()
  // Provide a toast element so showToast doesn't silently fail
  document.body.innerHTML = '<div id="toast"></div>'
  // Reset state
  state.items = []
  state.stats = null
  state.projects = {}
  state.packs = {}
})

// ==========================================================================
// loadStats
// ==========================================================================

describe('loadStats', () => {
  it('updates state.stats on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse({ skills: { active: 5 } }))
    await loadStats()
    expect(state.stats).toEqual({ skills: { active: 5 } })
  })

  it('does not throw on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    await expect(loadStats()).resolves.toBeUndefined()
    expect(state.stats).toBeNull()
  })
})

// ==========================================================================
// loadItems
// ==========================================================================

describe('loadItems', () => {
  it('updates state.items on success', async () => {
    state.type = 'skill'
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse([{ type: 'skill', name: 'test' }]),
    )
    await loadItems()
    expect(state.items).toHaveLength(1)
    expect(state.items[0].name).toBe('test')
  })

  it('passes query parameters from state', async () => {
    state.type = 'rule'
    state.source = 'ecc'
    state.status = 'active'
    state.search = 'test'
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse([]))
    await loadItems()

    const calledUrl = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string
    expect(calledUrl).toContain('type=rules')
    expect(calledUrl).toContain('source=ecc')
    expect(calledUrl).toContain('status=active')
    expect(calledUrl).toContain('search=test')
  })

  it('does not throw on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    await expect(loadItems()).resolves.toBeUndefined()
  })
})

// ==========================================================================
// loadItem
// ==========================================================================

describe('loadItem', () => {
  it('returns the item on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ type: 'skill', name: 'my-skill' }),
    )
    const item = await loadItem('skill', 'my-skill')
    expect(item).not.toBeNull()
    expect(item!.name).toBe('my-skill')
  })

  it('returns null on 404', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse(null, false, 404))
    const item = await loadItem('skill', 'missing')
    expect(item).toBeNull()
  })

  it('returns null on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const item = await loadItem('skill', 'any')
    expect(item).toBeNull()
  })
})

// ==========================================================================
// saveItem
// ==========================================================================

describe('saveItem', () => {
  it('returns true on successful save', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true }),
    )
    const result = await saveItem('skill', 'my-skill', 'content')
    expect(result).toBe(true)
  })

  it('returns false when API returns success: false', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: false }),
    )
    const result = await saveItem('skill', 'my-skill', 'content')
    expect(result).toBe(false)
  })

  it('returns false on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const result = await saveItem('skill', 'my-skill', 'content')
    expect(result).toBe(false)
  })

  it('sends PUT request with correct headers', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse({ success: true }))
    await saveItem('rule', 'test-rule', 'new content', 'new desc')
    const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(callArgs[1].method).toBe('PUT')
    expect(callArgs[1].headers['Content-Type']).toBe('application/json')
  })
})

// ==========================================================================
// moveItem
// ==========================================================================

describe('moveItem', () => {
  it('returns true on successful move', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse({ success: true }))
    const result = await moveItem('skill', 'my-skill', 'archived')
    expect(result).toBe(true)
  })

  it('returns false on API error', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse({ success: false }))
    const result = await moveItem('skill', 'my-skill', 'archived')
    expect(result).toBe(false)
  })

  it('returns false on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const result = await moveItem('skill', 'my-skill', 'archived')
    expect(result).toBe(false)
  })
})

// ==========================================================================
// loadProjects
// ==========================================================================

describe('loadProjects', () => {
  it('updates state.projects on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ 'my-proj': { name: 'my-proj' } }),
    )
    await loadProjects()
    expect(state.projects).toHaveProperty('my-proj')
  })

  it('does not throw on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    await expect(loadProjects()).resolves.toBeUndefined()
  })
})

// ==========================================================================
// createProject
// ==========================================================================

describe('createProject', () => {
  it('returns true on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true, message: '已创建' }),
    )
    const result = await createProject('test', '/tmp/test')
    expect(result).toBe(true)
  })

  it('returns false on API failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: false, message: '已存在' }),
    )
    const result = await createProject('dup', '/tmp/dup')
    expect(result).toBe(false)
  })

  it('returns false on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const result = await createProject('test', '/tmp/test')
    expect(result).toBe(false)
  })
})

// ==========================================================================
// deleteProject
// ==========================================================================

describe('deleteProject', () => {
  it('returns true on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true, message: '已删除' }),
    )
    const result = await deleteProject('my-proj')
    expect(result).toBe(true)
  })

  it('returns false on API failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: false, message: '不存在' }),
    )
    const result = await deleteProject('missing')
    expect(result).toBe(false)
  })
})

// ==========================================================================
// addProjectItem
// ==========================================================================

describe('addProjectItem', () => {
  it('returns true on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true, message: '已添加' }),
    )
    const result = await addProjectItem('proj', 'skill', 's1')
    expect(result).toBe(true)
  })

  it('returns false on failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: false, message: '不存在' }),
    )
    const result = await addProjectItem('missing', 'skill', 's1')
    expect(result).toBe(false)
  })
})

// ==========================================================================
// discoverProject
// ==========================================================================

describe('discoverProject', () => {
  it('returns discovery result on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ added: 3, message: '发现 3 项' }),
    )
    const result = await discoverProject('my-proj')
    expect(result.added).toBe(3)
  })

  it('returns zeros on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const result = await discoverProject('my-proj')
    expect(result.added).toBe(0)
    expect(result.message).toBe('')
  })
})

// ==========================================================================
// loadPacks
// ==========================================================================

describe('loadPacks', () => {
  it('updates state.packs on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ 'my-pack': { name: 'my-pack' } }),
    )
    await loadPacks()
    expect(state.packs).toHaveProperty('my-pack')
  })

  it('does not throw on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    await expect(loadPacks()).resolves.toBeUndefined()
  })
})

// ==========================================================================
// createPack
// ==========================================================================

describe('createPack', () => {
  it('returns true on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true, message: '已创建' }),
    )
    const result = await createPack('test-pack')
    expect(result).toBe(true)
  })

  it('returns false on failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: false, message: '已存在' }),
    )
    const result = await createPack('dup')
    expect(result).toBe(false)
  })

  it('trims the name before sending', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true }),
    )
    await createPack('  spaced name  ')
    const body = JSON.parse(
      (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
    )
    expect(body.name).toBe('spaced name')
  })
})

// ==========================================================================
// deletePack
// ==========================================================================

describe('deletePack', () => {
  it('returns true on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true, message: '已删除' }),
    )
    const result = await deletePack('my-pack')
    expect(result).toBe(true)
  })

  it('returns false on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const result = await deletePack('my-pack')
    expect(result).toBe(false)
  })
})

// ==========================================================================
// addPackItem / removePackItem
// ==========================================================================

describe('addPackItem', () => {
  it('returns true on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true, message: '已添加' }),
    )
    const result = await addPackItem('pack', 'skill', 's1')
    expect(result).toBe(true)
  })
})

describe('removePackItem', () => {
  it('returns true on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true, message: '已移除' }),
    )
    const result = await removePackItem('pack', 'skill', 's1')
    expect(result).toBe(true)
  })
})

// ==========================================================================
// batchLoadItems
// ==========================================================================

describe('batchLoadItems', () => {
  it('returns items on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse([{ type: 'skill', name: 's1' }]),
    )
    const result = await batchLoadItems([{ type: 'skill', name: 's1' }])
    expect(result).toHaveLength(1)
  })

  it('returns empty array on non-ok response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse([], false, 500),
    )
    const result = await batchLoadItems([{ type: 'skill', name: 's1' }])
    expect(result).toEqual([])
  })

  it('returns empty array on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const result = await batchLoadItems([{ type: 'skill', name: 's1' }])
    expect(result).toEqual([])
  })
})

// ==========================================================================
// createWorkflow / deleteWorkflow / copyWorkflow
// ==========================================================================

describe('createWorkflow', () => {
  it('returns true on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true, message: '已创建' }),
    )
    const result = await createWorkflow('my-wf', 'auto')
    expect(result).toBe(true)
  })

  it('trims name before sending', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true }),
    )
    await createWorkflow('  wf-name  ', 'step')
    const body = JSON.parse(
      (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
    )
    expect(body.name).toBe('wf-name')
  })
})

describe('deleteWorkflow', () => {
  it('returns true on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true }),
    )
    const result = await deleteWorkflow('my-wf')
    expect(result).toBe(true)
  })

  it('returns false on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const result = await deleteWorkflow('my-wf')
    expect(result).toBe(false)
  })
})

describe('copyWorkflow', () => {
  it('returns true on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true, message: '已复制' }),
    )
    const result = await copyWorkflow('my-wf')
    expect(result).toBe(true)
  })

  it('returns false on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const result = await copyWorkflow('my-wf')
    expect(result).toBe(false)
  })
})

// ==========================================================================
// importFile
// ==========================================================================

describe('importFile', () => {
  it('returns result on success', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      mockResponse({ success: true, message: '已导入' }),
    )
    const file = new File(['test'], 'test.md', { type: 'text/markdown' })
    const result = await importFile(file)
    expect(result.success).toBe(true)
  })

  it('returns failure on network error', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const file = new File(['test'], 'test.md', { type: 'text/markdown' })
    const result = await importFile(file)
    expect(result.success).toBe(false)
    expect(result.message).toContain('失败')
  })

  it('sends FormData', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse({ success: true }))
    const file = new File(['test'], 'test.md', { type: 'text/markdown' })
    await importFile(file)
    const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(callArgs[0]).toContain('/api/import')
    expect(callArgs[1].method).toBe('POST')
    expect(callArgs[1].body).toBeInstanceOf(FormData)
  })
})
