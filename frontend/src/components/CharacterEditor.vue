<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { LoaderCircle, X } from 'lucide-vue-next'
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  TONE_OPTIONS,
  type AssetTag,
  type Character,
  type TagCategory,
  type Tone,
} from '../composables/useAssets'

const props = defineProps<{
  character: Character | null
  tags: AssetTag[]
  saving: boolean
  error: string
  /** 由父组件注入：创建标签并返回新标签，便于编辑框自动勾选。 */
  createTag: (payload: { name: string; category: TagCategory; tone: Tone }) => Promise<AssetTag>
}>()

const emit = defineEmits<{
  close: []
  save: [payload: { fields: Record<string, string | Tone>; tagIds: number[] }]
}>()

const name = ref('')
const roleLabel = ref('')
const description = ref('')
const promptAnchor = ref('')
const tone = ref<Tone>('amber')
const selected = ref<number[]>([])
const newTagName = ref('')
const newTagCategory = ref<TagCategory>('appearance')
const localError = ref('')

function reset() {
  const character = props.character
  name.value = character?.name ?? ''
  roleLabel.value = character?.role_label ?? ''
  description.value = character?.description ?? ''
  promptAnchor.value = character?.prompt_anchor ?? ''
  tone.value = character?.tone ?? 'amber'
  selected.value = character ? character.tags.map((tag) => tag.id) : []
  newTagName.value = ''
  localError.value = ''
}

watch(() => props.character, reset, { immediate: true })

const grouped = computed(() =>
  CATEGORY_ORDER.map((category) => ({
    category,
    label: CATEGORY_LABELS[category],
    items: props.tags.filter((tag) => tag.category === category),
  })).filter((group) => group.items.length),
)

const canSave = computed(() => name.value.trim().length > 0 && !props.saving)

function toggle(id: number) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((item) => item !== id)
    : [...selected.value, id]
}

function submit() {
  if (!canSave.value) return
  emit('save', {
    fields: {
      name: name.value.trim(),
      role_label: roleLabel.value.trim(),
      description: description.value.trim(),
      prompt_anchor: promptAnchor.value.trim(),
      tone: tone.value,
    },
    tagIds: [...selected.value],
  })
}

async function addTag() {
  const value = newTagName.value.trim()
  if (!value) return
  if (props.tags.some((tag) => tag.name === value)) {
    localError.value = '该标签已存在，勾选即可'
    return
  }
  localError.value = ''
  try {
    const tag = await props.createTag({
      name: value,
      category: newTagCategory.value,
      tone: 'neutral',
    })
    if (!selected.value.includes(tag.id)) selected.value = [...selected.value, tag.id]
    newTagName.value = ''
  } catch (exception) {
    localError.value = exception instanceof Error ? exception.message : '创建标签失败'
  }
}
</script>

<template>
  <div class="sheet-gate" role="dialog" aria-modal="true" aria-label="角色编辑">
    <form class="sheet-card" @submit.prevent="submit">
      <header class="sheet-head">
        <div>
          <p class="eyebrow">CHARACTER</p>
          <h3>{{ props.character ? '编辑角色' : '新建角色' }}</h3>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="$emit('close')">
          <X :size="15" />
        </button>
      </header>

      <div class="sheet-body">
        <label class="sheet-field">
          <span>角色名称</span>
          <input v-model="name" maxlength="40" placeholder="例如：天命人" required />
        </label>

        <label class="sheet-field">
          <span>类型 / 定位</span>
          <input v-model="roleLabel" maxlength="40" placeholder="例如：齐天大圣 · 核心角色" />
        </label>

        <label class="sheet-field">
          <span>描述</span>
          <textarea v-model="description" rows="2" placeholder="跨镜头视觉规范、出场语境……" />
        </label>

        <label class="sheet-field">
          <span>提示词锚点（英文，逗号分隔）</span>
          <input v-model="promptAnchor" placeholder="golden circlet, monkey warrior, brown fur" />
          <small class="sheet-hint">本轮只保存不启用：不会自动改写项目里的锚点</small>
        </label>

        <div class="sheet-field">
          <span>人像配色</span>
          <div class="tone-row">
            <button
              v-for="option in TONE_OPTIONS"
              :key="option"
              type="button"
              class="tone-dot"
              :class="[`tone-${option}`, { active: tone === option }]"
              :aria-label="option"
              @click="tone = option"
            ></button>
          </div>
        </div>

        <div class="sheet-field">
          <span>标签</span>
          <div v-for="group in grouped" :key="group.category" class="sheet-tag-group">
            <em>{{ group.label }}</em>
            <div class="cloud">
              <button
                v-for="tag in group.items"
                :key="tag.id"
                type="button"
                class="tag-chip"
                :class="[`t-${tag.tone}`, { active: selected.includes(tag.id) }]"
                @click="toggle(tag.id)"
              >
                {{ tag.name }}
              </button>
            </div>
          </div>

          <div class="sheet-newtag">
            <input v-model="newTagName" maxlength="24" placeholder="新标签名" />
            <select v-model="newTagCategory">
              <option v-for="category in CATEGORY_ORDER" :key="category" :value="category">
                {{ CATEGORY_LABELS[category] }}
              </option>
            </select>
            <button class="login-ghost" type="button" @click="addTag">新建</button>
          </div>
        </div>
      </div>

      <p v-if="localError || props.error" class="login-error">{{ localError || props.error }}</p>

      <footer class="sheet-actions">
        <button class="login-ghost" type="button" @click="$emit('close')">取消</button>
        <button class="login-submit" type="submit" :disabled="!canSave">
          <LoaderCircle v-if="props.saving" class="spin" :size="15" />保存
        </button>
      </footer>
    </form>
  </div>
</template>
