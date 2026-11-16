<script setup lang="ts">
/** B1：单镜微调的新旧对比。只有点"采用"才会写回故事板。 */
import { computed } from 'vue'
import { ArrowRight, Check, X } from 'lucide-vue-next'
import type { Shot } from '../lib/types'

const props = defineProps<{
  before: Shot
  after: Shot
  instruction: string
}>()

defineEmits<{ apply: []; cancel: [] }>()

type FieldSpec = { key: keyof Shot; label: string; multiline: boolean }

const FIELDS: FieldSpec[] = [
  { key: 'title', label: '标题', multiline: false },
  { key: 'description', label: '画面描述', multiline: true },
  { key: 'prompt', label: '中文提示词', multiline: true },
  { key: 'runwayPrompt', label: '英文提示词', multiline: true },
]

const rows = computed(() =>
  FIELDS.map((field) => {
    const before = String(props.before[field.key] ?? '')
    const after = String(props.after[field.key] ?? '')
    return { ...field, before, after, changed: before !== after }
  }),
)

const changedCount = computed(() => rows.value.filter((row) => row.changed).length)
</script>

<template>
  <div class="sheet-gate" role="dialog" aria-modal="true" aria-label="微调对比">
    <div class="sheet-card sheet-wide">
      <header class="sheet-head">
        <div>
          <p class="eyebrow">REFINE</p>
          <h3>微调结果对比</h3>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="$emit('cancel')">
          <X :size="15" />
        </button>
      </header>

      <p class="sheet-quote">指令：{{ instruction }}</p>
      <p class="sheet-hint">共 {{ changedCount }} 个字段发生变化，未变化的字段不会改动。</p>

      <div class="diff-list">
        <section v-for="row in rows" :key="row.key" class="diff-row" :class="{ changed: row.changed }">
          <header>
            <b>{{ row.label }}</b>
            <span v-if="row.changed" class="diff-tag">已修改</span>
            <span v-else class="diff-tag muted">未改动</span>
          </header>
          <template v-if="row.changed">
            <p class="diff-before">{{ row.before || '（空）' }}</p>
            <ArrowRight :size="12" class="diff-arrow" />
            <p class="diff-after">{{ row.after || '（空）' }}</p>
          </template>
          <p v-else class="diff-same">{{ row.before || '（空）' }}</p>
        </section>
      </div>

      <footer class="sheet-actions">
        <button class="login-ghost" type="button" @click="$emit('cancel')">放弃</button>
        <button class="login-submit" type="button" @click="$emit('apply')">
          <Check :size="15" />采用这次修改
        </button>
      </footer>
    </div>
  </div>
</template>
