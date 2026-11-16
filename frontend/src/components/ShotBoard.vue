<script setup lang="ts">
/** 卡片墙容器：网格/列表切换、空态、新增镜头。 */
import { Plus } from 'lucide-vue-next'
import type { Shot } from '../lib/types'
import ShotCard from './ShotCard.vue'

const props = defineProps<{
  shots: Shot[]
  model: string
  anchors: string[]
  viewMode: 'grid' | 'list'
  refiningId?: number | null
}>()

defineEmits<{
  copy: [shot: Shot]
  refine: [payload: { shot: Shot; instruction: string }]
  upload: [shot: Shot]
  removeReference: [shot: Shot]
  add: []
}>()
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
      @copy="$emit('copy', $event)"
      @refine="$emit('refine', $event)"
      @upload="$emit('upload', $event)"
      @remove-reference="$emit('removeReference', $event)"
    />
    <button v-if="!props.shots.length" class="add-shot add-shot-empty" type="button" @click="$emit('add')">
      <Plus :size="15" />还没有镜头，先点左侧「生成分镜脚本」
    </button>
    <button v-else class="add-shot" type="button" @click="$emit('add')">
      <Plus :size="15" />添加镜头
    </button>
  </div>
</template>
