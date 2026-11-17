<script setup lang="ts">
/**
 * 资产中心：把原来常驻右侧的「资产与灵感」独立成一个居中弹窗。
 *
 * 数据仍来自 useAssets 单例，和主界面共享同一份，不存在两边不同步。
 * 角色编辑/绑定仍由 App 负责（那两个弹层比本弹窗层级更高）。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Aperture, AudioLines, ArrowRight, LoaderCircle, Plus, Search, Tags, X } from 'lucide-vue-next'
import { ApiError } from '../api/client'
import { useAssets, type AssetTag, type Character, type TagCategory } from '../composables/useAssets'
import CharacterCard from './CharacterCard.vue'
import TagPanel from './TagPanel.vue'

const emit = defineEmits<{
  close: []
  create: []
  edit: [character: Character]
  remove: [character: Character]
}>()

const {
  characters,
  tags,
  loading,
  error,
  refresh,
  removeCharacterTags,
  createTag,
  updateTag,
  deleteTag,
} = useAssets()

const query = ref('')
const selectedTagId = ref<number | null>(null)

const visibleCharacters = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return characters.value.filter((character) => {
    if (selectedTagId.value !== null) {
      const ids = (character.tags ?? []).map((tag) => tag.id)
      if (!ids.includes(selectedTagId.value)) return false
    }
    if (!keyword) return true
    const haystack = `${character.name} ${character.role_label} ${character.description}`.toLowerCase()
    return haystack.includes(keyword)
  })
})

const filterTagName = computed(() => {
  if (selectedTagId.value === null) return ''
  return tags.value.find((tag) => tag.id === selectedTagId.value)?.name ?? ''
})

function retry() {
  void refresh()
}

function toggleTagFilter(tagId: number) {
  selectedTagId.value = selectedTagId.value === tagId ? null : tagId
}

async function detachTag(payload: { characterId: number; tagId: number }) {
  try {
    await removeCharacterTags(payload.characterId, [payload.tagId])
  } catch (exception) {
    window.alert(exception instanceof Error ? exception.message : '移除标签失败')
  }
}

async function createTagInCategory(category: TagCategory) {
  const name = window.prompt('新标签名')
  if (!name?.trim()) return
  try {
    const result = await createTag({ name: name.trim(), category, tone: 'neutral' })
    if (!result.created) window.alert(`标签「${result.tag.name}」已存在，已复用`)
  } catch (exception) {
    window.alert(exception instanceof Error ? exception.message : '新建标签失败')
  }
}

async function renameTag(tag: AssetTag) {
  const name = window.prompt('重命名标签', tag.name)
  if (!name?.trim() || name.trim() === tag.name) return
  try {
    await updateTag(tag.id, { name: name.trim() })
  } catch (exception) {
    window.alert(exception instanceof Error ? exception.message : '重命名失败')
  }
}

async function removeTag(tag: AssetTag) {
  try {
    await deleteTag(tag.id)
    clearFilterIfRemoved(tag.id)
    return
  } catch (exception) {
    const usedBy = exception instanceof ApiError ? (exception.data.used_by as { id: number; name: string }[] | undefined) : undefined
    if (!usedBy?.length) {
      window.alert(exception instanceof Error ? exception.message : '删除标签失败')
      return
    }
    const names = usedBy.map((item) => item.name).join('、')
    const confirmed = window.confirm(
      `标签「${tag.name}」正被 ${usedBy.length} 个角色使用：${names}。\n删除后会解除这些角色上的该标签（角色本身保留），继续？`,
    )
    if (!confirmed) return
    try {
      await deleteTag(tag.id, { force: true })
      clearFilterIfRemoved(tag.id)
    } catch (retryError) {
      window.alert(retryError instanceof Error ? retryError.message : '删除失败')
    }
  }
}

/** 删除标签后，如果它正被当作筛选条件，必须清掉，否则列表会莫名其妙变空。 */
function clearFilterIfRemoved(tagId: number) {
  if (selectedTagId.value === tagId) selectedTagId.value = null
}

function applyDirectorNote() {
  window.alert('已应用导演建议')
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  document.body.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="asset-gate" role="dialog" aria-modal="true" aria-label="资产与灵感" @click.self="emit('close')">
    <section class="asset-center">
      <header class="asset-center-head">
        <div>
          <p class="eyebrow">CREATIVE ASSETS</p>
          <h2>资产与灵感</h2>
        </div>
        <div class="asset-center-actions">
          <label class="asset-search">
            <Search :size="13" />
            <input v-model="query" placeholder="搜索角色名 / 类型 / 描述" />
          </label>
          <button class="text-action" type="button" @click="emit('create')">
            <Plus :size="13" />新建角色
          </button>
          <button class="icon-button" type="button" aria-label="关闭" @click="emit('close')">
            <X :size="16" />
          </button>
        </div>
      </header>

      <div v-if="loading && !characters.length" class="asset-center-state">
        <LoaderCircle class="spin" :size="16" />正在载入资产…
      </div>

      <div v-else-if="error" class="asset-center-state error">
        <span>{{ error }}</span>
        <button class="text-action" type="button" @click="retry">重试</button>
      </div>

      <div v-else class="asset-center-body">
        <section class="asset-center-column">
          <div class="asset-center-title">
            <span class="section-icon amber"><Aperture :size="14" /></span>
            <b>角色资产库</b>
            <span class="subtle">{{ visibleCharacters.length }} / {{ characters.length }}</span>
            <button
              v-if="selectedTagId !== null"
              class="asset-filter-clear"
              type="button"
              @click="selectedTagId = null"
            >
              筛选：{{ filterTagName }} <X :size="10" />
            </button>
          </div>

          <div class="asset-grid">
            <CharacterCard
              v-for="(character, index) in visibleCharacters"
              :key="character.id"
              :character="character"
              :index="index"
              @edit="emit('edit', character)"
              @remove="emit('remove', character)"
              @remove-tag="detachTag"
              @add-tag="emit('edit', character)"
            />
          </div>

          <p v-if="!visibleCharacters.length" class="asset-empty">
            {{ query || selectedTagId !== null ? '没有匹配的角色' : '还没有角色，点右上角「新建角色」' }}
          </p>
        </section>

        <section class="asset-center-column tags">
          <TagPanel
            :tags="tags"
            :selected="selectedTagId"
            @select="toggleTagFilter"
            @rename="renameTag"
            @remove="removeTag"
            @create="createTagInCategory"
          />

          <div class="insight-card asset-insight">
            <AudioLines :size="15" />
            <div>
              <span>DIRECTOR'S NOTE</span>
              <p>镜头与音乐鼓点的情绪峰值重合，试试缩短时长，让转场更有力量。</p>
              <button type="button" @click="applyDirectorNote">
                应用建议 <ArrowRight :size="12" />
              </button>
            </div>
          </div>
        </section>
      </div>

      <footer class="asset-center-foot">
        <span>角色与标签是项目级资产，绑定关系在故事板里逐镜维护</span>
        <span class="subtle"><Tags :size="11" /> {{ tags.length }} 个标签</span>
      </footer>
    </section>
  </div>
</template>
