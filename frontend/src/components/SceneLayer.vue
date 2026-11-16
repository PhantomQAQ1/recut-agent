<script setup lang="ts">
/**
 * 场景层：叠在调色板渐变之上的一层轻量 SVG 装饰。
 *
 * 之前 `scene` 字段有定义但从未渲染，这里把它落到画面上。
 * 用 useId() 生成唯一 id，避免多张卡片同时出现时 SVG 渐变 id 冲突。
 */
import { useId } from 'vue'
import type { SceneKind } from '../lib/types'

const props = defineProps<{ scene: SceneKind }>()
const uid = useId()
const glowId = `glow-${uid}`
const sparkId = `spark-${uid}`
</script>

<template>
  <div class="scene-layer" aria-hidden="true">
    <svg v-if="props.scene === 'lantern'" viewBox="0 0 320 140" preserveAspectRatio="none">
      <defs>
        <radialGradient :id="glowId">
          <stop offset="0%" stop-color="#fbbf24" stop-opacity="0.55" />
          <stop offset="100%" stop-color="#fbbf24" stop-opacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="246" cy="30" rx="58" ry="38" :fill="`url(#${glowId})`" />
      <rect x="244" y="2" width="1.6" height="22" fill="#f59e0b" opacity="0.5" />
      <circle cx="246" cy="32" r="6.5" fill="#fcd34d" opacity="0.8" />
      <ellipse cx="70" cy="118" rx="82" ry="32" :fill="`url(#${glowId})`" opacity="0.45" />
      <ellipse cx="176" cy="126" rx="46" ry="20" fill="#0b1220" opacity="0.5" />
    </svg>

    <svg v-else-if="props.scene === 'curtain'" viewBox="0 0 320 140" preserveAspectRatio="none">
      <path d="M0 0h86c-16 40-22 92-12 140H0Z" fill="#0b1220" opacity="0.62" />
      <path d="M320 0h-78c14 38 20 90 11 140h67Z" fill="#0b1220" opacity="0.58" />
      <path d="M132 0c10 34 12 96 4 140h48c-8-44-6-106 4-140Z" fill="#0b1220" opacity="0.34" />
      <path d="M96 0h14c-6 46-6 96 0 140H96c-8-46-8-96 0-140Z" fill="#f8fafc" opacity="0.07" />
      <path d="M214 0h14c8 44 8 94 0 140h-14c6-46 6-96 0-140Z" fill="#f8fafc" opacity="0.06" />
    </svg>

    <svg v-else viewBox="0 0 320 140" preserveAspectRatio="none">
      <defs>
        <radialGradient :id="sparkId">
          <stop offset="0%" stop-color="#fde68a" stop-opacity="0.95" />
          <stop offset="100%" stop-color="#f97316" stop-opacity="0" />
        </radialGradient>
      </defs>
      <circle cx="78" cy="96" r="16" :fill="`url(#${sparkId})`" />
      <circle cx="124" cy="70" r="10" :fill="`url(#${sparkId})`" />
      <circle cx="186" cy="104" r="13" :fill="`url(#${sparkId})`" />
      <circle cx="238" cy="58" r="8" :fill="`url(#${sparkId})`" />
      <circle cx="270" cy="112" r="11" :fill="`url(#${sparkId})`" />
      <path d="M28 128 148 38" stroke="#fcd34d" stroke-width="1.2" opacity="0.35" />
      <path d="M196 126 286 46" stroke="#fb923c" stroke-width="1" opacity="0.28" />
    </svg>
  </div>
</template>
