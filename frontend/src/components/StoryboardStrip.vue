<script setup lang="ts">
/**
 * C3：等宽缩略导航条。
 *
 * 明确不是时间轴：每格宽度相同，不显示时长、没有播放头，只用于定位。
 */
import { paletteBackground } from '../lib/palettes'
import type { Shot } from '../lib/types'

const props = defineProps<{
  shots: Shot[]
  activeIndex: number | null
}>()

defineEmits<{ select: [index: number] }>()
</script>

<template>
  <nav v-if="props.shots.length > 1" class="board-strip" aria-label="镜头导航">
    <button
      v-for="(shot, index) in props.shots"
      :key="shot.id"
      type="button"
      class="strip-item"
      :class="{ active: props.activeIndex === index }"
      :aria-label="`定位到第 ${index + 1} 镜`"
      @click="$emit('select', index)"
    >
      <span class="strip-thumb" :style="{ backgroundImage: paletteBackground(shot.palette) }">
        <img
          v-if="shot.reference_image_id"
          :src="`/api/v1/uploads/${shot.reference_image_id}`"
          alt=""
        />
      </span>
      <span class="strip-index">{{ String(index + 1).padStart(2, '0') }}</span>
    </button>
  </nav>
</template>
