<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import LoginDialog from './components/LoginDialog.vue'
import UserMenu from './components/UserMenu.vue'
import CharacterCard from './components/CharacterCard.vue'
import CharacterEditor from './components/CharacterEditor.vue'
import TagPanel from './components/TagPanel.vue'
import { api } from './api/client'
import { useAuth } from './composables/useAuth'
import {
  useAssets,
  type AssetTag,
  type Character,
  type TagCategory,
  type Tone,
} from './composables/useAssets'
import { Aperture, ArrowDownToLine, ArrowRight, AudioLines, Check, ChevronDown, Clapperboard, Copy, Film, Focus, Layers3, LoaderCircle, LockKeyhole, MessageSquareText, MoreHorizontal, Plus, ScanLine, Send, SlidersHorizontal, Sparkles, Upload, WandSparkles, X } from 'lucide-vue-next'

type Shot = { id: number; duration: string; scale: string; lens: string; move: string; title: string; description: string; prompt: string; runwayPrompt: string; edit: string; palette: string; scene: string }
const models = ['即梦 Jimeng', '可灵 Kling', 'Runway Gen-3']
const model = ref(models[0])
const mode = ref<'forward' | 'reverse'>('forward')
const viewMode = ref<'grid' | 'list'>('grid')
const project = ref('黑神话：最后一盏灯')
const idea = ref('黄昏时分，天命人走进一座被遗忘的戏台。台上空无一人，锣鼓却自己响了起来……')
const style = ref('燃向踩点')
const styles = ['搞笑反转', '燃向踩点', '黑深残', '日常整活']
const anchors = ref(['golden circlet', 'monkey warrior', 'brown fur'])
const loading = ref(false)
const toast = ref('')
const selectedFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const shots = ref<Shot[]>([
  { id: 1, duration: '04s', scale: '特写 ECU', lens: '85mm', move: '急速推镜 Crash Zoom', title: '铜锣无风自鸣，天命人蓦然回首', description: '黄昏余晖落在古旧戏台。沉睡的铜锣突然震颤，近处扬起一层薄灰；天命人停步，眼神从松弛转为警觉。', prompt: 'golden circlet, monkey warrior, brown fur, 夕阳下的古戏台，铜锣无风自鸣，扬起细微尘埃。天命人突然回头，瞳孔映出暖金色余晖。电影级光影，浅景深，胶片颗粒，紧张氛围。', runwayPrompt: 'An 85mm extreme close-up of a bronze gong vibrating in an abandoned Chinese opera stage at golden hour. A monkey warrior with brown fur and a golden circlet suddenly turns back; dust drifts through warm amber light. Crash zoom, shallow depth of field, cinematic film grain, tense atmosphere.', edit: '', palette: 'from-amber-950 via-orange-950 to-slate-950', scene: 'lantern' },
  { id: 2, duration: '06s', scale: '中景 MS', lens: '50mm', move: '环绕跟拍 Orbit', title: '旧戏幕层层掀起，空台上显出一双脚印', description: '褪色戏幕被风般的力量缓缓卷起，镜头绕过天命人肩侧。空荡舞台积尘之上，多出一串湿润的脚印，延向黑暗。', prompt: 'golden circlet, monkey warrior, brown fur, 褪色戏幕无风自启，空旷戏台浮现湿漉漉的脚印。镜头环绕角色肩侧，远处烛火摇曳，冷暖交织的阴森电影感。高反差光影，神秘东方志怪氛围。', runwayPrompt: 'A 50mm medium shot orbiting a monkey warrior with brown fur and a golden circlet as faded opera curtains lift by themselves. Wet footprints appear across the dusty empty stage, leading into darkness. Flickering candlelight, cool-warm contrast, high-contrast cinematic lighting, mysterious folklore mood.', edit: '', palette: 'from-indigo-950 via-slate-900 to-amber-950', scene: 'curtain' },
  { id: 3, duration: '05s', scale: '全景 WS', lens: '28mm', move: '低机位升格 Low angle', title: '鼓点骤然炸响，天命人举棍迎向台上黑影', description: '鼓声切入的瞬间，天命人踏上戏台，金箍棒横扫，火星照亮帷幕后巨大的轮廓。画面定格在棍梢燃起的一点金光。', prompt: 'golden circlet, monkey warrior, brown fur, 天命人跃上古戏台挥动金箍棒，火星四溅，身后帷幕浮现巨大黑色轮廓。低角度升格镜头，金色火光勾勒毛发和盔甲，东方奇幻史诗电影，强烈戏剧张力。', runwayPrompt: 'A 28mm wide low-angle shot in slow motion: a monkey warrior with brown fur and a golden circlet leaps onto an ancient opera stage, staff sweeping as sparks scatter. A towering shadow emerges behind the curtain. Golden rim light, epic eastern fantasy cinema, dramatic tension.', edit: '', palette: 'from-red-950 via-amber-950 to-slate-950', scene: 'sparks' },
])
const activePrompt = (shot: Shot) => model.value.includes('Runway') ? shot.runwayPrompt : shot.prompt
const modelHint = computed(() => model.value.includes('Runway') ? '结构化英文提示词' : '中文自然语言提示词')
const formatSize = (size: number) => size < 1024 * 1024 ? `${(size / 1024).toFixed(1)} KB` : `${(size / (1024 * 1024)).toFixed(2)} MB`
function notify(message: string) { toast.value = message; window.setTimeout(() => toast.value = '', 2200) }
async function copyPrompt(shot: Shot) { try { await navigator.clipboard.writeText(activePrompt(shot)); notify('提示词已复制到剪贴板') } catch { notify('复制失败，请检查浏览器剪贴板权限') } }
async function generate() {
  if (loading.value || !isAuthenticated.value) return
  loading.value = true
  try {
    const data = await api.post<{ shots?: Shot[] }>('/api/v1/storyboard/generate', {
      idea: idea.value,
      style: style.value,
      anchors: anchors.value,
      model: model.value,
    })
    const next = data.shots ?? []
    if (!next.length) throw new Error('模型没有返回镜头，请调整梗概后重试')
    shots.value = next
    notify(`已生成 ${next.length} 个镜头`)
  } catch (error) {
    // 失败时保留当前故事板（含演示分镜），只把原因提示给用户。
    notify(`生成失败：${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    loading.value = false
  }
}
function acceptFile(file?: File) { if (!file) return; selectedFile.value = file; notify(`已选择素材：${file.name}`) }
function onFileChange(event: Event) { acceptFile((event.target as HTMLInputElement).files?.[0]) }
function onDrop(event: DragEvent) { acceptFile(event.dataTransfer?.files?.[0]) }
async function reverse() {
  if (loading.value || !isAuthenticated.value) return
  if (!selectedFile.value) { notify('请先上传视频或图片素材'); return }
  loading.value = true
  try {
    const body = new FormData()
    body.append('file', selectedFile.value)
    body.append('model', model.value)
    body.append('anchors', anchors.value.join(','))
    const data = await api.upload<{ shots?: Shot[] }>('/api/v1/storyboard/reverse', body)
    const next = data.shots ?? []
    if (!next.length) throw new Error('没有解析出镜头，请更换素材后重试')
    shots.value = next
    notify(`已解析 ${next.length} 个镜头`)
  } catch (error) {
    notify(`解析失败：${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    loading.value = false
  }
}
function refineShot(shot: Shot) { const request = shot.edit.trim(); if (!request) return; shot.description = `${shot.description} 画面微调：${request}。`; shot.prompt = `${shot.prompt} 画面调整：${request}。`; shot.runwayPrompt = `${shot.runwayPrompt} Visual refinement: ${request}.`; shot.edit = ''; notify(`Shot ${String(shot.id).padStart(2, '0')} 已更新`) }
function addAnchor() { const value = window.prompt('输入角色视觉锚点'); if (value?.trim()) anchors.value.push(value.trim()) }
function addShot() { const previous = shots.value[shots.value.length - 1]; shots.value.push({ ...previous, id: Date.now(), title: '新镜头：点击此处开始创作', description: '为这个镜头补充核心剧情与画面描述……', prompt: `${anchors.value.join(', ')}, 新镜头画面描述，电影级光影，细腻质感。`, runwayPrompt: `Cinematic shot, ${anchors.value.join(', ')}, describe the new scene, cinematic lighting.`, edit: '' }) }
// --------------------------------------------------------------------------- //
// 认证 + 项目持久化
// --------------------------------------------------------------------------- //

const { user, isAuthenticated, bootstrapping, bootstrap } = useAuth()

type ProjectSummary = { id: number; name: string; updated_at: string }
type StoryboardDoc = { shots: Shot[]; style: string; model: string; anchors: string[] }

const projectId = ref<number | null>(null)
const projectList = ref<ProjectSummary[]>([])
const projectMenuOpen = ref(false)
const saveState = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')
const saveMessage = ref('')
// 载入项目期间不要触发自动保存，否则会用旧数据覆盖刚打开的项目。
let hydrating = false
let saveTimer: number | undefined

function storyboardDoc(): StoryboardDoc {
  return { shots: shots.value, style: style.value, model: model.value, anchors: anchors.value }
}

function applyStoryboard(doc: Partial<StoryboardDoc> | undefined) {
  if (!doc) return
  if (Array.isArray(doc.shots)) shots.value = doc.shots as Shot[]
  if (typeof doc.style === 'string') style.value = doc.style
  if (typeof doc.model === 'string') model.value = doc.model
  if (Array.isArray(doc.anchors)) anchors.value = doc.anchors as string[]
}

async function refreshProjects() {
  try {
    const data = await api.get<{ projects: ProjectSummary[] }>('/api/v1/projects')
    projectList.value = data.projects
  } catch {
    /* 列表拉取失败不影响继续编辑 */
  }
}

async function openProject(id: number) {
  hydrating = true
  try {
    const data = await api.get<{ id: number; name: string; storyboard: Partial<StoryboardDoc> }>(
      `/api/v1/projects/${id}`,
    )
    projectId.value = data.id
    project.value = data.name
    applyStoryboard(data.storyboard)
    saveState.value = 'saved'
    saveMessage.value = '刚刚'
  } catch (error) {
    notify(error instanceof Error ? `打开项目失败：${error.message}` : '打开项目失败')
  } finally {
    projectMenuOpen.value = false
    window.setTimeout(() => {
      hydrating = false
    }, 0)
  }
}

async function createProject() {
  try {
    const data = await api.post<{ id: number }>('/api/v1/projects', {
      name: '未命名项目',
      storyboard: { shots: [], style: style.value, model: model.value, anchors: anchors.value },
    })
    await refreshProjects()
    await openProject(data.id)
    notify('已创建新项目')
  } catch (error) {
    notify(error instanceof Error ? `新建项目失败：${error.message}` : '新建项目失败')
  }
}

async function switchProject(id: number) {
  if (id === projectId.value) {
    projectMenuOpen.value = false
    return
  }
  await openProject(id)
}

function scheduleSave() {
  if (!isAuthenticated.value || hydrating || projectId.value === null) return
  window.clearTimeout(saveTimer)
  saveState.value = 'saving'
  saveTimer = window.setTimeout(persistProject, 1200)
}

async function persistProject() {
  const id = projectId.value
  if (id === null || !isAuthenticated.value) return
  try {
    await api.put(`/api/v1/projects/${id}`, {
      name: project.value.trim() || '未命名项目',
      storyboard: storyboardDoc(),
    })
    saveState.value = 'saved'
    saveMessage.value = '刚刚'
  } catch (error) {
    saveState.value = 'error'
    saveMessage.value = error instanceof Error ? error.message : '保存失败'
  }
}

const saveLabel = computed(() => {
  if (!isAuthenticated.value) return '未登录 · 改动不会保存'
  if (saveState.value === 'saving') return '保存中…'
  if (saveState.value === 'error') return `保存失败：${saveMessage.value}`
  return `已保存 · ${saveMessage.value || '刚刚'}`
})

/** 登录后载入项目；退出登录时保留画面内容，不清空故事板。 */
async function syncProjects() {
  if (!isAuthenticated.value) {
    projectList.value = []
    projectId.value = null
    return
  }
  await refreshProjects()
  if (!projectList.value.length) {
    // 第一次登录：把当前（演示）故事板存成第一个项目，避免空白页。
    const created = await api.post<{ id: number }>('/api/v1/projects', {
      name: project.value.trim() || '未命名项目',
      storyboard: storyboardDoc(),
    })
    await refreshProjects()
    projectId.value = created.id
    saveState.value = 'saved'
    saveMessage.value = '刚刚'
  } else if (projectId.value === null) {
    await openProject(projectList.value[0]!.id)
  }
}

// --------------------------------------------------------------------------- //
// 角色资产与标签
// --------------------------------------------------------------------------- //

const {
  characters: assetCharacters,
  tags: assetTags,
  ensureLoaded: ensureAssetsLoaded,
  reset: resetAssets,
  createCharacter,
  updateCharacter,
  deleteCharacter,
  addCharacterTags,
  removeCharacterTags,
  createTag: createAssetTag,
  updateTag: renameAssetTag,
  deleteTag: deleteAssetTag,
} = useAssets()

const editorOpen = ref(false)
const editingCharacter = ref<Character | null>(null)
const savingCharacter = ref(false)
const editorError = ref('')
const selectedTagId = ref<number | null>(null)

const visibleCharacters = computed(() =>
  selectedTagId.value === null
    ? assetCharacters.value
    : assetCharacters.value.filter((character) =>
        character.tags.some((tag) => tag.id === selectedTagId.value),
      ),
)

const errorText = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback

function openEditor(character: Character | null) {
  editingCharacter.value = character
  editorError.value = ''
  editorOpen.value = true
}

function closeEditor() {
  editorOpen.value = false
  editingCharacter.value = null
  editorError.value = ''
}

async function saveCharacter(payload: {
  fields: Record<string, string | Tone>
  tagIds: number[]
}) {
  savingCharacter.value = true
  editorError.value = ''
  const fields = payload.fields
  const body = {
    name: String(fields.name ?? ''),
    role_label: String(fields.role_label ?? ''),
    description: String(fields.description ?? ''),
    prompt_anchor: String(fields.prompt_anchor ?? ''),
    tone: fields.tone as Tone,
  }
  try {
    if (editingCharacter.value) {
      const current = editingCharacter.value
      const before = new Set(current.tags.map((tag) => tag.id))
      const after = new Set(payload.tagIds)
      await updateCharacter(current.id, body)
      const added = [...after].filter((id) => !before.has(id))
      const removed = [...before].filter((id) => !after.has(id))
      if (added.length) await addCharacterTags(current.id, added)
      if (removed.length) await removeCharacterTags(current.id, removed)
      notify(`已更新角色「${body.name}」`)
    } else {
      await createCharacter({ ...body, tag_ids: payload.tagIds })
      notify(`已创建角色「${body.name}」`)
    }
    closeEditor()
  } catch (error) {
    editorError.value = errorText(error, '保存失败')
  } finally {
    savingCharacter.value = false
  }
}

async function removeCharacter(character: Character) {
  if (!window.confirm(`删除角色「${character.name}」？此操作不可恢复。`)) return
  try {
    await deleteCharacter(character.id)
    notify(`已删除角色「${character.name}」`)
  } catch (error) {
    notify(`删除失败：${errorText(error, '未知错误')}`)
  }
}

async function detachTag(payload: { characterId: number; tagId: number }) {
  try {
    await removeCharacterTags(payload.characterId, [payload.tagId])
    notify('已移除标签')
  } catch (error) {
    notify(`移除标签失败：${errorText(error, '未知错误')}`)
  }
}

async function createTagFromEditor(payload: {
  name: string
  category: TagCategory
  tone: Tone
}) {
  const result = await createAssetTag(payload)
  if (!result.created) notify(`标签「${result.tag.name}」已存在，已复用`)
  return result.tag
}

async function createTagFromPanel(category: TagCategory) {
  const name = window.prompt('新标签名')
  if (!name?.trim()) return
  try {
    const result = await createAssetTag({ name: name.trim(), category, tone: 'neutral' })
    notify(
      result.created
        ? `已创建标签「${result.tag.name}」`
        : `标签「${result.tag.name}」已存在，已复用`,
    )
  } catch (error) {
    notify(`新建标签失败：${errorText(error, '未知错误')}`)
  }
}

async function renameTag(tag: AssetTag) {
  const name = window.prompt('重命名标签', tag.name)
  if (!name?.trim() || name.trim() === tag.name) return
  try {
    await renameAssetTag(tag.id, { name: name.trim() })
    notify('标签已重命名')
  } catch (error) {
    notify(`重命名失败：${errorText(error, '未知错误')}`)
  }
}

async function removeTag(tag: AssetTag) {
  try {
    await deleteAssetTag(tag.id)
    notify(`已删除标签「${tag.name}」`)
    return
  } catch (error) {
    // 409：标签仍被引用。后端会带回 used_by，提示后改为"仅解绑"。
    const usedBy = (error as { data?: { used_by?: { id: number; name: string }[] } }).data
      ?.used_by
    if (usedBy?.length) {
      const names = usedBy.map((item) => item.name).join('、')
      const confirmed = window.confirm(
        `标签「${tag.name}」正被 ${usedBy.length} 个角色使用：${names}。\n删除后会解除这些角色上的该标签（角色本身保留），继续？`,
      )
      if (!confirmed) return
      try {
        await deleteAssetTag(tag.id, { force: true })
        notify(`已删除标签「${tag.name}」`)
      } catch (retryError) {
        notify(`删除失败：${errorText(retryError, '未知错误')}`)
      }
      return
    }
    notify(`删除失败：${errorText(error, '未知错误')}`)
  }
}

function toggleTagFilter(tagId: number) {
  selectedTagId.value = selectedTagId.value === tagId ? null : tagId
}

onMounted(async () => {
  await bootstrap()
  try {
    await syncProjects()
  } catch (error) {
    // 项目初始化失败不影响继续编辑（可能是离线或后端刚重启）。
    notify(error instanceof Error ? `项目初始化失败：${error.message}` : '项目初始化失败')
  }
  if (isAuthenticated.value) await ensureAssetsLoaded()
})

watch([project, style, model, anchors, shots], scheduleSave, { deep: true })

watch(user, async (current, previous) => {
  if (current && !previous) {
    try {
      await syncProjects()
      await ensureAssetsLoaded()
    } catch (error) {
      notify(error instanceof Error ? `初始化失败：${error.message}` : '初始化失败')
    }
  }
  if (!current) {
    projectMenuOpen.value = false
    // 换账号后必须清空项目指针，否则会把下一位用户的项目 id 当自己的用。
    projectId.value = null
    selectedTagId.value = null
    resetAssets()
  }
})

onBeforeUnmount(() => window.clearTimeout(saveTimer))

</script>

<template>
  <div class="app-shell min-h-screen bg-slate-950 text-slate-100">
    <header class="topbar flex h-[66px] items-center justify-between border-b border-slate-800/80 px-7">
      <div class="flex min-w-0 items-center gap-7"><a class="brand flex items-center gap-2.5" href="#"><span class="brand-icon"><Clapperboard :size="19" /></span><span>ReCut <i>Agent</i></span></a><div class="h-6 w-px bg-slate-800"></div><div class="project-name flex items-center gap-2"><span>PROJECT</span><input v-model="project" aria-label="项目标题" :disabled="!isAuthenticated" /><button class="project-toggle" type="button" aria-label="切换项目" @click="projectMenuOpen = !projectMenuOpen"><ChevronDown :size="14" /></button><div v-if="projectMenuOpen" class="project-menu"><button v-for="item in projectList" :key="item.id" type="button" :class="{ current: item.id === projectId }" @click="switchProject(item.id)">{{ item.name }}</button><button class="new-project" type="button" @click="createProject">+ 新建项目</button></div></div></div>
      <div class="flex items-center gap-3"><span class="hidden text-[11px] text-slate-500 md:block">生成模型</span><div class="select-wrap"><select v-model="model" aria-label="选择生成模型"><option v-for="item in models" :key="item">{{ item }}</option></select><ChevronDown :size="14" /></div><button class="export-btn" @click="notify('剪映草稿已准备导出')"><ArrowDownToLine :size="15" />导出剪映草稿</button><UserMenu v-if="isAuthenticated" /></div>
    </header>
    <div class="workspace">
      <aside class="left-panel"><div class="panel-heading"><div><p class="eyebrow">WORKSPACE</p><h2>创作工作台</h2></div><button class="icon-button"><SlidersHorizontal :size="16" /></button></div>
        <div class="mode-switch"><button :class="{ active: mode === 'forward' }" @click="mode = 'forward'"><Sparkles :size="14" />正向生成</button><button :class="{ active: mode === 'reverse' }" @click="mode = 'reverse'"><ScanLine :size="14" />逆向拆解</button></div>
        <template v-if="mode === 'forward'"><div class="field-label"><span>剧情梗概</span><span class="muted">灵感由此开始</span></div><textarea v-model="idea" class="idea-input" rows="5"></textarea><div class="field-label style-heading"><span>二创风格</span><span class="muted">选择一种叙事基调</span></div><div class="style-grid"><button v-for="item in styles" :key="item" :class="{ chosen: style === item }" @click="style = item">{{ item }}</button></div></template>
        <template v-else><div class="field-label"><span>参考素材</span><span class="muted">5–15 秒为佳</span></div><input ref="fileInput" class="hidden-file" type="file" accept="video/*,image/*" @change="onFileChange" /><div class="upload-box" role="button" tabindex="0" @click="fileInput?.click()" @keydown.enter="fileInput?.click()" @dragover.prevent @drop.prevent="onDrop"><Upload :size="21" /><b>拖拽视频或漫画切片至此</b><span>支持 MP4、MOV、PNG、JPG</span><template v-if="selectedFile"><strong>{{ selectedFile.name }}</strong><span>{{ formatSize(selectedFile.size) }}</span></template></div><button class="generate-btn mt-4" :disabled="loading" @click="reverse"><LoaderCircle v-if="loading" class="spin" :size="16" /><ScanLine v-else :size="16" />{{ loading ? '正在解析视听语言…' : '一键解析视听语言' }}<ArrowRight :size="15" /></button></template>
        <section class="anchor-card"><div class="anchor-head"><span class="anchor-symbol"><LockKeyhole :size="15" /></span><div><b>角色一致性锚点</b><small>CHARACTER ANCHORS</small></div><button class="mini-add" @click="addAnchor"><Plus :size="15" /></button></div><p class="anchor-name">天命人</p><div class="anchor-tags"><button v-for="tag in anchors" :key="tag" class="anchor-tag" @click="anchors = anchors.filter(x => x !== tag)">{{ tag }} <X :size="10" /></button></div><p class="anchor-note">已锁定 · 将应用至全部镜头</p></section><button class="generate-btn" :disabled="loading" @click="generate"><WandSparkles :size="16" />生成分镜脚本<ArrowRight :size="15" /></button><div class="sidebar-footer">AI 创作引擎已就绪 <span>v1.2.0</span></div>
      </aside>
      <main class="canvas"><div class="canvas-top"><div><div class="breadcrumb">项目 <span>/</span> {{ project }}</div><div class="canvas-title"><h1>故事板</h1><span class="shot-count">{{ shots.length }} SHOTS</span></div></div><div class="collab-pill"><span></span>人机协同 · 等待你的灵感</div></div>
        <div class="board-toolbar"><div class="toolbar-label"><Film :size="14" /><span>镜头序列</span><span class="toolbar-divider"></span><span class="subtle">{{ modelHint }}</span></div><div class="view-switch"><button :class="{ selected: viewMode === 'grid' }" @click="viewMode = 'grid'"><Layers3 :size="13" />卡片</button><button :class="{ selected: viewMode === 'list' }" @click="viewMode = 'list'"><span>☷</span>列表</button></div></div>
        <div v-if="loading" class="skeleton-list"><div v-for="i in 3" :key="i" class="skeleton-card"><div class="skeleton-line w-1/3"></div><div class="skeleton-image"></div><div class="skeleton-line w-3/4"></div></div></div>
        <div v-else :class="viewMode === 'grid' ? 'shot-list grid-cols-1 md:grid-cols-2' : 'shot-list list-mode flex-col'"><article v-for="(shot, index) in shots" :key="shot.id" class="shot-card"><div class="shot-top"><div class="shot-index"><span class="index-num">{{ String(index + 1).padStart(2, '0') }}</span><div><b>SHOT {{ String(index + 1).padStart(2, '0') }}</b><small>{{ shot.duration }} · {{ shot.scale }} · {{ shot.lens }}</small></div></div><span class="move-badge"><Focus :size="11" />{{ shot.move }}</span></div><div class="scene-art" :class="shot.palette"><div class="scene-glow"></div><div class="scene-figure"><i></i><span></span></div><div class="scene-caption">SCENE {{ String(index + 1).padStart(2, '0') }}</div></div><div class="shot-copy"><input v-model="shot.title" :aria-label="`镜头 ${index + 1} 标题`" /><textarea v-model="shot.description" rows="2" aria-label="画面描述"></textarea></div><div class="prompt-block"><div class="prompt-head"><span><Sparkles :size="12" /> AI PROMPT · {{ model }}</span><button class="copy-btn" @click="copyPrompt(shot)"><Copy :size="12" />一键复制</button></div><div class="prompt-text">{{ activePrompt(shot) }}</div><div class="prompt-foot"><span><b>{{ anchors.join(' · ') }}</b> 已应用角色锚点</span><span>{{ activePrompt(shot).length }} 字符</span></div></div><div class="tweak-row"><MessageSquareText :size="14" /><input v-model="shot.edit" placeholder="输入单镜微调要求，例如：改为赛博朋克霓虹灯" @keydown.enter="refineShot(shot)" /><button :disabled="!shot.edit.trim()" aria-label="发送镜头微调" @click="refineShot(shot)"><Send :size="14" /></button></div></article><button class="add-shot" @click="addShot"><Plus :size="15" />添加镜头</button></div><footer class="canvas-footer"><span>{{ saveLabel }}</span><span>所有更改均已同步 <Check :size="12" /></span></footer>
      </main>
      <aside class="right-panel"><div class="right-heading"><div><p class="eyebrow">CREATIVE ASSETS</p><h2>资产与灵感</h2></div><button class="icon-button"><MoreHorizontal :size="17" /></button></div><section class="asset-section"><div class="section-title"><div><span class="section-icon amber"><Aperture :size="14" /></span><b>角色资产库</b></div><button class="text-action" @click="openEditor(null)">新建 <ArrowRight :size="12" /></button></div><CharacterCard v-for="(character, index) in visibleCharacters" :key="character.id" :character="character" :index="index" @edit="openEditor(character)" @remove="removeCharacter(character)" @remove-tag="detachTag" @add-tag="openEditor(character)" /><p v-if="!visibleCharacters.length" class="asset-empty">{{ selectedTagId === null ? '还没有角色，点右上角「新建」' : '该标签下还没有角色' }}</p></section><TagPanel :tags="assetTags" :selected="selectedTagId" @select="toggleTagFilter" @rename="renameTag" @remove="removeTag" @create="createTagFromPanel" /><div class="insight-card"><AudioLines :size="15" /><div><span>DIRECTOR'S NOTE</span><p>镜头与音乐鼓点的情绪峰值重合，试试缩短时长，让转场更有力量。</p><button @click="notify('已应用导演建议')">应用建议 <ArrowRight :size="12" /></button></div></div></aside>
    </div><CharacterEditor v-if="editorOpen" :character="editingCharacter" :tags="assetTags" :saving="savingCharacter" :error="editorError" :create-tag="createTagFromEditor" @close="closeEditor" @save="saveCharacter" /><LoginDialog v-if="!user && !bootstrapping" /><Transition><div v-if="toast" class="toast"><span><Check :size="14" /></span>{{ toast }}</div></Transition>
  </div>
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap');
@tailwind base; @tailwind components; @tailwind utilities;
.app-shell{font-family:'DM Sans','Noto Sans SC',sans-serif;background:radial-gradient(ellipse at 46% -35%,#1e293b5c,transparent 60%),#020617;color:#e2e8f0}.topbar{position:sticky;top:0;z-index:5;background:#050a16ed;backdrop-filter:blur(16px)}.brand{color:#f8fafc;text-decoration:none;font-weight:700}.brand i{color:#fbbf24;font-style:normal}.brand-icon,.anchor-symbol,.section-icon{display:grid;place-items:center}.brand-icon{width:31px;height:31px;border-radius:9px;background:#f59e0b;color:#111827}.project-name input,.shot-copy input{background:transparent;border:0;outline:0;color:#cbd5e1}.project-name input{width:180px}.workspace{display:grid;grid-template-columns:260px minmax(500px,1fr) 270px;max-width:1780px;min-height:calc(100vh - 66px);margin:auto}.left-panel,.right-panel{padding:24px 19px;background:#050b16}.left-panel{border-right:1px solid #151f31;display:flex;flex-direction:column}.right-panel{border-left:1px solid #151f31}.panel-heading,.right-heading,.section-title,.anchor-head,.shot-top,.shot-index,.prompt-head,.prompt-foot,.canvas-top,.board-toolbar,.canvas-footer{display:flex;align-items:center;justify-content:space-between}.eyebrow,.anchor-head small{font:9px 'DM Mono';letter-spacing:1px;color:#64748b}.panel-heading h2,.right-heading h2{font-size:14px;margin:0}.icon-button{width:30px;height:30px;display:grid;place-items:center;background:#0a1120;border:1px solid #1e293b;border-radius:7px;color:#8290a4}.mode-switch,.view-switch{display:flex;padding:3px;margin:20px 0;background:#0a1120;border:1px solid #1e293b;border-radius:7px}.mode-switch button,.view-switch button{flex:1;display:flex;justify-content:center;align-items:center;gap:6px;padding:8px 4px;border:0;border-radius:5px;background:transparent;color:#8190a5;font-size:10px}.mode-switch button.active,.view-switch button.selected{background:#1a2434;color:#fbbf24}.field-label{display:flex;justify-content:space-between;margin:10px 0;font-size:11px}.muted,.subtle{color:#64748b;font-size:9px}.idea-input,.upload-box,.anchor-card,.shot-card,.character-card,.prompt-block{background:#0a1120;border:1px solid #1e293b;border-radius:8px}.idea-input{width:100%;padding:11px;color:#cbd5e1;font-size:11px;line-height:1.8;resize:vertical}.style-heading{margin-top:20px}.style-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.style-grid button,.anchor-tag{background:#101827;border:1px solid #263246;border-radius:5px;padding:8px;color:#94a3b8;font-size:10px}.style-grid button.chosen{color:#fbbf24;border-color:#805a1e;background:#21190f}.anchor-card{margin-top:22px;padding:13px}.anchor-symbol,.section-icon{width:28px;height:28px;border:1px solid #76562170;border-radius:7px;color:#fbbf24}.anchor-head>div{margin-right:auto;margin-left:9px;display:grid;gap:3px}.anchor-head b,.section-title b{font-size:10px}.mini-add{background:none;border:0;color:#fbbf24}.anchor-name{font-size:11px}.anchor-tags,.character-tags,.cloud{display:flex;flex-wrap:wrap;gap:5px}.anchor-tag{display:flex;align-items:center;gap:4px;padding:5px;color:#e9b64f;font:8px 'DM Mono'}.anchor-note,.sidebar-footer,.canvas-footer{color:#718096;font-size:9px}.generate-btn,.export-btn{display:flex;align-items:center;justify-content:center;gap:8px;background:#f59e0b;color:#111827;border:0;border-radius:7px;font-weight:700;font-size:11px;padding:10px}.generate-btn{margin-top:16px}.generate-btn:disabled{opacity:.65}.sidebar-footer{margin-top:auto;padding-top:22px}.sidebar-footer span{float:right}.canvas{padding:25px 30px}.breadcrumb{color:#64748b;font-size:10px}.canvas-title{display:flex;align-items:center;gap:11px}.canvas-title h1{font-size:24px}.shot-count,.tag-chip,.move-badge{padding:5px 7px;border:1px solid #29354a;border-radius:5px;color:#b9c5d4;font-size:9px}.collab-pill{padding:8px 11px;border:1px solid #1e3a34;border-radius:20px;background:#0b171b;color:#9eb3ad;font-size:9px}.collab-pill span{display:inline-block;width:6px;height:6px;border-radius:50%;background:#34d399;margin-right:6px}.board-toolbar{border-block:1px solid #172133;margin-bottom:14px;padding:6px 0}.toolbar-label,.prompt-head>span{display:flex;align-items:center;gap:7px;color:#aab5c3;font-size:10px}.toolbar-label svg{color:#fbbf24}.view-switch{margin:0}.view-switch button{padding:5px}.shot-list{display:grid;gap:13px}.shot-card{min-width:0;padding:12px}.shot-index{justify-content:flex-start;gap:8px}.index-num{color:#e6b14c;font:15px 'DM Mono'}.shot-index b{font:9px 'DM Mono';color:#b6c1ce}.shot-index small{display:block;color:#718096;font-size:9px;margin-top:3px}.move-badge{display:flex;align-items:center;gap:4px}.scene-art{height:110px;margin-top:10px;position:relative;overflow:hidden;border-radius:6px;background:linear-gradient(110deg,#24130e,#382015 44%,#111827)}.scene-art.from-indigo-950{background:linear-gradient(110deg,#080c1c,#242039 48%,#673e21)}.scene-art.from-red-950{background:linear-gradient(110deg,#320b12,#541c13 48%,#171326)}.scene-glow{position:absolute;inset:10% 35%;border-radius:50%;background:#e9943080;filter:blur(30px)}.scene-figure{position:absolute;left:50%;bottom:12px;width:30px;height:55px;transform:translateX(-50%);background:linear-gradient(90deg,#151217,#594126,#15131a);clip-path:polygon(35% 0,65% 0,100% 100%,0 100%)}.scene-figure i{position:absolute;top:3px;left:8px;width:14px;height:3px;background:#e9b84c}.scene-figure span{position:absolute;left:-10px;top:20px;width:50px;height:2px;background:#d8ad61;transform:rotate(-20deg)}.scene-caption{position:absolute;bottom:7px;left:9px;font:8px 'DM Mono';color:#cbd5e1}.shot-copy{padding:8px 2px}.shot-copy input{width:100%;font-size:12px;font-weight:600}.shot-copy textarea{width:100%;margin-top:6px;background:none;border:0;outline:0;resize:vertical;color:#94a3b8;font-size:10px;line-height:1.6}.prompt-block{background:#080e18;overflow:hidden}.prompt-head{padding:7px 9px;border-bottom:1px solid #1e293b}.prompt-head>span svg{color:#fbbf24}.copy-btn{display:flex;gap:5px;align-items:center;padding:6px 8px;border:1px solid #805a1e;border-radius:5px;background:#51370f;color:#ffdb89;font-size:9px}.prompt-text{padding:9px;color:#a8b4c4;font-size:9px;line-height:1.7}.prompt-foot{padding:0 9px 8px;color:#66758a;font-size:8px}.prompt-foot b{color:#e7ad42}.tweak-row{height:34px;margin-top:8px;padding:0 8px;display:flex;align-items:center;gap:7px;border:1px solid #1e293b;border-radius:6px;background:#0a111e;color:#718096}.tweak-row input{flex:1;min-width:0;border:0;outline:0;background:none;color:#cbd5e1;font-size:9px}.tweak-row button{border:0;background:transparent;color:#fbbf24}.tweak-row button:disabled{opacity:.35}.list-mode .shot-card{display:grid;grid-template-columns:120px minmax(0,1fr);gap:0 12px}.list-mode .shot-top{grid-column:1/-1}.list-mode .scene-art{grid-row:2/5;height:100%;min-height:130px;margin:0}.list-mode .shot-copy,.list-mode .prompt-block,.list-mode .tweak-row{grid-column:2}.add-shot{min-height:40px;background:none;border:1px dashed #334155;border-radius:7px;color:#e6b14c}.canvas-footer{padding-top:14px}.section-title{margin-bottom:12px}.section-title>div{display:flex;align-items:center;gap:8px}.section-icon.amber{background:#f59e0b16}.section-icon.violet{color:#b49afa;background:#8b5cf616}.character-art{height:105px;position:relative;background:radial-gradient(ellipse at 50% 43%,#90632a55,transparent 43%),linear-gradient(135deg,#211a18,#131625)}.portrait-halo{position:absolute;left:50%;top:12px;width:70px;height:70px;transform:translateX(-50%);border:1px solid #dfa94755;border-radius:50%}.portrait-body{position:absolute;left:50%;bottom:0;width:60px;height:70px;transform:translateX(-50%);background:linear-gradient(110deg,#130f11,#503a24,#15151b);clip-path:polygon(38% 0,62% 0,100% 100%,0 100%)}.portrait-circlet{position:absolute;top:33px;left:calc(50% - 12px);width:24px;height:4px;background:#e7b446}.character-info,.character-tags{padding:9px}.character-info b{font-size:11px}.character-type,.character-info p{display:block;color:#718096;font-size:9px;margin:5px 0}.character-info strong{color:#6ed3ab}.character-tags span,.tag-chip{font-size:8px;color:#b2bdcc;background:#121a27;border:1px solid #263246;border-radius:4px;padding:4px}.tag-section{padding-top:18px}.tag-group{margin:12px 0}.tag-category{display:flex;justify-content:space-between;color:#9aa6b6;font-size:9px}.tag-line{flex:1;border-top:1px solid #1b2637;margin:auto 8px}.t-amber{color:#e9b64f!important}.t-violet{color:#bd9af2!important}.t-rose{color:#f48b9b!important}.t-indigo{color:#8ab6ed!important}.insight-card{display:flex;gap:9px;padding:11px;margin-top:15px;border:1px solid #57411c75;border-radius:7px;color:#f8bb4f}.insight-card p{color:#9aa6b6;font-size:9px;line-height:1.6}.insight-card button{border:0;background:none;color:#e5b34f;font-size:9px}.upload-box{height:150px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:9px;border-style:dashed;color:#e7b34c;cursor:pointer}.upload-box b{color:#cbd5e1;font-size:10px}.upload-box span,.upload-box strong{font-size:9px;color:#94a3b8}.hidden-file{display:none}.toast{position:fixed;z-index:10;right:24px;top:80px;padding:12px 16px;border:1px solid #235443;border-radius:8px;background:#0c1a19;color:#b8e9d5;font-size:11px}.skeleton-list{display:flex;flex-direction:column;gap:12px}.skeleton-card{height:250px;padding:15px;border:1px solid #1e293b;border-radius:8px;background:#0a1120}.skeleton-line,.skeleton-image{height:10px;margin:10px 0;border-radius:8px;background:linear-gradient(90deg,#131c2a,#263448,#131c2a);background-size:200% 100%;animation:shimmer 1.3s infinite}.skeleton-image{height:140px}@keyframes shimmer{to{background-position:-200% 0}}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1150px){.workspace{grid-template-columns:230px minmax(0,1fr)}.right-panel{display:none}}@media(max-width:720px){.topbar{padding:0 12px}.project-name input{width:90px}.workspace{display:block}.left-panel,.right-panel{display:none}.canvas{padding:18px 12px}.shot-list.grid-cols-1.md\\:grid-cols-2{grid-template-columns:1fr}.list-mode .shot-card{grid-template-columns:90px minmax(0,1fr)}.collab-pill{font-size:0}}
/* ---- 登录 / 用户菜单 / 项目切换 ---- */
.login-gate{position:fixed;inset:0;z-index:60;display:grid;place-items:center;padding:24px;background:#020617cc;backdrop-filter:blur(6px)}
.login-card{width:100%;max-width:360px;padding:26px 24px 20px;border:1px solid #1e293b;border-radius:14px;background:#070d1a;box-shadow:0 24px 80px #00000080;display:flex;flex-direction:column;gap:14px}
.login-brand{display:flex;align-items:center;gap:11px}
.login-brand b{display:block;font-size:14px;color:#f8fafc}
.login-brand small{display:block;margin-top:3px;font:10px 'DM Mono';color:#64748b;letter-spacing:.5px}
.login-field{display:flex;flex-direction:column;gap:6px;font-size:11px;color:#94a3b8}
.login-field input{height:38px;padding:0 12px;border:1px solid #1e293b;border-radius:8px;background:#0a1120;color:#e2e8f0;font-size:12px;outline:none}
.login-field input:focus{border-color:#f59e0b88;box-shadow:0 0 0 3px #f59e0b1f}
.login-remember{display:flex;align-items:center;gap:8px;font-size:11px;color:#94a3b8}
.login-remember input{accent-color:#f59e0b}
.login-error{margin:0;padding:8px 10px;border:1px solid #f43f5e4d;border-radius:8px;background:#f43f5e14;color:#fda4af;font-size:11px;line-height:1.5}
.login-submit{height:40px;border:0;border-radius:8px;background:#f59e0b;color:#111827;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;gap:7px}
.login-submit:hover{background:#fbbf24}
.login-submit:disabled{opacity:.6;cursor:not-allowed}
.login-ghost{height:40px;flex:1;border:1px solid #1e293b;border-radius:8px;background:transparent;color:#94a3b8;font-size:12px}
.login-actions{display:flex;gap:10px}
.login-hint{margin:0;font-size:10px;line-height:1.6;color:#64748b}
.user-menu{position:relative;display:flex;align-items:center}
.user-chip{height:34px;padding:0 10px 0 6px;display:flex;align-items:center;gap:8px;border:1px solid #1e293b;border-radius:999px;background:#0b1220;color:#cbd5e1}
.user-chip:hover{border-color:#f59e0b55}
.user-chip .avatar{display:grid;place-items:center}
.user-name{font-size:11px;max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.user-dropdown{position:absolute;top:calc(100% + 8px);right:0;min-width:190px;padding:6px;border:1px solid #1e293b;border-radius:10px;background:#070d1a;box-shadow:0 18px 50px #00000080;display:flex;flex-direction:column;gap:2px;z-index:40}
.user-email{margin:6px 8px 8px;font:10px 'DM Mono';color:#64748b;word-break:break-all}
.user-dropdown button{display:flex;align-items:center;gap:8px;padding:8px;border:0;border-radius:7px;background:transparent;color:#cbd5e1;font-size:11px;text-align:left}
.user-dropdown button:hover{background:#111b2e}
.user-dropdown button.danger{color:#fda4af}
.user-notice{position:absolute;top:calc(100% + 8px);right:0;margin:0;padding:6px 10px;border:1px solid #22c55e4d;border-radius:8px;background:#22c55e14;color:#86efac;font-size:10px;white-space:nowrap;z-index:41}
.user-gate{z-index:70}
.project-name{position:relative}
.project-toggle{width:22px;height:22px;display:grid;place-items:center;border:0;border-radius:6px;background:transparent;color:#64748b}
.project-toggle:hover{background:#111b2e;color:#cbd5e1}
.project-menu{position:absolute;top:calc(100% + 10px);left:0;min-width:230px;max-height:280px;overflow:auto;padding:6px;border:1px solid #1e293b;border-radius:10px;background:#070d1a;box-shadow:0 18px 50px #00000080;display:flex;flex-direction:column;gap:2px;z-index:40}
.project-menu button{padding:8px 9px;border:0;border-radius:7px;background:transparent;color:#cbd5e1;font-size:11px;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.project-menu button:hover{background:#111b2e}
.project-menu button.current{color:#fbbf24;background:#1a2434}
.project-menu .new-project{color:#fbbf24;border-top:1px solid #151f31;margin-top:4px;padding-top:9px}
/* ---- 角色资产库 / 标签联动 ---- */
.character-art.tone-amber{background:radial-gradient(ellipse at 50% 43%,#90632a55,transparent 43%),linear-gradient(135deg,#211a18,#131625 70%)}
.character-art.tone-violet{background:radial-gradient(ellipse at 50% 43%,#5b3f8c55,transparent 43%),linear-gradient(135deg,#1b1730,#131625 70%)}
.character-art.tone-rose{background:radial-gradient(ellipse at 50% 43%,#8c3f5555,transparent 43%),linear-gradient(135deg,#241519,#131625 70%)}
.character-art.tone-indigo{background:radial-gradient(ellipse at 50% 43%,#2f5c9a55,transparent 43%),linear-gradient(135deg,#131b2b,#131625 70%)}
.character-art.tone-neutral{background:radial-gradient(ellipse at 50% 43%,#44506655,transparent 43%),linear-gradient(135deg,#191c25,#131625 70%)}
.character-actions{position:absolute;top:8px;right:8px;display:flex;gap:4px;opacity:0;transition:opacity .15s}
.character-card:hover .character-actions{opacity:1}
.character-actions button{width:22px;height:22px;display:grid;place-items:center;border:1px solid #33415a;border-radius:6px;background:#0b1220cc;color:#cbd5e1}
.character-actions button:hover{border-color:#f59e0b88;color:#fbbf24}
.character-tags{flex-wrap:wrap;align-items:center}
.character-tags .tag-chip{display:inline-flex;align-items:center;gap:3px}
.chip-remove,.chip-actions button{border:0;background:transparent;color:inherit;opacity:.55;font-size:9px;line-height:1;padding:0}
.chip-remove:hover,.chip-actions button:hover{opacity:1}
.chip-add{border:1px dashed #33415a;border-radius:4px;background:transparent;color:#7b8798;font-size:9px;padding:3px 6px}
.chip-add:hover{border-color:#f59e0b88;color:#fbbf24}
.asset-empty{margin:10px 2px 0;color:#64748b;font-size:9px;line-height:1.6}
.tag-chip{position:relative;display:inline-flex;align-items:center;gap:3px;cursor:pointer}
.tag-chip.active{border-color:#f59e0b;color:#fbbf24;box-shadow:0 0 0 2px #f59e0b2e}
.chip-count{font-style:normal;opacity:.5;font-size:7px}
.chip-actions{display:none;gap:2px;margin-left:2px}
.tag-chip:hover .chip-actions{display:inline-flex}
.sheet-gate{position:fixed;inset:0;z-index:65;display:grid;place-items:center;padding:24px;background:#020617cc;backdrop-filter:blur(6px)}
.sheet-card{width:100%;max-width:520px;max-height:86vh;overflow:auto;padding:22px;border:1px solid #1e293b;border-radius:14px;background:#070d1a;box-shadow:0 24px 80px #000000a0;display:flex;flex-direction:column;gap:14px}
.sheet-head{display:flex;align-items:flex-start;justify-content:space-between}
.sheet-head h3{margin:2px 0 0;font-size:15px;color:#f8fafc}
.sheet-body{display:flex;flex-direction:column;gap:12px}
.sheet-field{display:flex;flex-direction:column;gap:6px;font-size:11px;color:#94a3b8}
.sheet-field input,.sheet-field textarea,.sheet-field select{padding:8px 10px;border:1px solid #1e293b;border-radius:8px;background:#0a1120;color:#e2e8f0;font-size:12px;outline:none;font-family:inherit}
.sheet-field input:focus,.sheet-field textarea:focus{border-color:#f59e0b88;box-shadow:0 0 0 3px #f59e0b1f}
.sheet-hint{color:#5b6779;font-size:9px}
.sheet-tag-group{display:flex;flex-direction:column;gap:5px;margin-top:4px}
.sheet-tag-group em{font-style:normal;color:#64748b;font-size:9px}
.sheet-tag-group .cloud{gap:4px}
.sheet-tag-group .tag-chip{opacity:.55}
.sheet-tag-group .tag-chip.active{opacity:1}
.sheet-newtag{display:flex;gap:6px;margin-top:6px}
.sheet-newtag input{flex:1}
.sheet-newtag select{width:90px}
.sheet-actions{display:flex;gap:10px;justify-content:flex-end}
.sheet-actions .login-submit{min-width:96px}
.tone-row{display:flex;gap:8px}
.tone-dot{width:22px;height:22px;border-radius:50%;border:2px solid transparent;cursor:pointer}
.tone-dot.tone-amber{background:linear-gradient(145deg,#fcd34d,#b45309)}
.tone-dot.tone-violet{background:linear-gradient(145deg,#c4a2f5,#6d28d9)}
.tone-dot.tone-rose{background:linear-gradient(145deg,#f9a8b4,#be123c)}
.tone-dot.tone-indigo{background:linear-gradient(145deg,#93c5fd,#1d4ed8)}
.tone-dot.tone-neutral{background:linear-gradient(145deg,#94a3b8,#475569)}
.tone-dot.active{border-color:#fbbf24;box-shadow:0 0 0 2px #f59e0b33}
</style>
