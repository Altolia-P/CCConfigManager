// ============================================================
// TypeScript type definitions for CCConfigManager
// ============================================================

// --- API / Config Items ---
export type ItemType = 'skill' | 'agent' | 'command' | 'rule' | 'mcp' | 'tool' | 'workflow' | 'hook'
export type ItemStatus = 'active' | 'archived'

export interface ConfigItem {
  type: ItemType
  name: string
  source: string
  status: ItemStatus
  path: string
  paths: string[]
  description: string
  content_preview: string
  raw_content?: string
}

// --- Projects ---
export interface ProjectData {
  name: string
  path: string
  skills: string[]
  agents: string[]
  commands: string[]
  rules: string[]
  mcps: string[]
  tools: string[]
  workflows: string[]
  hooks: string[]
}

// --- Packs ---
export interface PackData {
  name: string
  skills: string[]
  agents: string[]
  commands: string[]
  rules: string[]
  mcps: string[]
  tools: string[]
  workflows: string[]
}

// --- App State ---
export interface StatsMap {
  [type: string]: { active: number; archived: number }
}

export interface AppState {
  type: string
  source: string
  status: string
  search: string
  selected: ConfigItem | null
  items: ConfigItem[]
  stats: StatsMap | null
  projects: Record<string, ProjectData>
  project: string
  packs: Record<string, PackData>
  pack: string
  wfMode: string
  _allItems?: ConfigItem[]
  _cache?: ConfigItem[]
  timer: ReturnType<typeof setTimeout> | null
}

// --- Workflow Types ---
export type WfMode = 'auto' | 'step'
export type NodeType = 'agent' | 'gate' | 'command'
export type EdgeCondition = 'auto' | 'manual' | 'expression'
export type HookTiming = 'onEnter' | 'onLeave'
export type HookKind = 'shell' | 'agent'

export interface Position { x: number; y: number }

export interface Permissions {
  allows: string[]
  blocks: string[]
}

export interface GateConfig {
  condition: EdgeCondition
  autoDetect: string
  manualAdvance: string
  expression: string
}

export interface HookConfig {
  type: HookKind
  timing: HookTiming
  value: string
}

export interface WfNode {
  id: string
  type: NodeType
  label: string
  position: Position
  packId?: string
  agentId?: string | null
  commandId?: string | null
  skillIds?: string[]
  mcpIds?: string[]
  toolIds?: string[]
  permissions?: Permissions
  produces?: string[]
  hooks?: HookConfig[]
  timeout?: number
  gateConfig?: GateConfig
}

export interface WfEdge {
  id: string
  from: string
  to: string
  condition: EdgeCondition
  autoDetect?: string | null
  manualAdvance?: string | null
  expression?: string | null
}

export interface WorkflowData {
  slug: string
  name: string
  description: string
  mode: WfMode
  nodes: WfNode[]
  edges: WfEdge[]
}

// --- Canvas Interaction State ---
export interface DragState {
  nodeId: string
  startX: number
  startY: number
  origX: number
  origY: number
}

export interface DrawState {
  fromNodeId: string
  fromX: number
  fromY: number
  mouseX: number
  mouseY: number
}

export interface PanState {
  startX: number
  startY: number
  startPanX: number
  startPanY: number
  wasBlank?: boolean
}

// --- Cached Reference Data ---
export interface CachedRef {
  slug: string
  name: string
}
