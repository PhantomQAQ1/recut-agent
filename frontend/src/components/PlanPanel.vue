<script setup lang="ts">
/** B4：镜头计划面板。确认后才逐镜展开提示词。 */
import { computed, ref } from 'vue'
import { Check, LoaderCircle, Plus, Trash2, X } from 'lucide-vue-next'
import {
  DURATION_OPTIONS,
  LENS_OPTIONS,
  MOVE_OPTIONS,
  SCALE_OPTIONS,
  planSeconds,
  type ShotPlan,
} from '../lib/types'

const props = defineProps<{
  plan: ShotPlan
  busy: boolean
  /** index -> pending / done / error */
  progress: Record<number, 'pending' | 'done' | 'error'>
  /** 故事板上已有的卡片数；>0 时让用户选择替换还是追加 */
  existingShots?: number
}>()

const emit = defineEmits<{
  confirm: [mode: 'replace' | 'append']
  cancel: []
  update: [plan: ShotPlan]
}>()

/** 展开结果怎么落盘：默认替换，用户可改为追加到末尾。 */
const mode = ref<'replace' | 'append'>('replace')
const existing = computed(() => props.existingShots ?? 0)

const totalSeconds = computed(() => planSeconds(props.plan))
const doneCount = computed(
  () => Object.values(props.progress).filter((state) => state === 'done').length,
)
const errorCount = computed(
  () => Object.values(props.progress).filter((state) => state === 'error').length,
)

function reindex(plan: ShotPlan): ShotPlan {
  return {
    ...plan,
    total_seconds: planSeconds(plan),
    shots: plan.shots.map((shot, index) => ({ ...shot, index: index + 1 })),
  }
}

function addShot() {
  const template = props.plan.shots[props.plan.shots.length - 1]
  emit(
    'update',
    reindex({
      ...props.plan,
      shots: [
        ...props.plan.shots,
        {
          index: props.plan.shots.length + 1,
          duration: template?.duration ?? '04s',
          scale: template?.scale ?? '中景 MS',
          lens: template?.lens ?? '50mm',
          move: template?.move ?? '固定机位 Static',
          purpose: '',
        },
      ],
    }),
  )
}

function removeShot(index: number) {
  if (props.plan.shots.length <= 1) return
  emit(
    'update',
    reindex({ ...props.plan, shots: props.plan.shots.filter((_, i) => i !== index) }),
  )
}

function durationChanged() {
  emit('update', reindex(props.plan))
}
</script>

<template>
  <section class="plan-panel">
    <header class="plan-head">
      <div>
        <p class="eyebrow">SHOT PLAN</p>
        <h3>镜头计划 · {{ props.plan.shots.length }} 镜 / {{ totalSeconds }}s</h3>
      </div>
      <div class="plan-head-actions">
        <div v-if="existing > 0" class="plan-mode" role="group" aria-label="展开结果的落盘方式">
          <button
            type="button"
            :class="{ chosen: mode === 'replace' }"
            :disabled="props.busy"
            @click="mode = 'replace'"
          >
            替换 {{ existing }} 张
          </button>
          <button
            type="button"
            :class="{ chosen: mode === 'append' }"
            :disabled="props.busy"
            @click="mode = 'append'"
          >
            追加到末尾
          </button>
        </div>
        <button class="login-ghost plan-cancel" type="button" :disabled="props.busy" @click="$emit('cancel')">
          放弃计划
        </button>
        <button class="login-submit plan-confirm" type="button" :disabled="props.busy" @click="emit('confirm', mode)">
          <LoaderCircle v-if="props.busy" class="spin" :size="15" />
          <Check v-else :size="15" />
          {{ props.busy ? `展开中 ${doneCount}/${props.plan.shots.length}` : '确认并展开提示词' }}
        </button>
      </div>
    </header>

    <p v-if="props.plan.narrative" class="plan-narrative">{{ props.plan.narrative }}</p>
    <p v-if="errorCount" class="plan-error">{{ errorCount }} 镜展开失败，可单独重试</p>

    <div class="plan-rows">
      <div
        v-for="(shot, index) in props.plan.shots"
        :key="shot.index"
        class="plan-row"
        :class="props.progress[shot.index] ? `is-${props.progress[shot.index]}` : ''"
      >
        <span class="plan-index">{{ String(index + 1).padStart(2, '0') }}</span>

        <select v-model="shot.duration" @change="durationChanged">
          <option v-for="option in DURATION_OPTIONS" :key="option" :value="option">{{ option }}</option>
        </select>
        <select v-model="shot.scale">
          <option v-for="option in SCALE_OPTIONS" :key="option" :value="option">{{ option }}</option>
        </select>
        <select v-model="shot.lens">
          <option v-for="option in LENS_OPTIONS" :key="option" :value="option">{{ option }}</option>
        </select>
        <select v-model="shot.move">
          <option v-for="option in MOVE_OPTIONS" :key="option" :value="option">{{ option }}</option>
        </select>
        <input v-model="shot.purpose" placeholder="这一镜的叙事功能" maxlength="40" />

        <span class="plan-state">
          <LoaderCircle v-if="props.progress[shot.index] === 'pending'" class="spin" :size="12" />
          <Check v-else-if="props.progress[shot.index] === 'done'" :size="12" />
          <X v-else-if="props.progress[shot.index] === 'error'" :size="12" />
        </span>

        <button
          class="plan-remove"
          type="button"
          aria-label="删除这一镜"
          :disabled="props.busy || props.plan.shots.length <= 1"
          @click="removeShot(index)"
        >
          <Trash2 :size="12" />
        </button>
      </div>
    </div>

    <button class="plan-add" type="button" :disabled="props.busy" @click="addShot">
      <Plus :size="13" />添加一镜
    </button>
  </section>
</template>
