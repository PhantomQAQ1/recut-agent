/** 导出（E1/E3）：校验、Markdown、CSV 全部在前端即时生成。 */

import type { Shot } from './types'
import { isRunway, shotSeconds } from './types'

export type IssueLevel = 'error' | 'warning'

export type ExportIssue = {
  level: IssueLevel
  shotIndex: number | null
  message: string
}

export const CSV_COLUMNS = [
  '序号',
  '标题',
  '时长',
  '景别',
  '焦段',
  '运镜',
  '画面描述',
  '中文提示词',
  '英文提示词',
  '调色板',
  '场景',
]

export function validateShots(shots: Shot[]): ExportIssue[] {
  const issues: ExportIssue[] = []

  if (!shots.length) {
    issues.push({ level: 'error', shotIndex: null, message: '当前项目还没有镜头' })
    return issues
  }

  shots.forEach((shot, index) => {
    const label = index + 1
    if (!shot.title.trim()) {
      issues.push({ level: 'error', shotIndex: label, message: `第 ${label} 镜缺少标题` })
    }
    if (!shot.prompt.trim()) {
      issues.push({ level: 'error', shotIndex: label, message: `第 ${label} 镜缺少中文提示词` })
    }
    const seconds = shotSeconds(shot.duration)
    if (seconds < 3 || seconds > 6) {
      issues.push({
        level: 'error',
        shotIndex: label,
        message: `第 ${label} 镜时长 ${shot.duration} 超出 3-6 秒`,
      })
    }
    if (!shot.runwayPrompt.trim()) {
      issues.push({ level: 'warning', shotIndex: label, message: `第 ${label} 镜缺少英文提示词` })
    }
    if (!shot.reference_image_id) {
      issues.push({ level: 'warning', shotIndex: label, message: `第 ${label} 镜还没有参考首帧` })
    }
  })

  const total = shots.reduce((sum, shot) => sum + shotSeconds(shot.duration), 0)
  if (total < 12 || total > 60) {
    issues.push({
      level: 'warning',
      shotIndex: null,
      message: `总时长 ${total}s 不在建议的 12-60s 区间`,
    })
  }
  return issues
}

export function issueSummary(issues: ExportIssue[]): { errors: number; warnings: number } {
  return {
    errors: issues.filter((issue) => issue.level === 'error').length,
    warnings: issues.filter((issue) => issue.level === 'warning').length,
  }
}

export function toMarkdown(projectName: string, shots: Shot[], model: string): string {
  const lines: string[] = [`# ${projectName || '未命名项目'}`, '']
  const total = shots.reduce((sum, shot) => sum + shotSeconds(shot.duration), 0)
  lines.push(`共 ${shots.length} 个镜头 · 总时长 ${total}s · 默认模型 ${model}`, '')

  shots.forEach((shot, index) => {
    const label = String(index + 1).padStart(2, '0')
    lines.push(`## SHOT ${label} · ${shot.title || '未命名'}`, '')
    lines.push(
      `- 时长：${shot.duration} · 景别：${shot.scale} · 焦段：${shot.lens} · 运镜：${shot.move}`,
    )
    if (shot.description.trim()) lines.push(`- 画面：${shot.description.trim()}`)
    if (shot.reference_image_id) lines.push('- 参考首帧：已上传')
    lines.push('')
    lines.push('**中文提示词**', '', '```', shot.prompt, '```', '')
    lines.push('**英文提示词**', '', '```', shot.runwayPrompt, '```', '')
    lines.push(`_当前模型：${isRunway(model) ? 'Runway（使用英文提示词）' : model}_`, '')
  })
  return lines.join('\n')
}

function csvCell(value: string): string {
  const text = value.replace(/\r?\n/g, ' ')
  return /[",]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function toCsv(shots: Shot[]): string {
  const rows = [CSV_COLUMNS.join(',')]
  shots.forEach((shot, index) => {
    const cells = [
      String(index + 1),
      shot.title,
      shot.duration,
      shot.scale,
      shot.lens,
      shot.move,
      shot.description,
      shot.prompt,
      shot.runwayPrompt,
      shot.palette,
      shot.scene,
    ].map((cell) => csvCell(String(cell ?? '')))
    rows.push(cells.join(','))
  })
  // 带 BOM，Excel 直接双击不乱码
  return `\ufeff${rows.join('\r\n')}\r\n`
}

export function downloadText(filename: string, content: string, mime: string): void {
  downloadBlob(filename, new Blob([content], { type: mime }))
}

export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export function safeFilename(name: string): string {
  return (name || 'recut-storyboard').replace(/[\\/:*?"<>|]/g, '-').slice(0, 60)
}
