<script setup lang="ts">
/**
 * 单镜卡片：提示词是主体内容，参数压缩为徽标行。
 * F 组：显示绑定角色与一致性提醒；A 组：提供上移/下移重排。
 */
import { computed } from 'vue'
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Copy,
  Focus,
  ImagePlus,
  Link2,
  LoaderCircle,
  MessageSquareText,
  Send,
  Sparkles,
  Trash2,
  X,
} from 'lucide-vue-next'
import { paletteBackground, paletteLabel } from '../lib/palettes'
import { activePrompt, isRunway, type BindingChip, type Shot } from '../lib/types'
import SceneLayer from './SceneLayer.vue'

const props = defineProps<{
  shot: Shot
  index: number
  model: string
  anchors: string[]
  refining?: boolean
  bindings?: BindingChip[]
  canMoveUp?: boolean
  canMoveDown?: boolean
}>()

const emit = defineEmits<{
  copy: [shot: Shot]
  refine: [payload: { shot: Shot; instruction: string }]
  upload: [shot: Shot]
  removeReference: [shot: Shot]
  remove: [shot: Shot]
  bind: [shot: Shot]
  injectMissing: [shot: Shot]
  moveUp: []
  moveDown: []
}>()

const label = computed(() => `SHOT ${String(props.index + 1).padStart(2, '0')}`)
const background = computed(() => paletteBackground(props.shot.palette))
const promptText = computed(() => activePrompt(props.shot, props.model))
const hasReference = computed(() => Boolean(props.shot.reference_image_id))
const referenceUrl = computed(() => `/api/v1/uploads/${props.shot.reference_image_id}`)
const chips = computed(() => props.bindings ?? [])

/** 每个锚点是否真的出现在这条提示词里（中英都看）。 */
const anchorHits = computed(() => {
  const haystack = `${props.shot.prompt}\n${props.shot.runwayPrompt}`.toLowerCase()
  return props.anchors.map((text) => ({
    text,
    hit: haystack.includes(text.toLowerCase()),
  }))
})
const missingAnchors = computed(() => anchorHits.value.filter((item) => !item.hit))

function submitRefine() {
  const instruction = props.shot.edit.trim()
  if (!instruction || props.refining) return
  emit('refine', { shot: props.shot, instruction })
}
</script>

<template>
  <article class="shot-card" :id="`shot-card-${index}`" :data-shot-index="index">
    <div class="shot-top">
      <div class="shot-index">
        <span class="index-num">{{ String(index + 1).padStart(2, '0') }}</span>
        <div>
          <b>{{ label }}</b>
          <small>{{ paletteLabel(shot.palette) }}</small>
        </div>
      </div>
      <div class="shot-top-right">
        <span class="move-badge"><Focus :size="11" />{{ shot.move }}</span>
        <div class="shot-move-group">
          <button
            class="shot-move"
            type="button"
            aria-label="上移镜头"
            :disabled="!props.canMoveUp"
            @click="emit('moveUp')"
          >
            <ChevronUp :size="13" />
          </button>
          <button
            class="shot-move"
            type="button"
            aria-label="下移镜头"
            :disabled="!props.canMoveDown"
            @click="emit('moveDown')"
          >
            <ChevronDown :size="13" />
          </button>
        </div>
        <button
          class="shot-delete"
          type="button"
          aria-label="删除镜头"
          @click="emit('remove', shot)"
        >
          <Trash2 :size="13" />
        </button>
      </div>
    </div>

    <div class="scene-art" :style="{ backgroundImage: background }">
      <img v-if="hasReference" class="scene-reference" :src="referenceUrl" :alt="`${shot.title} 参考首帧`" />
      <SceneLayer v-else :scene="shot.scene" />
      <div class="scene-caption">
        <span>SCENE {{ String(index + 1).padStart(2, '0') }}</span>
        <span>{{ hasReference ? '参考首帧' : '待补首帧' }}</span>
      </div>
      <div class="scene-actions">
        <button type="button" :aria-label="hasReference ? '替换首帧' : '上传首帧'" @click="emit('upload', shot)">
          <ImagePlus :size="12" />
        </button>
        <button v-if="hasReference" type="button" aria-label="移除首帧" @click="emit('removeReference', shot)">
          <X :size="12" />
        </button>
      </div>
    </div>

    <div class="shot-copy">
      <input v-model="shot.title" :aria-label="`镜头 ${index + 1} 标题`" />
      <div class="shot-meta">
        <span>{{ shot.duration }}</span>
        <span>{{ shot.scale }}</span>
        <span>{{ shot.lens }}</span>
      </div>

      <div class="shot-bindings">
        <span
          v-for="chip in chips"
          :key="chip.id"
          class="binding-chip"
          :class="{ missing: chip.missing }"
          :title="chip.missing ? `「${chip.name}」的锚点没有出现在这条提示词里` : `已绑定「${chip.name}」`"
        >
          <AlertTriangle v-if="chip.missing" :size="9" />
          {{ chip.name }}
        </span>
        <button class="binding-add" type="button" @click="emit('bind', shot)">
          <Link2 :size="10" />{{ chips.length ? '调整角色' : '绑定角色' }}
        </button>
      </div>

      <textarea v-model="shot.description" rows="2" aria-label="画面描述"></textarea>
    </div>

    <div class="prompt-block">
      <div class="prompt-head">
        <span><Sparkles :size="12" /> AI PROMPT · {{ model }}</span>
        <button class="copy-btn" type="button" @click="emit('copy', shot)">
          <Copy :size="12" />一键复制
        </button>
      </div>
      <div class="prompt-text">{{ promptText || '尚未生成提示词' }}</div>
      <div class="prompt-foot">
        <span class="anchor-status">
          <template v-if="anchorHits.length">
            <span
              v-for="item in anchorHits"
              :key="item.text"
              class="anchor-pill"
              :class="{ miss: !item.hit }"
              :title="item.hit ? '已在提示词中出现' : '这条提示词里没有这个锚点'"
            >
              <AlertTriangle v-if="!item.hit" :size="8" />{{ item.text }}
            </span>
          </template>
          <b v-else>未设置角色锚点</b>
        </span>
        <span class="prompt-foot-right">
          <button
            v-if="missingAnchors.length"
            class="anchor-fix"
            type="button"
            :title="`把缺失的 ${missingAnchors.length} 个锚点补到提示词开头`"
            @click="emit('injectMissing', shot)"
          >
            补齐 {{ missingAnchors.length }} 个
          </button>
          <span>{{ promptText.length }} 字符 · {{ isRunway(model) ? '英文' : '中文' }}</span>
        </span>
      </div>
    </div>

    <div class="tweak-row">
      <MessageSquareText :size="14" />
      <input
        v-model="shot.edit"
        placeholder="输入单镜微调要求，例如：改为赛博朋克霓虹灯"
        @keydown.enter="submitRefine"
      />
      <button :disabled="!shot.edit.trim() || refining" aria-label="发送镜头微调" @click="submitRefine">
        <LoaderCircle v-if="refining" class="spin" :size="14" />
        <Send v-else :size="14" />
      </button>
    </div>
  </article>
</template>
