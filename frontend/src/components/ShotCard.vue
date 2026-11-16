<script setup lang="ts">
/**
 * 单镜卡片：提示词是主体内容，参数压缩为徽标行。
 */
import { computed } from 'vue'
import {
  Copy,
  Focus,
  ImagePlus,
  LoaderCircle,
  MessageSquareText,
  Send,
  Sparkles,
  Trash2,
  X,
} from 'lucide-vue-next'
import { paletteBackground, paletteLabel } from '../lib/palettes'
import { activePrompt, isRunway, type Shot } from '../lib/types'
import SceneLayer from './SceneLayer.vue'

const props = defineProps<{
  shot: Shot
  index: number
  model: string
  anchors: string[]
  refining?: boolean
}>()

const emit = defineEmits<{
  copy: [shot: Shot]
  refine: [payload: { shot: Shot; instruction: string }]
  upload: [shot: Shot]
  removeReference: [shot: Shot]
  remove: [shot: Shot]
}>()

const label = computed(() => `SHOT ${String(props.index + 1).padStart(2, '0')}`)
const background = computed(() => paletteBackground(props.shot.palette))
const promptText = computed(() => activePrompt(props.shot, props.model))
const hasReference = computed(() => Boolean(props.shot.reference_image_id))
const referenceUrl = computed(() => `/api/v1/uploads/${props.shot.reference_image_id}`)

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
        <span>
          <b v-if="anchors.length">{{ anchors.join(' · ') }}</b>
          <b v-else>未设置角色锚点</b>
        </span>
        <span>{{ promptText.length }} 字符 · {{ isRunway(model) ? '英文' : '中文' }}</span>
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
