<script setup lang="ts">
/** F1：给单个镜头挑选要绑定的角色资产。 */
import { computed, ref } from 'vue'
import { AlertTriangle, Check, Link2, X } from 'lucide-vue-next'
import { anchorTokens } from '../lib/consistency'
import type { Character } from '../composables/useAssets'

const props = defineProps<{
  characters: Character[]
  selected: number[]
  prompt: string
}>()

const emit = defineEmits<{
  apply: [ids: number[]]
  close: []
}>()

const chosen = ref<number[]>([...props.selected])

const missingInPrompt = (character: Character) => {
  const haystack = props.prompt.toLowerCase()
  if (haystack.includes(character.name.toLowerCase())) return false
  const tokens = anchorTokens(character)
  return !tokens.some((token) => haystack.includes(token.toLowerCase()))
}

const warningCount = computed(
  () => chosen.value.filter((id) => {
    const character = props.characters.find((item) => item.id === id)
    return character ? missingInPrompt(character) : false
  }).length,
)

function toggle(id: number) {
  chosen.value = chosen.value.includes(id)
    ? chosen.value.filter((item) => item !== id)
    : [...chosen.value, id]
}
</script>

<template>
  <div class="sheet-gate" role="dialog" aria-modal="true" aria-label="绑定角色">
    <div class="sheet-card">
      <header class="sheet-head">
        <div>
          <p class="eyebrow">CHARACTER BINDING</p>
          <h3>绑定到这一镜</h3>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="$emit('close')">
          <X :size="15" />
        </button>
      </header>

      <p class="sheet-hint">
        绑定的角色会把它的提示词锚点带进微调请求；提示词里没提到的角色会被标黄提醒。
      </p>

      <div v-if="!props.characters.length" class="asset-empty">
        资产库还没有角色，先到右侧「角色资产库」新建一个。
      </div>

      <div class="binding-list">
        <button
          v-for="character in props.characters"
          :key="character.id"
          type="button"
          class="binding-option"
          :class="{ active: chosen.includes(character.id) }"
          @click="toggle(character.id)"
        >
          <span class="binding-mark">
            <Check v-if="chosen.includes(character.id)" :size="12" />
          </span>
          <span class="binding-body">
            <b>{{ character.name }}</b>
            <small>{{ character.role_label || '未设置类型' }}</small>
            <em v-if="character.prompt_anchor">{{ character.prompt_anchor }}</em>
          </span>
          <AlertTriangle
            v-if="chosen.includes(character.id) && missingInPrompt(character)"
            class="binding-warn"
            :size="13"
          />
        </button>
      </div>

      <p v-if="warningCount" class="login-error">
        {{ warningCount }} 个已选角色的锚点还没出现在这条提示词里，可在卡片上点「注入锚点」补齐。
      </p>

      <footer class="sheet-actions">
        <button class="login-ghost" type="button" @click="$emit('close')">取消</button>
        <button class="login-submit" type="button" @click="emit('apply', chosen)">
          <Link2 :size="15" />保存绑定
        </button>
      </footer>
    </div>
  </div>
</template>
