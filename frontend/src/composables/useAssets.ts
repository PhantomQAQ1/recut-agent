/**
 * 角色资产与标签的共享状态（模块级单例）。
 *
 * 与 useAuth 同样的取舍：当前只有"当前用户的资产列表"这一份全局状态，
 * 不引入 Pinia。所有写操作完成后都会重新拉取列表，保证 version 与 usage_count 是最新的。
 */

import { computed, ref } from 'vue'
import { api } from '../api/client'

export type TagCategory = 'character' | 'emotion' | 'palette' | 'lighting' | 'appearance'
export type Tone = 'amber' | 'violet' | 'rose' | 'indigo' | 'neutral'

export type AssetTag = {
  id: number
  name: string
  category: TagCategory
  tone: Tone
  usage_count: number
}

export type Character = {
  id: number
  name: string
  role_label: string
  description: string
  consistency: number | null
  prompt_anchor: string
  tone: Tone
  version: number
  tags: AssetTag[]
  created_at: string
  updated_at: string
}

export type CharacterPayload = {
  name?: string
  role_label?: string
  description?: string
  prompt_anchor?: string
  tone?: Tone
  expected_version?: number
}

export const CATEGORY_ORDER: TagCategory[] = [
  'character',
  'emotion',
  'palette',
  'lighting',
  'appearance',
]

export const CATEGORY_LABELS: Record<TagCategory, string> = {
  character: '人物',
  emotion: '情绪',
  palette: '色调',
  lighting: '光影',
  appearance: '外观',
}

export const TONE_OPTIONS: Tone[] = ['amber', 'violet', 'rose', 'indigo', 'neutral']

const characters = ref<Character[]>([])
const tags = ref<AssetTag[]>([])
const loading = ref(false)
const loaded = ref(false)
const error = ref('')

const groupedTags = computed(() => {
  const groups: { category: TagCategory; label: string; items: AssetTag[] }[] = []
  for (const category of CATEGORY_ORDER) {
    const items = tags.value.filter((tag) => tag.category === category)
    if (items.length) {
      groups.push({ category, label: CATEGORY_LABELS[category], items })
    }
  }
  return groups
})

async function refresh(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [characterList, tagList] = await Promise.all([
      api.get<Character[]>('/api/v1/characters'),
      api.get<AssetTag[]>('/api/v1/tags'),
    ])
    characters.value = characterList
    tags.value = tagList
    loaded.value = true
  } catch (exception) {
    error.value = exception instanceof Error ? exception.message : '资产加载失败'
  } finally {
    loading.value = false
  }
}

async function ensureLoaded(): Promise<void> {
  if (!loaded.value && !loading.value) await refresh()
}

function reset(): void {
  characters.value = []
  tags.value = []
  loaded.value = false
  error.value = ''
}

async function createCharacter(payload: CharacterPayload & { tag_ids?: number[] }): Promise<Character> {
  const created = await api.post<Character>('/api/v1/characters', payload)
  await refresh()
  return created
}

async function updateCharacter(id: number, payload: CharacterPayload): Promise<Character> {
  const updated = await api.patch<Character>(`/api/v1/characters/${id}`, payload)
  await refresh()
  return updated
}

async function deleteCharacter(id: number): Promise<void> {
  await api.delete(`/api/v1/characters/${id}`)
  await refresh()
}

async function addCharacterTags(id: number, tagIds: number[]): Promise<Character> {
  const updated = await api.patch<Character>(`/api/v1/characters/${id}/tags`, {
    add: tagIds,
  })
  await refresh()
  return updated
}

async function removeCharacterTags(id: number, tagIds: number[]): Promise<Character> {
  const updated = await api.patch<Character>(`/api/v1/characters/${id}/tags`, {
    remove: tagIds,
  })
  await refresh()
  return updated
}

async function createTag(payload: {
  name: string
  category: TagCategory
  tone: Tone
}): Promise<{ tag: AssetTag; created: boolean }> {
  const result = await api.post<AssetTag & { created: boolean }>('/api/v1/tags', payload)
  await refresh()
  return { tag: result, created: result.created }
}

async function updateTag(
  id: number,
  payload: { name?: string; category?: TagCategory; tone?: Tone },
): Promise<AssetTag> {
  const updated = await api.patch<AssetTag>(`/api/v1/tags/${id}`, payload)
  await refresh()
  return updated
}

async function deleteTag(
  id: number,
  options: { force?: boolean; reassignTo?: number } = {},
): Promise<void> {
  const params = new URLSearchParams()
  if (options.force) params.set('force', 'true')
  if (options.reassignTo) params.set('reassign_to', String(options.reassignTo))
  const query = params.toString()
  await api.delete(`/api/v1/tags/${id}${query ? `?${query}` : ''}`)
  await refresh()
}

export function useAssets() {
  return {
    characters,
    tags,
    groupedTags,
    loading,
    loaded,
    error,
    refresh,
    ensureLoaded,
    reset,
    createCharacter,
    updateCharacter,
    deleteCharacter,
    addCharacterTags,
    removeCharacterTags,
    createTag,
    updateTag,
    deleteTag,
  }
}
