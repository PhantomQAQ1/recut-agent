/**
 * F2：镜头与角色的一致性检查。
 *
 * 判定口径很朴素——绑定的角色名或它的任一提示词锚点，必须出现在该镜的
 * 中文或英文提示词里。这不是"造型一致性百分比"，只是一个能立刻发现的
 * 漏配提醒：绑了角色但提示词里完全没提到它。
 */

import type { CharacterLike, Shot } from './types'

export type BindingIssue = {
  characterId: number
  name: string
  reason: string
}

export function anchorTokens(character: CharacterLike): string[] {
  return character.prompt_anchor
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean)
}

function contains(haystack: string, needle: string): boolean {
  if (!needle) return false
  return haystack.toLowerCase().includes(needle.toLowerCase())
}

/** 返回该镜缺失的角色（空数组表示一致）。 */
export function checkBindings(shot: Shot, characters: CharacterLike[]): BindingIssue[] {
  const ids = shot.character_ids ?? []
  if (!ids.length) return []

  const haystack = `${shot.prompt}\n${shot.runwayPrompt}`
  const issues: BindingIssue[] = []

  for (const id of ids) {
    const character = characters.find((item) => item.id === id)
    if (!character) {
      issues.push({ characterId: id, name: `#${id}`, reason: '角色已被删除' })
      continue
    }
    const tokens = anchorTokens(character)
    const matched =
      contains(haystack, character.name) || tokens.some((token) => contains(haystack, token))
    if (!matched) {
      issues.push({ characterId: id, name: character.name, reason: '提示词里没有出现该角色' })
    }
  }
  return issues
}

/** 把绑定角色的锚点合并进项目锚点（用于微调请求）。 */
export function mergeAnchors(
  base: string[],
  shot: Shot,
  characters: CharacterLike[],
): string[] {
  const ids = new Set(shot.character_ids ?? [])
  const merged = [...base]
  for (const character of characters) {
    if (!ids.has(character.id)) continue
    merged.push(...anchorTokens(character))
  }
  return Array.from(new Set(merged.map((item) => item.trim()).filter(Boolean)))
}

/** 生成"注入锚点"后的一句话前缀。 */
export function anchorPrefix(shot: Shot, characters: CharacterLike[]): string {
  return mergeAnchors([], shot, characters).join(', ')
}
