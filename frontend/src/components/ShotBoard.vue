<script setup lang="ts">
/** 卡片墙容器：网格/列表切换、空态、新增镜头、重排与角色绑定。 */
import { Plus } from 'lucide-vue-next'
import { checkBindings } from '../lib/consistency'
import type { BindingChip, CharacterLike, Shot } from '../lib/types'
import ShotCard from './ShotCard.vue'

const props = defineProps<{
  shots: Shot[]
  model: string
  anchors: string[]
  viewMode: 'grid' | 'list'
  refiningId?: number | null
  characters?: CharacterLike[]
}>()

const emit = defineEmits<{
  copy: [shot: Shot]
  refine: [payload: { shot: Shot; instruction: string }]
  upload: [shot: Shot]
  removeReference: [shot: Shot]
  remove: [shot: Shot]
  bind: [shot: Shot]
  injectAnchors: [shot: Shot]
  move: [payload: { from: number; to: number }]
  add: []
}>()

function chipsFor(shot: Shot): BindingChip[] {
  const characters = props.characters ?? []
  const issues = checkBindings(shot, characters)
  return (shot.character_ids ?? []).map((id) => {
    const character = characters.find((item) => item.id === id)
    return {
      id,
      name: character?.name ?? `#${id}`,
      missing: issues.some((issue) => issue.characterId === id),
    }
  })
}
</script>

<template>
  <div :class="props.viewMode === 'grid' ? 'shot-list grid-cols-1 md:grid-cols-2' : 'shot-list list-mode flex-col'">
    <ShotCard
      v-for="(shot, index) in props.shots"
      :key="shot.id"
      :shot="shot"
      :index="index"
      :model="props.model"
      :anchors="props.anchors"
      :refining="props.refiningId === shot.id"
      :bindings="chipsFor(shot)"
      :can-move-up="index > 0"
      :can-move-down="index < props.shots.length - 1"
      @copy="emit('copy', $event)"
      @refine="emit('refine', $event)"
      @upload="emit('upload', $event)"
      @remove-reference="emit('removeReference', $event)"
      @remove="emit('remove', $event)"
      @bind="emit('bind', $event)"
      @inject-anchors="emit('injectAnchors', $event)"
      @move-up="emit('move', { from: index, to: index - 1 })"
      @move-down="emit('move', { from: index, to: index + 1 })"
    />
    <button v-if="!props.shots.length" class="add-shot add-shot-empty" type="button" @click="emit('add')">
      <Plus :size="15" />还没有镜头，先点左侧「生成分镜脚本」
    </button>
    <button v-else class="add-shot" type="button" @click="emit('add')">
      <Plus :size="15" />添加镜头
    </button>
  </div>
</template>
