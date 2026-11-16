<script setup lang="ts">
import { computed } from 'vue'
import { Plus, Tags } from 'lucide-vue-next'
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  type AssetTag,
  type TagCategory,
} from '../composables/useAssets'

const props = defineProps<{
  tags: AssetTag[]
  selected: number | null
}>()

defineEmits<{
  select: [tagId: number]
  rename: [tag: AssetTag]
  remove: [tag: AssetTag]
  create: [category: TagCategory]
}>()

const groups = computed(() =>
  CATEGORY_ORDER.map((category) => ({
    category,
    label: CATEGORY_LABELS[category],
    items: props.tags.filter((tag) => tag.category === category),
  })).filter((group) => group.items.length),
)

const pad = (value: number) => String(value).padStart(2, '0')
</script>

<template>
  <section class="tag-section">
    <div class="section-title">
      <div>
        <span class="section-icon violet"><Tags :size="14" /></span>
        <b>智能标签云</b>
      </div>
      <span class="subtle">{{ tags.length }} TAGS</span>
    </div>

    <div v-for="group in groups" :key="group.category" class="tag-group">
      <div class="tag-category">
        {{ group.label }} <span class="tag-line"></span>{{ pad(group.items.length) }}
        <button
          class="mini-add"
          type="button"
          :aria-label="`在${group.label}新建标签`"
          @click="$emit('create', group.category)"
        >
          <Plus :size="11" />
        </button>
      </div>

      <div class="cloud">
        <span
          v-for="tag in group.items"
          :key="tag.id"
          class="tag-chip"
          :class="[`t-${tag.tone}`, { active: selected === tag.id }]"
          role="button"
          tabindex="0"
          @click="$emit('select', tag.id)"
          @keydown.enter="$emit('select', tag.id)"
        >
          {{ tag.name }}<em class="chip-count">{{ tag.usage_count }}</em>
          <span class="chip-actions">
            <button type="button" :aria-label="`重命名 ${tag.name}`" @click.stop="$emit('rename', tag)">
              ✎
            </button>
            <button type="button" :aria-label="`删除 ${tag.name}`" @click.stop="$emit('remove', tag)">
              ×
            </button>
          </span>
        </span>
      </div>
    </div>

    <p v-if="!tags.length" class="asset-empty">还没有标签，点分组右侧的 ＋ 新建</p>
  </section>
</template>
