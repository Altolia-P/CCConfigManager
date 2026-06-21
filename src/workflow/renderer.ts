// ============================================================
// Workflow Renderer — SVG node/edge rendering
// ============================================================

import { esc, escAttr, trunc } from '../utils'
import type { WfNode, WfEdge } from '../types'
import { WF } from './engine'

export function renderAll(this: typeof WF): void {
  if (!this.nodesGroup || !this.edgesGroup) return
  renderNodes.call(this)
  renderEdges.call(this)
  this.renderProps()
  this.updateViewport()
  this.updateStatus()
}

function renderNodes(this: typeof WF): void {
  let h = ''
  this.nodes.forEach(n => {
    const sel = n.id === this.selectedId
    const x = n.position.x, y = n.position.y
    if (n.type === 'gate') {
      h += `<g class="wf-node node-gate${sel ? ' selected' : ''}" data-node-id="${n.id}" transform="translate(${x},${y})">
        <polygon class="node-body" points="60,0 120,35 60,70 0,35"/>
        <rect class="node-icon-bg" x="50" y="6" width="20" height="20" rx="4"/>
        <text x="60" y="20" font-size="14" text-anchor="middle" fill="var(--color-unknown)">◇</text>
        <text class="node-title" x="60" y="45" text-anchor="middle"><title>${esc(n.label || 'Gate')}</title>${esc(trunc(n.label || 'Gate', 5))}</text>
        <circle class="node-handle" data-node-id="${n.id}" data-handle="input" cx="0" cy="35" r="8"/>
        <circle class="node-handle" data-node-id="${n.id}" data-handle="output" cx="120" cy="35" r="8"/>
        <circle class="node-del-btn-circle" data-del="${n.id}" cx="108" cy="5" r="9"/>
        <text class="node-del-btn-x" data-del="${n.id}" x="104" y="9" font-size="14" font-weight="700">×</text>
      </g>`
    } else if (n.type === 'command') {
      const cmdBadges: string[] = []
      if ((n.produces || []).length) cmdBadges.push(`📄${n.produces!.length}`)
      if ((n.hooks || []).length) cmdBadges.push(`🪝${n.hooks!.length}`)
      h += `<g class="wf-node node-command${sel ? ' selected' : ''}" data-node-id="${n.id}" transform="translate(${x},${y})">
        <rect class="node-body" x="0" y="0" width="200" height="64" rx="8"/>
        <rect class="node-body-bg" x="0" y="0" width="200" height="64" rx="8" fill="var(--color-ecc)"/>
        <rect class="node-icon-bg" x="10" y="14" width="36" height="36" rx="6"/>
        <text x="28" y="37" font-size="16" text-anchor="middle">⌨</text>
        <text class="node-title" x="54" y="24"><title>${esc(n.label || 'Command')}</title>${esc(trunc(n.label || 'Command', 10))}</text>
        <text class="node-sub" x="54" y="40"><title>${esc(n.commandId || '')}</title>${esc(trunc(n.commandId || 'Command', 18))}</text>
        ${cmdBadges.length ? `<text class="node-sub" x="${200 - cmdBadges.length * 22}" y="54" font-size="9" fill="var(--text-secondary)">${cmdBadges.join(' ')}</text>` : ''}
        <circle class="node-handle" data-node-id="${n.id}" data-handle="input" cx="0" cy="32" r="8"/>
        <circle class="node-handle" data-node-id="${n.id}" data-handle="output" cx="200" cy="32" r="8"/>
        <circle class="node-del-btn-circle" data-del="${n.id}" cx="188" cy="4" r="9"/>
        <text class="node-del-btn-x" data-del="${n.id}" x="184" y="8" font-size="13" font-weight="700">×</text>
        <circle class="node-add-btn-circle" data-node-id="${n.id}" cx="218" cy="32" r="9"/>
        <text class="node-add-btn-plus" data-node-id="${n.id}" x="214" y="36" font-size="16" font-weight="700">+</text>
      </g>`
    } else {
      const badges: string[] = []
      if ((n.mcpIds || []).length) badges.push(`🔌${n.mcpIds!.length}`)
      if ((n.toolIds || []).length) badges.push(`🔧${n.toolIds!.length}`)
      if ((n.produces || []).length) badges.push(`📄${n.produces!.length}`)
      if ((n.hooks || []).length) badges.push(`🪝${n.hooks!.length}`)
      h += `<g class="wf-node node-agent${sel ? ' selected' : ''}" data-node-id="${n.id}" transform="translate(${x},${y})">
        <rect class="node-body" x="0" y="0" width="200" height="64" rx="8"/>
        <rect class="node-body-bg" x="0" y="0" width="200" height="64" rx="8"/>
        <rect class="node-icon-bg" x="10" y="14" width="36" height="36" rx="6"/>
        <text x="28" y="37" font-size="16" text-anchor="middle">🤖</text>
        <text class="node-title" x="54" y="24"><title>${esc(n.label || '步骤')}</title>${esc(trunc(n.label || '步骤', 8))}</text>
        <text class="node-sub" x="54" y="40"><title>${esc(n.agentId || '未指定 Agent')}</title>${esc(trunc(n.agentId || '未指定 Agent', 16))}</text>
        ${(n.skillIds || []).length ? `<text class="node-sub" x="54" y="54" fill="var(--color-superpowers)">+${n.skillIds!.length} Skills</text>` : ''}
        ${badges.length ? `<text class="node-sub" x="${200 - badges.length * 26}" y="54" font-size="9" fill="var(--text-secondary)">${badges.join(' ')}</text>` : ''}
        <circle class="node-handle" data-node-id="${n.id}" data-handle="input" cx="0" cy="32" r="8"/>
        <circle class="node-handle" data-node-id="${n.id}" data-handle="output" cx="200" cy="32" r="8"/>
        <circle class="node-del-btn-circle" data-del="${n.id}" cx="188" cy="4" r="9"/>
        <text class="node-del-btn-x" data-del="${n.id}" x="184" y="8" font-size="13" font-weight="700">×</text>
        <circle class="node-add-btn-circle" data-node-id="${n.id}" cx="218" cy="32" r="9"/>
        <text class="node-add-btn-plus" data-node-id="${n.id}" x="214" y="36" font-size="16" font-weight="700">+</text>
      </g>`
    }
  })
  this.nodesGroup.innerHTML = h

  // Bind delete buttons
  this.nodesGroup.querySelectorAll<HTMLElement>('.node-del-btn-circle, .node-del-btn-x').forEach(el => {
    el.onclick = (e: Event) => { e.stopPropagation(); const nid = el.dataset.del; if (nid) { this.selectedId = nid; this.deleteSelected() } }
  })
  // Bind + buttons
  this.nodesGroup.querySelectorAll<HTMLElement>('.node-add-btn-circle').forEach(el => {
    el.onclick = (e: Event) => {
      e.stopPropagation()
      const nodeId = el.dataset.nodeId
      const node = this.nodes.find(n => n.id === nodeId)
      if (node) {
        const nx = node.position.x + 260, ny = node.position.y
        this.addNode('agent', nx, ny, nodeId)
      }
    }
  })
}

function renderEdges(this: typeof WF): void {
  let h = ''
  this.edges.forEach(e => {
    const sel = e.id === this.selectedId
    const from = this.nodes.find(n => n.id === e.from)
    const to = this.nodes.find(n => n.id === e.to)
    if (!from || !to) return
    const [x1, y1] = this.getOutputPos(from); const [x2, y2] = this.getInputPos(to)
    const d = this.bezierPath(x1, y1, x2, y2)
    h += `<path class="wf-edge-hit" data-edge-id="${e.id}" d="${d}"/><path class="wf-edge${sel ? ' selected' : ''}" data-edge-id="${e.id}" d="${d}" marker-end="url(#wfArrow)"/>`
  })
  this.edgesGroup.innerHTML = h
}
