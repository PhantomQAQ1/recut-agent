<script setup lang="ts">
/** E3 + E1：导出前校验，以及 Markdown / CSV / 剪映草稿三种导出。 */
import { computed, ref } from 'vue'
import { AlertTriangle, Download, LoaderCircle, X } from 'lucide-vue-next'
import { issueSummary, validateShots } from '../lib/export'
import type { Shot } from '../lib/types'

const props = defineProps<{
  shots: Shot[]
  projectName: string
  model: string
  busy: boolean
}>()

const emit = defineEmits<{
  close: []
  export: [format: 'md' | 'csv' | 'jianying']
}>()

type Format = 'md' | 'csv' | 'jianying'
const format = ref<Format>('md')
const force = ref(false)

const OPTIONS: { value: Format; label: string; hint: string }[] = [
  { value: 'md', label: 'Markdown', hint: '一镜一节，含中英提示词，适合交付文档' },
  { value: 'csv', label: 'CSV', hint: '表格版，Excel 直接打开，适合排期与对接' },
  { value: 'jianying', label: '剪映草稿', hint: '占位图 + 文字轨的实验性草稿（zip）' },
]

const issues = computed(() => validateShots(props.shots))
const summary = computed(() => issueSummary(issues.value))
const blocked = computed(() => summary.value.errors > 0 && !force.value)
</script>

<template>
  <div class="sheet-gate" role="dialog" aria-modal="true" aria-label="导出">
    <div class="sheet-card">
      <header class="sheet-head">
        <div>
          <p class="eyebrow">EXPORT</p>
          <h3>导出故事板</h3>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="$emit('close')">
          <X :size="15" />
        </button>
      </header>

      <p class="sheet-hint">
        {{ props.shots.length }} 个镜头 · {{ props.projectName || '未命名项目' }}
      </p>

      <div class="export-options">
        <button
          v-for="option in OPTIONS"
          :key="option.value"
          type="button"
          class="export-option"
          :class="{ active: format === option.value }"
          @click="format = option.value"
        >
          <b>{{ option.label }}</b>
          <small>{{ option.hint }}</small>
        </button>
      </div>

      <section v-if="issues.length" class="export-issues">
        <p class="export-summary">
          <AlertTriangle :size="13" />
          校验结果：{{ summary.errors }} 个错误 · {{ summary.warnings }} 个提醒
        </p>
        <ul>
          <li v-for="(issue, index) in issues" :key="index" :class="issue.level">
            {{ issue.message }}
          </li>
        </ul>
        <label v-if="summary.errors" class="login-remember">
          <input v-model="force" type="checkbox" />
          <span>忽略错误，仍然导出</span>
        </label>
      </section>
      <p v-else class="export-summary ok">校验通过，可以直接导出</p>

      <footer class="sheet-actions">
        <button class="login-ghost" type="button" @click="$emit('close')">取消</button>
        <button
          class="login-submit"
          type="button"
          :disabled="blocked || props.busy"
          @click="emit('export', format)"
        >
          <LoaderCircle v-if="props.busy" class="spin" :size="15" />
          <Download v-else :size="15" />
          {{ blocked ? '请先修正错误' : '导出' }}
        </button>
      </footer>
    </div>
  </div>
</template>
