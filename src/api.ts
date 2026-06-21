// ============================================================
// API layer — all fetch calls
// ============================================================

import { API } from './state'
import { fetchJSON, showToast } from './utils'
import type { ConfigItem, StatsMap, ProjectData, PackData } from './types'
import { state } from './state'

// --- Stats ---
export async function loadStats(): Promise<void> {
  try {
    state.stats = await fetchJSON<StatsMap>(`${API}/api/stats`)
  } catch (e) {
    console.error('loadStats failed:', e)
  }
}

// --- Items ---
export async function loadItems(): Promise<void> {
  try {
    const p = new URLSearchParams({ type: state.type + 's' })
    if (state.source) p.set('source', state.source)
    if (state.wfMode && state.type === 'workflow') p.set('source', state.wfMode)
    if (state.status) p.set('status', state.status)
    if (state.search) p.set('search', state.search)
    state.items = await fetchJSON<ConfigItem[]>(`${API}/api/items?${p}`)
  } catch (e) {
    console.error('loadItems failed:', e)
    import('./utils').then(u => u.showToast('加载项目列表失败，请刷新重试', 'error'))
  }
}

export async function loadItem(type: string, name: string): Promise<ConfigItem | null> {
  try {
    return await fetchJSON<ConfigItem>(`${API}/api/item/${type}s/${encodeURIComponent(name)}`)
  } catch {
    return null
  }
}

export async function saveItem(type: string, name: string, content?: string, description?: string): Promise<boolean> {
  try {
    const body: Record<string, string> = {}
    if (content !== undefined) body.content = content
    if (description !== undefined) body.description = description
    const r = await fetch(`${API}/api/item/${type}s/${encodeURIComponent(name)}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    const data = await r.json()
    return data.success === true
  } catch { return false }
}

export async function moveItem(type: string, name: string, to: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/move`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, name, to })
    })
    const data = await r.json()
    return data.success === true
  } catch { return false }
}

// --- Projects ---
export async function loadProjects(): Promise<void> {
  try {
    state.projects = await fetchJSON<Record<string, ProjectData>>(`${API}/api/projects`)
  } catch { /* projects not critical */ }
}

export async function createProject(name: string, path: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/projects`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, path })
    })
    const data = await r.json()
    showToast(data.message, data.success ? 'success' : 'error')
    return data.success === true
  } catch {
    showToast('创建失败', 'error')
    return false
  }
}

export async function deleteProject(name: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/projects/${encodeURIComponent(name)}`, { method: 'DELETE' })
    const data = await r.json()
    showToast(data.message, data.success ? 'success' : 'error')
    return data.success === true
  } catch {
    showToast('删除失败', 'error')
    return false
  }
}

export async function addProjectItem(projectName: string, itemType: string, itemName: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/projects/${encodeURIComponent(projectName)}/items`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: itemType, item_name: itemName })
    })
    const data = await r.json()
    showToast(data.message, data.success ? 'success' : 'error')
    return data.success === true
  } catch {
    showToast('添加失败', 'error')
    return false
  }
}

export async function discoverProject(name: string): Promise<{ added: number; message: string }> {
  try {
    const r = await fetch(`${API}/api/projects/${encodeURIComponent(name)}/discover`, { method: 'POST' })
    return await r.json()
  } catch { return { added: 0, message: '' } }
}

// --- Packs ---
export async function loadPacks(): Promise<void> {
  try {
    state.packs = await fetchJSON<Record<string, PackData>>(`${API}/api/packs`)
  } catch { /* packs not critical */ }
}

export async function createPack(name: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/packs`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim() })
    })
    const data = await r.json()
    showToast(data.message, data.success ? 'success' : 'error')
    return data.success === true
  } catch {
    showToast('创建失败', 'error')
    return false
  }
}

export async function deletePack(name: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/packs/${encodeURIComponent(name)}`, { method: 'DELETE' })
    const data = await r.json()
    showToast(data.message, data.success ? 'success' : 'error')
    return data.success === true
  } catch {
    showToast('删除失败', 'error')
    return false
  }
}

export async function addPackItem(packName: string, itemType: string, itemName: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/packs/${encodeURIComponent(packName)}/items`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: itemType, item_name: itemName })
    })
    const data = await r.json()
    showToast(data.message, data.success ? 'success' : 'error')
    return data.success === true
  } catch {
    showToast('添加失败', 'error')
    return false
  }
}

export async function removePackItem(packName: string, itemType: string, itemName: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/packs/${encodeURIComponent(packName)}/items`, {
      method: 'DELETE', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: itemType, item_name: itemName })
    })
    const data = await r.json()
    showToast(data.message, data.success ? 'success' : 'error')
    return data.success === true
  } catch {
    showToast('移除失败', 'error')
    return false
  }
}

export async function batchLoadItems(items: { type: string; name: string }[]): Promise<ConfigItem[]> {
  try {
    const r = await fetch(`${API}/api/items/batch`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items })
    })
    if (!r.ok) return []
    return await r.json()
  } catch { return [] }
}

// --- Workflow ---
export async function createWorkflow(name: string, mode: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/workflows/create`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim(), mode })
    })
    const data = await r.json()
    showToast(data.message, data.success ? 'success' : 'error')
    return data.success === true
  } catch {
    showToast('创建失败', 'error')
    return false
  }
}

export async function deleteWorkflow(name: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/workflows/${encodeURIComponent(name)}`, { method: 'DELETE' })
    const data = await r.json()
    return data.success === true
  } catch { return false }
}

export async function copyWorkflow(name: string): Promise<boolean> {
  try {
    const r = await fetch(`${API}/api/workflows/${encodeURIComponent(name)}/copy`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })
    const data = await r.json()
    showToast(data.message, data.success ? 'success' : 'error')
    return data.success === true
  } catch {
    showToast('复制失败', 'error')
    return false
  }
}

export async function importFile(file: File): Promise<{ success: boolean; message: string; type?: string }> {
  const form = new FormData()
  form.append('file', file)
  try {
    const r = await fetch(`${API}/api/import`, { method: 'POST', body: form })
    return await r.json()
  } catch {
    return { success: false, message: '导入失败' }
  }
}
