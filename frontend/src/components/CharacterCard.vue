<script setup lang="ts">
import { Pencil, Trash2 } from 'lucide-vue-next'
import type { Character } from '../composables/useAssets'

const props = defineProps<{
  character: Character
  index: number
}>()

defineEmits<{
  edit: []
  remove: []
  removeTag: [payload: { characterId: number; tagId: number }]
  addTag: []
}>()

const label = (index: number) => `CHARACTER ${String(index + 1).padStart(2, '0')}`
const consistency = (value: number | null) =>
  value === null ? '未评估' : `${value.toFixed(1)}%`
</script>

<template>
  <article class="character-card">
    <div class="character-art" :class="`tone-${props.character.tone}`">
      <div class="portrait-halo"></div>
      <div class="portrait-body"><span></span></div>
      <div class="portrait-circlet"></div>
      <small>{{ label(props.index) }}</small>
      <div class="character-actions">
        <button type="button" aria-label="编辑角色" @click="$emit('edit')">
          <Pencil :size="11" />
        </button>
        <button type="button" aria-label="删除角色" @click="$emit('remove')">
          <Trash2 :size="11" />
        </button>
      </div>
    </div>

    <div class="character-info">
      <b>{{ character.name }}</b>
      <span class="character-type">{{ character.role_label || '未设置类型' }}</span>
      <p>
        {{ character.description || '暂无描述' }}<br />
        造型一致性 <strong>{{ consistency(character.consistency) }}</strong>
      </p>
    </div>

    <div class="character-tags">
      <span v-for="tag in character.tags" :key="tag.id" class="tag-chip" :class="`t-${tag.tone}`">
        {{ tag.name }}
        <button
          class="chip-remove"
          type="button"
          :aria-label="`移除标签 ${tag.name}`"
          @click="$emit('removeTag', { characterId: character.id, tagId: tag.id })"
        >
          ×
        </button>
      </span>
      <button class="chip-add" type="button" aria-label="添加标签" @click="$emit('addTag')">+</button>
    </div>
  </article>
</template>
