// ============================================================
// Global application state
// ============================================================

import type { AppState } from './types'

export const API = ''

export const TYPES: [string, string][] = [
  ['skill','Skills'],['agent','Agents'],['command','Commands'],
  ['rule','Rules'],['mcp','MCP'],['tool','Tools'],['hook','Hooks']
]

export const WORKFLOW_MODES: [string, string][] = [
  ['auto','Auto 自动编排'],['step','Step 阶段门禁']
]

export const SOURCES: [string, string][] = [
  ['ecc','ECC'],['gstack','Gstack'],['superpowers','Superpowers'],
  ['claude-mem','Claude Mem'],['example-skills','Example'],
  ['standalone','独立'],['unknown','未知']
]

export const state: AppState = {
  type: '',
  source: '',
  status: 'active',
  search: '',
  selected: null,
  items: [],
  stats: null,
  projects: {},
  project: '',
  packs: {},
  pack: '',
  wfMode: '',
  timer: null,
}
