<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import LoginDialog from './components/LoginDialog.vue'
import UserMenu from './components/UserMenu.vue'
import AssetCenter from './components/AssetCenter.vue'
import CharacterEditor from './components/CharacterEditor.vue'
import ShotBoard from './components/ShotBoard.vue'
import StoryboardStrip from './components/StoryboardStrip.vue'
import PlanPanel from './components/PlanPanel.vue'
import RefineDialog from './components/RefineDialog.vue'
import ExportDialog from './components/ExportDialog.vue'
import CharacterPicker from './components/CharacterPicker.vue'
import { ApiError, api } from './api/client'
import { useAuth } from './composables/useAuth'
import { useHistory } from './composables/useHistory'
import { anchorTokens, mergeAnchors } from './lib/consistency'
import { downloadBlob, downloadText, safeFilename, toCsv, toMarkdown } from './lib/export'
import type { Shot, ShotPlan } from './lib/types'
import {
  useAssets,
  type Character,
  type TagCategory,
  type Tone,
} from './composables/useAssets'
import { ArrowDownToLine, ArrowRight, Check, ChevronDown, Clapperboard, Film, Layers3, LoaderCircle, LockKeyhole, Package, Plus, ScanLine, SlidersHorizontal, Sparkles, Upload, WandSparkles, X } from 'lucide-vue-next'

const models = ['即梦 Jimeng', '可灵 Kling', 'Runway Gen-3']
const model = ref(models[0])
const mode = ref<'forward' | 'reverse'>('forward')
const viewMode = ref<'grid' | 'list'>('grid')
const project = ref('黑神话：最后一盏灯')
/**
 * 剧情梗概：项目级字段，随 storyboard 一起保存。
 * 早前它只是个组件内变量，从来没进过文档，所以刷新就丢——
 * 现在老项目读出来是空串，靠 placeholder 提示，不会强行塞示例文案。
 */
const idea = ref('')
const ideaEmpty = computed(() => !idea.value.trim())
const ideaWarn = computed(() => {
  const length = idea.value.trim().length
  return length > 0 && (length < 20 || length > 500)
})
const style = ref('燃向踩点')
const styles = ['搞笑反转', '燃向踩点', '黑深残', '日常整活']
// 项目级角色：锚点从角色资产派生，不再让用户手打字符串（避免三处表述不一致）
const projectCharacterIds = ref<number[]>([])
// 项目补充词：画风、镜头语言这类不属于任何角色的词，仍然保留下手位
const extras = ref<string[]>([])
/** 由项目角色 + 补充词合成的锚点，生成/展开/微调都用它。 */
const projectAnchors = computed(() => {
  const tokens: string[] = []
  for (const character of assetCharacters.value) {
    if (projectCharacterIds.value.includes(character.id)) {
      tokens.push(...anchorTokens(character))
    }
  }
  const merged = [...tokens, ...extras.value].map((item) => item.trim()).filter(Boolean)
  return Array.from(new Set(merged))
})
/** 每个锚点在多少个镜头里真的出现了（只做统计与提示，不自动改写）。 */
const anchorStats = computed(() =>
  projectAnchors.value.map((text) => {
    const needle = text.toLowerCase()
    const hits = shots.value.filter((shot) =>
      `${shot.prompt}\n${shot.runwayPrompt}`.toLowerCase().includes(needle),
    ).length
    return { text, hits, total: shots.value.length }
  }),
)
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
  if (ideaEmpty.value) {
    notify('先写一句剧情梗概，再生成分镜')
    return
  }
  loading.value = true
  try {
    // B4 阶段一：先出镜头计划，用户确认后再逐镜展开提示词。
    const data = await api.post<{ plan: ShotPlan }>('/api/v1/storyboard/plan', {
      idea: idea.value,
      style: style.value,
      anchors: projectAnchors.value,
      model: model.value,
    })
    if (!data.plan?.shots?.length) throw new Error('模型没有返回镜头计划')
    plan.value = data.plan
    expandedShots.value = {}
    expandProgress.value = {}
    notify(`已生成 ${data.plan.shots.length} 镜的计划，确认后展开提示词`)
  } catch (error) {
    notify(`生成计划失败：${error instanceof Error ? error.message : '未知错误'}`)
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
    body.append('anchors', projectAnchors.value.join(','))
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
async function refineShot(payload: { shot: Shot; instruction: string }) {
  if (refiningId.value !== null || !isAuthenticated.value) return
  refiningId.value = payload.shot.id
  try {
    // B1：真正调用模型，返回候选后由用户确认，不直接覆盖。
    const data = await api.post<{ shot: Shot }>('/api/v1/storyboard/refine', {
      shot: payload.shot,
      instruction: payload.instruction,
      model: model.value,
      // F1：把该镜绑定的角色锚点并入本次微调请求
      anchors: mergeAnchors(projectAnchors.value, payload.shot, assetCharacters.value),
    })
    refineCandidate.value = {
      before: { ...payload.shot },
      after: data.shot,
      instruction: payload.instruction,
    }
  } catch (error) {
    notify(`微调失败：${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    refiningId.value = null
  }
}
function toggleProjectCharacter(id: number) {
  projectCharacterIds.value = projectCharacterIds.value.includes(id)
    ? projectCharacterIds.value.filter((item) => item !== id)
    : [...projectCharacterIds.value, id]
}

function addExtra() {
  const value = window.prompt('添加项目补充词（画风 / 镜头语言等）')
  const text = value?.trim()
  if (!text) return
  if (projectAnchors.value.includes(text)) {
    notify('这个锚点已经在列表里了')
    return
  }
  extras.value = [...extras.value, text]
}

function removeExtra(text: string) {
  extras.value = extras.value.filter((item) => item !== text)
}

function addShot() { const previous = shots.value[shots.value.length - 1]; shots.value.push({ ...previous, id: Date.now(), title: '新镜头：点击此处开始创作', description: '为这个镜头补充核心剧情与画面描述……', prompt: `${projectAnchors.value.join(', ')}, 新镜头画面描述，电影级光影，细腻质感。`, runwayPrompt: `Cinematic shot, ${projectAnchors.value.join(', ')}, describe the new scene, cinematic lighting.`, edit: '' }) }

function removeShot(shot: Shot) {
  const index = shots.value.findIndex((item) => item.id === shot.id)
  if (index === -1) return
  if (!window.confirm(`删除「${shot.title || '该镜头'}」？此操作不可恢复。`)) return
  const removed = shots.value[index]
  shots.value.splice(index, 1)
  // 缩略导航的高亮索引可能已越界，重置掉
  if (activeShotIndex.value !== null && activeShotIndex.value >= shots.value.length) {
    activeShotIndex.value = null
  }
  // 清理可能残留的"删除中"微调状态
  if (refineCandidate.value?.after.id === shot.id) refineCandidate.value = null
  if (refiningId.value === shot.id) refiningId.value = null
  notify(`已删除「${removed?.title || '该镜头'}」`)
}

// ---- A1：重排 ----

function moveShot({ from, to }: { from: number; to: number }) {
  if (to < 0 || to >= shots.value.length || from === to) return
  const next = [...shots.value]
  const [moved] = next.splice(from, 1)
  if (!moved) return
  next.splice(to, 0, moved)
  shots.value = next
  activeShotIndex.value = to
}

// ---- F1 / F2：角色绑定与一致性 ----

const bindingShot = ref<Shot | null>(null)

function openBinding(shot: Shot) {
  bindingShot.value = shot
}

function applyBinding(ids: number[]) {
  if (!bindingShot.value) return
  bindingShot.value.character_ids = ids
  bindingShot.value = null
  notify(ids.length ? `已绑定 ${ids.length} 个角色` : '已解除全部角色绑定')
}

/** 把缺失的锚点补到提示词开头（项目锚点 + 该镜绑定角色的锚点）。 */
function injectMissing(shot: Shot) {
  const tokens = mergeAnchors(projectAnchors.value, shot, assetCharacters.value)
  if (!tokens.length) {
    notify('还没有可注入的锚点：先在左侧选择角色')
    return
  }
  const haystack = `${shot.prompt}\n${shot.runwayPrompt}`.toLowerCase()
  const missing = tokens.filter((token) => !haystack.includes(token.toLowerCase()))
  if (!missing.length) {
    notify('提示词里已经包含这些锚点')
    return
  }
  const prefix = missing.join(', ')
  shot.prompt = `${prefix}, ${shot.prompt}`.trim()
  shot.runwayPrompt = `${prefix}, ${shot.runwayPrompt}`.trim()
  notify(`已补齐 ${missing.length} 个锚点`)
}

// ---- A2：撤销 / 重做 ----

const history = useHistory(
  () => shots.value,
  (next) => {
    shots.value = next
  },
)

// ---- A3：快捷键 ----

function isTypingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null
  if (!element || !element.tagName) return false
  return (
    ['INPUT', 'TEXTAREA', 'SELECT'].includes(element.tagName) || element.isContentEditable === true
  )
}

function onKeydown(event: KeyboardEvent) {
  if (event.isComposing) return
  // 任何弹层打开时都不触发故事板快捷键，否则 Delete 会误删弹层背后的镜头
  if (
    assetCenterOpen.value ||
    editorOpen.value ||
    exportOpen.value ||
    bindingShot.value !== null ||
    refineCandidate.value !== null
  ) {
    return
  }
  const meta = event.ctrlKey || event.metaKey
  const key = event.key.toLowerCase()

  if (meta && key === 's') {
    event.preventDefault()
    void manualSave()
    return
  }
  if (meta && key === 'z') {
    event.preventDefault()
    if (event.shiftKey) history.redo()
    else history.undo()
    return
  }
  if (meta && key === 'y') {
    event.preventDefault()
    history.redo()
    return
  }
  if (meta && event.key === 'Enter') {
    event.preventDefault()
    if (!loading.value && !plan.value) void generate()
    return
  }

  // 在输入框里打字时不要吃掉方向键/删除键
  if (isTypingTarget(event.target)) return

  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    if (!shots.value.length) return
    event.preventDefault()
    const current = activeShotIndex.value ?? 0
    const next =
      event.key === 'ArrowDown'
        ? Math.min(shots.value.length - 1, current + 1)
        : Math.max(0, current - 1)
    scrollToShot(next)
    return
  }

  if (event.key === 'Delete' || event.key === 'Backspace') {
    const index = activeShotIndex.value
    const shot = index === null ? undefined : shots.value[index]
    if (!shot) return
    event.preventDefault()
    removeShot(shot)
  }
}

// --------------------------------------------------------------------------- //
// 故事板：镜头计划（B4）、单镜微调（B1）、参考首帧（C1）、导出（E1/E3）
// --------------------------------------------------------------------------- //

const plan = ref<ShotPlan | null>(null)
/** 本次计划已展开的镜头，按 plan index 存放；避免和已有 shots 的 id 混淆。 */
const expandedShots = ref<Record<number, Shot>>({})
const expandProgress = ref<Record<number, 'pending' | 'done' | 'error'>>({})
const expanding = ref(false)
const refiningId = ref<number | null>(null)
const refineCandidate = ref<{ before: Shot; after: Shot; instruction: string } | null>(null)
const exportOpen = ref(false)
const exporting = ref(false)
const activeShotIndex = ref<number | null>(null)
const uploadTarget = ref<Shot | null>(null)
const referenceInput = ref<HTMLInputElement | null>(null)

function updatePlan(next: ShotPlan) {
  plan.value = next
}

function cancelPlan() {
  if (expanding.value) return
  plan.value = null
  expandedShots.value = {}
  expandProgress.value = {}
}

function refreshFromExpansion(current: ShotPlan) {
  const ordered = current.shots
    .map((item) => expandedShots.value[item.index])
    .filter((shot): shot is Shot => Boolean(shot))
  if (ordered.length) shots.value = ordered
}

/** B4 阶段二：逐镜并发展开；已完成的镜头不会重复请求，失败可单独重试。 */
async function confirmPlan() {
  const current = plan.value
  if (!current || expanding.value || !isAuthenticated.value) return
  expanding.value = true
  try {
    const pending = current.shots.filter((item) => !expandedShots.value[item.index])
    if (!pending.length) {
      plan.value = null
      return
    }

    expandProgress.value = {
      ...expandProgress.value,
      ...Object.fromEntries(pending.map((item) => [item.index, 'pending' as const])),
    }

    const queue = [...pending]
    const worker = async () => {
      while (queue.length) {
        const item = queue.shift()
        if (!item) return
        try {
          const data = await api.post<{ shot: Shot }>('/api/v1/storyboard/shot', {
            idea: idea.value,
            style: style.value,
            anchors: projectAnchors.value,
            model: model.value,
            plan: current,
            index: item.index,
          })
          expandedShots.value = { ...expandedShots.value, [item.index]: data.shot }
          expandProgress.value = { ...expandProgress.value, [item.index]: 'done' }
          refreshFromExpansion(current)
        } catch {
          expandProgress.value = { ...expandProgress.value, [item.index]: 'error' }
        }
      }
    }

    // 并发 3 路：够快，也不会把模型服务打满
    await Promise.all(Array.from({ length: Math.min(3, pending.length) }, worker))

    const failed = current.shots.filter((item) => !expandedShots.value[item.index])
    if (failed.length) {
      notify(`${failed.length} 镜展开失败，可再点一次「确认并展开」只重试失败的镜头`)
    } else {
      refreshFromExpansion(current)
      plan.value = null
      expandedShots.value = {}
      expandProgress.value = {}
      notify(`已展开 ${current.shots.length} 个镜头`)
    }
  } finally {
    expanding.value = false
  }
}

function applyRefine() {
  const candidate = refineCandidate.value
  if (!candidate) return
  const target = shots.value.find((shot) => shot.id === candidate.after.id)
  if (target) {
    target.title = candidate.after.title
    target.description = candidate.after.description
    target.prompt = candidate.after.prompt
    target.runwayPrompt = candidate.after.runwayPrompt
    target.duration = candidate.after.duration
    target.scale = candidate.after.scale
    target.lens = candidate.after.lens
    target.move = candidate.after.move
    target.palette = candidate.after.palette
    target.scene = candidate.after.scene
    target.edit = ''
  }
  refineCandidate.value = null
  notify('已采用这次修改')
}

function cancelRefine() {
  refineCandidate.value = null
}

// ---- C1：参考首帧 ----

function requestUpload(shot: Shot) {
  uploadTarget.value = shot
  referenceInput.value?.click()
}

/** 大图先在本地压到 1280px，省流量也避免撞上后端 5MB 限制。 */
async function compressImage(file: File, maxEdge = 1280): Promise<File> {
  if (file.size <= 400 * 1024) return file
  try {
    const bitmap = await createImageBitmap(file)
    const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(bitmap.width * scale))
    canvas.height = Math.max(1, Math.round(bitmap.height * scale))
    const context = canvas.getContext('2d')
    if (!context) return file
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', 0.85),
    )
    if (!blob) return file
    return new File([blob], `${file.name.replace(/\.[^.]+$/, '')}.jpg`, { type: 'image/jpeg' })
  } catch {
    return file
  }
}

async function onReferenceSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  const target = uploadTarget.value
  input.value = ''
  uploadTarget.value = null
  if (!file || !target) return
  try {
    const prepared = await compressImage(file)
    const form = new FormData()
    form.append('file', prepared, prepared.name)
    const data = await api.upload<{ id: number }>('/api/v1/uploads', form)
    target.reference_image_id = data.id
    notify('已设置参考首帧')
  } catch (error) {
    notify(`首帧上传失败：${error instanceof Error ? error.message : '未知错误'}`)
  }
}

function removeReference(shot: Shot) {
  shot.reference_image_id = null
  notify('已移除参考首帧')
}

// ---- E1 / E3：导出 ----

function openExport() {
  if (!shots.value.length) {
    notify('还没有镜头可以导出')
    return
  }
  exportOpen.value = true
}

async function runExport(format: 'md' | 'csv' | 'jianying') {
  exporting.value = true
  try {
    const base = safeFilename(project.value)
    if (format === 'md') {
      downloadText(
        `${base}.md`,
        toMarkdown(project.value, shots.value, model.value),
        'text/markdown;charset=utf-8',
      )
    } else if (format === 'csv') {
      downloadText(`${base}.csv`, toCsv(shots.value), 'text/csv;charset=utf-8')
    } else {
      if (projectId.value === null) throw new Error('项目尚未保存，请稍后再试')
      const response = await fetch(`/api/v1/projects/${projectId.value}/export/jianying`, {
        credentials: 'include',
      })
      if (!response.ok) {
        const detail = (await response.json().catch(() => ({}))) as { detail?: string }
        throw new Error(detail.detail ?? `HTTP ${response.status}`)
      }
      downloadBlob(`${base}-jianying-draft.zip`, await response.blob())
    }
    exportOpen.value = false
    notify('导出已开始')
  } catch (error) {
    notify(`导出失败：${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    exporting.value = false
  }
}

// ---- C3：缩略导航 ----

function scrollToShot(index: number) {
  activeShotIndex.value = index
  document
    .getElementById(`shot-card-${index}`)
    ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

/** 滚动时高亮离视口顶部最近的卡片（缩略条跟随）。 */
function onViewportScroll() {
  if (!shots.value.length) return
  let bestIndex: number | null = null
  let bestDistance = Number.POSITIVE_INFINITY
  document.querySelectorAll<HTMLElement>('[data-shot-index]').forEach((element) => {
    const distance = Math.abs(element.getBoundingClientRect().top - 140)
    if (distance < bestDistance) {
      bestDistance = distance
      bestIndex = Number(element.dataset.shotIndex)
    }
  })
  if (bestIndex !== null) activeShotIndex.value = bestIndex
}

// --------------------------------------------------------------------------- //
// 认证 + 项目持久化
// --------------------------------------------------------------------------- //

const { user, isAuthenticated, bootstrapping, bootstrap } = useAuth()

type ProjectSummary = { id: number; name: string; updated_at: string }
type StoryboardDoc = {
  shots: Shot[]
  style: string
  model: string
  /** 剧情梗概（项目级） */
  idea: string
  /** 项目级角色（锚点由角色资产派生） */
  character_ids: number[]
  /** 项目补充词（画风 / 镜头语言） */
  extras: string[]
  plan?: ShotPlan | null
  /** 旧版本字段：只在读取历史项目时兼容，不再写入 */
  anchors?: string[]
}

const projectId = ref<number | null>(null)
/** 当前项目的乐观锁版本号；保存时带回去，防止两个标签页互相覆盖。 */
const projectVersion = ref<number>(1)
const projectList = ref<ProjectSummary[]>([])
const projectMenuOpen = ref(false)
const saveState = ref<'idle' | 'saving' | 'saved' | 'error' | 'conflict'>('idle')
const saveMessage = ref('')
// 载入项目期间不要触发自动保存，否则会用旧数据覆盖刚打开的项目。
let hydrating = false
let saveTimer: number | undefined

function storyboardDoc(): StoryboardDoc {
  return {
    shots: shots.value,
    style: style.value,
    model: model.value,
    idea: idea.value,
    character_ids: projectCharacterIds.value,
    extras: extras.value,
    plan: plan.value,
  }
}

function applyStoryboard(doc: Partial<StoryboardDoc> | undefined) {
  if (!doc) return
  if (Array.isArray(doc.shots)) shots.value = doc.shots as Shot[]
  if (typeof doc.style === 'string') style.value = doc.style
  if (typeof doc.model === 'string') model.value = doc.model
  // 老项目没有 idea 字段：给空串，靠 placeholder 提示，不覆盖成示例文案
  idea.value = typeof doc.idea === 'string' ? doc.idea : ''

  projectCharacterIds.value = Array.isArray(doc.character_ids)
    ? (doc.character_ids as number[])
    : []
  if (Array.isArray(doc.extras)) {
    extras.value = doc.extras as string[]
  } else if (Array.isArray(doc.anchors)) {
    // 老项目没有 extras：把原来的自由锚点降级成"项目补充词"，
    // 提示词里的注入行为不变，用户再逐步改成按角色选择。
    extras.value = doc.anchors as string[]
  } else {
    extras.value = []
  }

  // 计划也随项目保存，刷新后可以继续展开未完成的镜头。
  plan.value = (doc.plan as ShotPlan | null | undefined) ?? null
  expandProgress.value = {}
  // 换项目后清空撤销栈，避免撤销到上一个项目的内容
  history.reset()
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
    const data = await api.get<{
      id: number
      name: string
      version: number
      storyboard: Partial<StoryboardDoc>
    }>(`/api/v1/projects/${id}`)
    projectId.value = data.id
    projectVersion.value = data.version ?? 1
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
  // 先把手头未保存的改动落盘，否则新建项目会把它们丢掉
  await flushSave()
  try {
    const data = await api.post<{ id: number }>('/api/v1/projects', {
      name: '未命名项目',
      storyboard: {
        shots: [],
        style: style.value,
        model: model.value,
        // 新建项目刻意留空，让用户自己写；示例文案只放在 placeholder 里
        idea: '',
        character_ids: projectCharacterIds.value,
        extras: extras.value,
      },
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
  // 防抖窗口内切换项目会把刚输入的内容覆盖掉，这里先 flush
  await flushSave()
  await openProject(id)
}

/** 立即把待保存的改动写库（绕过 1.2s 防抖）。 */
async function flushSave() {
  if (projectId.value === null || !isAuthenticated.value) return
  if (saveTimer === undefined) return
  window.clearTimeout(saveTimer)
  saveTimer = undefined
  await persistProject()
}

/** Ctrl/⌘+S：立即落盘（绕过防抖）。 */
async function manualSave() {
  if (projectId.value === null) {
    notify('项目还没保存过，稍后再试')
    return
  }
  if (saveState.value === 'conflict') {
    notify('有保存冲突，请先点「加载最新版本」')
    return
  }
  window.clearTimeout(saveTimer)
  saveTimer = undefined
  await persistProject()
  notify(saveState.value === 'saved' ? '已保存' : '保存失败，请检查网络')
}

/** 冲突后放弃本地改动，拉取服务器上的最新版本。 */
async function reloadProject() {
  if (projectId.value === null) return
  await openProject(projectId.value)
  if (saveState.value === 'saved') notify('已载入服务器上的最新版本')
}

/** 还有没写完的保存时，关页面前提醒一下。 */
function onBeforeUnload(event: BeforeUnloadEvent) {
  if (saveTimer === undefined) return
  event.preventDefault()
  event.returnValue = ''
}

function scheduleSave() {
  if (!isAuthenticated.value || hydrating || projectId.value === null) return
  if (saveState.value === 'conflict') return
  window.clearTimeout(saveTimer)
  saveState.value = 'saving'
  saveTimer = window.setTimeout(persistProject, 1200)
}

async function persistProject() {
  const id = projectId.value
  if (id === null || !isAuthenticated.value) return
  // 冲突未解决前不再自动写，否则每次编辑都会重复触发 409
  if (saveState.value === 'conflict') return
  window.clearTimeout(saveTimer)
  saveTimer = undefined
  try {
    const updated = await api.put<{ version: number }>(`/api/v1/projects/${id}`, {
      name: project.value.trim() || '未命名项目',
      storyboard: storyboardDoc(),
      expected_version: projectVersion.value,
    })
    projectVersion.value = updated.version ?? projectVersion.value + 1
    saveState.value = 'saved'
    saveMessage.value = '刚刚'
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      const current = error.data.current_version
      saveState.value = 'conflict'
      saveMessage.value =
        typeof current === 'number' ? `服务器已是 v${current}` : '已被其他窗口修改'
      notify('该项目已被其他窗口修改，自动保存已暂停')
      return
    }
    saveState.value = 'error'
    saveMessage.value = error instanceof Error ? error.message : '保存失败'
  }
}

const saveLabel = computed(() => {
  if (!isAuthenticated.value) return '未登录 · 改动不会保存'
  if (saveState.value === 'conflict') return `保存冲突：${saveMessage.value}`
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
    projectVersion.value = 1
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
} = useAssets()

const editorOpen = ref(false)
const editingCharacter = ref<Character | null>(null)
const savingCharacter = ref(false)
const editorError = ref('')
const assetCenterOpen = ref(false)

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
    // 顺手清理故事板里对该角色的悬空绑定，否则镜头卡会一直显示「角色已被删除」
    const cleaned = cleanupCharacterBindings(character.id)
    notify(
      cleaned
        ? `已删除角色「${character.name}」，并清理了 ${cleaned} 个镜头上的绑定`
        : `已删除角色「${character.name}」`,
    )
  } catch (error) {
    notify(`删除失败：${errorText(error, '未知错误')}`)
  }
}

/** 从所有镜头上摘掉某个角色的绑定，返回受影响的镜头数。 */
function cleanupCharacterBindings(characterId: number): number {
  let touched = 0
  for (const shot of shots.value) {
    const ids = shot.character_ids ?? []
    if (!ids.includes(characterId)) continue
    shot.character_ids = ids.filter((id) => id !== characterId)
    touched += 1
  }
  return touched
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

onMounted(async () => {
  window.addEventListener('scroll', onViewportScroll, { passive: true })
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('beforeunload', onBeforeUnload)
  await bootstrap()
  try {
    await syncProjects()
  } catch (error) {
    // 项目初始化失败不影响继续编辑（可能是离线或后端刚重启）。
    notify(error instanceof Error ? `项目初始化失败：${error.message}` : '项目初始化失败')
  }
  if (isAuthenticated.value) await ensureAssetsLoaded()
})

watch([project, style, model, idea, projectCharacterIds, extras, shots, plan], scheduleSave, { deep: true })

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
    // 资产中心持有的是上一位用户的数据，直接关掉避免看到残留
    assetCenterOpen.value = false
    resetAssets()
  }
})

onBeforeUnmount(() => {
  window.clearTimeout(saveTimer)
  window.removeEventListener('scroll', onViewportScroll)
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('beforeunload', onBeforeUnload)
})

</script>

<template>
  <div class="app-shell min-h-screen bg-slate-950 text-slate-100">
    <header class="topbar flex h-[66px] items-center justify-between border-b border-slate-800/80 px-7">
      <div class="flex min-w-0 items-center gap-7"><a class="brand flex items-center gap-2.5" href="#"><span class="brand-icon"><Clapperboard :size="19" /></span><span>ReCut <i>Agent</i></span></a><div class="h-6 w-px bg-slate-800"></div><div class="project-name flex items-center gap-2"><span>PROJECT</span><input v-model="project" aria-label="项目标题" :disabled="!isAuthenticated" /><button class="project-toggle" type="button" aria-label="切换项目" @click="projectMenuOpen = !projectMenuOpen"><ChevronDown :size="14" /></button><div v-if="projectMenuOpen" class="project-menu"><button v-for="item in projectList" :key="item.id" type="button" :class="{ current: item.id === projectId }" @click="switchProject(item.id)">{{ item.name }}</button><button class="new-project" type="button" @click="createProject">+ 新建项目</button></div></div></div>
      <div class="flex items-center gap-3"><span class="hidden text-[11px] text-slate-500 md:block">生成模型</span><div class="select-wrap"><select v-model="model" aria-label="选择生成模型"><option v-for="item in models" :key="item">{{ item }}</option></select><ChevronDown :size="14" /></div><button class="export-btn" @click="openExport"><ArrowDownToLine :size="15" />导出剪映草稿</button><button class="asset-btn" type="button" :aria-expanded="assetCenterOpen" @click="assetCenterOpen = true"><Package :size="15" />资产与灵感</button><UserMenu v-if="isAuthenticated" /></div>
    </header>
    <div class="workspace">
      <aside class="left-panel"><div class="panel-heading"><div><p class="eyebrow">WORKSPACE</p><h2>创作工作台</h2></div><button class="icon-button"><SlidersHorizontal :size="16" /></button></div>
        <div class="mode-switch"><button :class="{ active: mode === 'forward' }" @click="mode = 'forward'"><Sparkles :size="14" />正向生成</button><button :class="{ active: mode === 'reverse' }" @click="mode = 'reverse'"><ScanLine :size="14" />逆向拆解</button></div>
        <template v-if="mode === 'forward'"><div class="field-label"><span>剧情梗概</span><span class="muted" :class="{ 'idea-warn': ideaWarn }">{{ idea.length }} 字 · 建议 20-500</span></div><textarea v-model="idea" class="idea-input" rows="5" placeholder="写下这个故事：人物、场景、冲突、结局……例如：黄昏时分，天命人走进一座被遗忘的戏台，台上空无一人，锣鼓却自己响了起来。"></textarea><div class="field-label style-heading"><span>二创风格</span><span class="muted">选择一种叙事基调</span></div><div class="style-grid"><button v-for="item in styles" :key="item" :class="{ chosen: style === item }" @click="style = item">{{ item }}</button></div></template>
        <template v-else><div class="field-label"><span>参考素材</span><span class="muted">5–15 秒为佳</span></div><input ref="fileInput" class="hidden-file" type="file" accept="video/*,image/*" @change="onFileChange" /><div class="upload-box" role="button" tabindex="0" @click="fileInput?.click()" @keydown.enter="fileInput?.click()" @dragover.prevent @drop.prevent="onDrop"><Upload :size="21" /><b>拖拽视频或漫画切片至此</b><span>支持 MP4、MOV、PNG、JPG</span><template v-if="selectedFile"><strong>{{ selectedFile.name }}</strong><span>{{ formatSize(selectedFile.size) }}</span></template></div><button class="generate-btn mt-4" :disabled="loading" @click="reverse"><LoaderCircle v-if="loading" class="spin" :size="16" /><ScanLine v-else :size="16" />{{ loading ? '正在解析视听语言…' : '一键解析视听语言' }}<ArrowRight :size="15" /></button></template>
        <section class="anchor-card"><div class="anchor-head"><span class="anchor-symbol"><LockKeyhole :size="15" /></span><div><b>角色一致性锚点</b><small>CHARACTER ANCHORS</small></div><button class="mini-add" title="添加项目补充词" @click="addExtra"><Plus :size="15" /></button></div><p class="anchor-label">项目角色 <span class="muted">锚点由角色资产派生</span></p><div class="anchor-tags"><button v-for="character in assetCharacters" :key="character.id" class="anchor-char" :class="{ chosen: projectCharacterIds.includes(character.id) }" @click="toggleProjectCharacter(character.id)">{{ character.name }}</button><span v-if="!assetCharacters.length" class="anchor-note">右侧资产库还没有角色</span></div><template v-if="anchorStats.length"><p class="anchor-label">锚点命中</p><ul class="anchor-stats"><li v-for="stat in anchorStats" :key="stat.text" :class="{ miss: stat.hits < stat.total }"><span class="anchor-text">{{ stat.text }}</span><span class="anchor-hit">{{ stat.hits }}/{{ stat.total }}</span></li></ul></template><template v-if="extras.length"><p class="anchor-label">项目补充词</p><div class="anchor-tags"><button v-for="extra in extras" :key="extra" class="anchor-tag" @click="removeExtra(extra)">{{ extra }} <X :size="10" /></button></div></template><p class="anchor-note">生成 / 展开 / 微调都会注入；缺失只在卡片上提示，不自动改写</p></section><button class="generate-btn" :disabled="loading || ideaEmpty" :title="ideaEmpty ? '先写一句剧情梗概' : ''" @click="generate"><WandSparkles :size="16" />生成分镜脚本<ArrowRight :size="15" /></button><div class="sidebar-footer">AI 创作引擎已就绪 <span>v1.2.0</span></div>
      </aside>
      <main class="canvas"><div class="canvas-top"><div><div class="breadcrumb">项目 <span>/</span> {{ project }}</div><div class="canvas-title"><h1>故事板</h1><span class="shot-count">{{ shots.length }} SHOTS</span></div></div><div class="collab-pill"><span></span>人机协同 · 等待你的灵感</div></div>
        <div class="board-toolbar"><div class="toolbar-label"><Film :size="14" /><span>镜头序列</span><span class="toolbar-divider"></span><span class="subtle">{{ modelHint }}</span></div><div class="view-switch"><button :class="{ selected: viewMode === 'grid' }" @click="viewMode = 'grid'"><Layers3 :size="13" />卡片</button><button :class="{ selected: viewMode === 'list' }" @click="viewMode = 'list'"><span>☷</span>列表</button></div></div>
        <div v-if="loading" class="skeleton-list"><div v-for="i in 3" :key="i" class="skeleton-card"><div class="skeleton-line w-1/3"></div><div class="skeleton-image"></div><div class="skeleton-line w-3/4"></div></div></div>
        <template v-else>
  <PlanPanel v-if="plan" :plan="plan" :busy="expanding" :progress="expandProgress" @confirm="confirmPlan" @cancel="cancelPlan" @update="updatePlan" />
  <template v-else>
    <ShotBoard :shots="shots" :model="model" :anchors="projectAnchors" :view-mode="viewMode" :refining-id="refiningId" :characters="assetCharacters" @copy="copyPrompt" @refine="refineShot" @upload="requestUpload" @remove-reference="removeReference" @remove="removeShot" @bind="openBinding" @inject-missing="injectMissing" @move="moveShot" @add="addShot" />
    <StoryboardStrip :shots="shots" :active-index="activeShotIndex" @select="scrollToShot" />
  </template>
</template>
<footer class="canvas-footer"><span>{{ saveLabel }}</span><button v-if="saveState === 'conflict'" class="conflict-reload" type="button" @click="reloadProject">加载最新版本</button><span v-else>所有更改均已同步 <Check :size="12" /></span></footer>
      </main>
    </div><AssetCenter v-if="assetCenterOpen" @close="assetCenterOpen = false" @create="openEditor(null)" @edit="openEditor" @remove="removeCharacter" /><CharacterPicker v-if="bindingShot" :characters="assetCharacters" :selected="bindingShot.character_ids ?? []" :prompt="`${bindingShot.prompt}\n${bindingShot.runwayPrompt}`" @apply="applyBinding" @close="bindingShot = null" /><CharacterEditor v-if="editorOpen" :character="editingCharacter" :tags="assetTags" :saving="savingCharacter" :error="editorError" :create-tag="createTagFromEditor" @close="closeEditor" @save="saveCharacter" /><RefineDialog v-if="refineCandidate" :before="refineCandidate.before" :after="refineCandidate.after" :instruction="refineCandidate.instruction" @apply="applyRefine" @cancel="cancelRefine" /><ExportDialog v-if="exportOpen" :shots="shots" :project-name="project" :model="model" :busy="exporting" @close="exportOpen = false" @export="runExport" /><input ref="referenceInput" class="hidden-file" type="file" accept="image/png,image/jpeg,image/webp" @change="onReferenceSelected" /><LoginDialog v-if="!user && !bootstrapping" /><Transition><div v-if="toast" class="toast"><span><Check :size="14" /></span>{{ toast }}</div></Transition>
  </div>
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap');
@tailwind base; @tailwind components; @tailwind utilities;
.app-shell{font-family:'DM Sans','Noto Sans SC',sans-serif;background:radial-gradient(ellipse at 46% -35%,#1e293b5c,transparent 60%),#020617;color:#e2e8f0}.topbar{position:sticky;top:0;z-index:5;background:#050a16ed;backdrop-filter:blur(16px)}.brand{color:#f8fafc;text-decoration:none;font-weight:700}.brand i{color:#fbbf24;font-style:normal}.brand-icon,.anchor-symbol,.section-icon{display:grid;place-items:center}.brand-icon{width:31px;height:31px;border-radius:9px;background:#f59e0b;color:#111827}.project-name input,.shot-copy input{background:transparent;border:0;outline:0;color:#cbd5e1}.project-name input{width:180px}.workspace{display:grid;grid-template-columns:260px minmax(560px,1fr);max-width:1780px;min-height:calc(100vh - 66px);margin:auto}.left-panel,.right-panel{padding:24px 19px;background:#050b16}.left-panel{border-right:1px solid #151f31;display:flex;flex-direction:column}.right-panel{border-left:1px solid #151f31}.panel-heading,.right-heading,.section-title,.anchor-head,.shot-top,.shot-index,.prompt-head,.prompt-foot,.canvas-top,.board-toolbar,.canvas-footer{display:flex;align-items:center;justify-content:space-between}.eyebrow,.anchor-head small{font:9px 'DM Mono';letter-spacing:1px;color:#64748b}.panel-heading h2,.right-heading h2{font-size:14px;margin:0}.icon-button{width:30px;height:30px;display:grid;place-items:center;background:#0a1120;border:1px solid #1e293b;border-radius:7px;color:#8290a4}.mode-switch,.view-switch{display:flex;padding:3px;margin:20px 0;background:#0a1120;border:1px solid #1e293b;border-radius:7px}.mode-switch button,.view-switch button{flex:1;display:flex;justify-content:center;align-items:center;gap:6px;padding:8px 4px;border:0;border-radius:5px;background:transparent;color:#8190a5;font-size:10px}.mode-switch button.active,.view-switch button.selected{background:#1a2434;color:#fbbf24}.field-label{display:flex;justify-content:space-between;margin:10px 0;font-size:11px}.muted,.subtle{color:#64748b;font-size:9px}.idea-input,.upload-box,.anchor-card,.shot-card,.character-card,.prompt-block{background:#0a1120;border:1px solid #1e293b;border-radius:8px}.idea-input{width:100%;padding:11px;color:#cbd5e1;font-size:11px;line-height:1.8;resize:vertical}.style-heading{margin-top:20px}.style-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.style-grid button,.anchor-tag{background:#101827;border:1px solid #263246;border-radius:5px;padding:8px;color:#94a3b8;font-size:10px}.style-grid button.chosen{color:#fbbf24;border-color:#805a1e;background:#21190f}.anchor-card{margin-top:22px;padding:13px}.anchor-symbol,.section-icon{width:28px;height:28px;border:1px solid #76562170;border-radius:7px;color:#fbbf24}.anchor-head>div{margin-right:auto;margin-left:9px;display:grid;gap:3px}.anchor-head b,.section-title b{font-size:10px}.mini-add{background:none;border:0;color:#fbbf24}.anchor-name{font-size:11px}.anchor-tags,.character-tags,.cloud{display:flex;flex-wrap:wrap;gap:5px}.anchor-tag{display:flex;align-items:center;gap:4px;padding:5px;color:#e9b64f;font:8px 'DM Mono'}.anchor-note,.sidebar-footer,.canvas-footer{color:#718096;font-size:9px}.generate-btn,.export-btn{display:flex;align-items:center;justify-content:center;gap:8px;background:#f59e0b;color:#111827;border:0;border-radius:7px;font-weight:700;font-size:11px;padding:10px}.generate-btn{margin-top:16px}.generate-btn:disabled{opacity:.65}.sidebar-footer{margin-top:auto;padding-top:22px}.sidebar-footer span{float:right}.canvas{padding:25px 30px}.breadcrumb{color:#64748b;font-size:10px}.canvas-title{display:flex;align-items:center;gap:11px}.canvas-title h1{font-size:24px}.shot-count,.tag-chip,.move-badge{padding:5px 7px;border:1px solid #29354a;border-radius:5px;color:#b9c5d4;font-size:9px}.collab-pill{padding:8px 11px;border:1px solid #1e3a34;border-radius:20px;background:#0b171b;color:#9eb3ad;font-size:9px}.collab-pill span{display:inline-block;width:6px;height:6px;border-radius:50%;background:#34d399;margin-right:6px}.board-toolbar{border-block:1px solid #172133;margin-bottom:14px;padding:6px 0}.toolbar-label,.prompt-head>span{display:flex;align-items:center;gap:7px;color:#aab5c3;font-size:10px}.toolbar-label svg{color:#fbbf24}.view-switch{margin:0}.view-switch button{padding:5px}.shot-list{display:grid;gap:13px}.shot-card{min-width:0;padding:12px}.shot-index{justify-content:flex-start;gap:8px}.index-num{color:#e6b14c;font:15px 'DM Mono'}.shot-index b{font:9px 'DM Mono';color:#b6c1ce}.shot-index small{display:block;color:#718096;font-size:9px;margin-top:3px}.move-badge{display:flex;align-items:center;gap:4px}.scene-art{height:110px;margin-top:10px;position:relative;overflow:hidden;border-radius:6px;background:linear-gradient(110deg,#24130e,#382015 44%,#111827)}.scene-art.from-indigo-950{background:linear-gradient(110deg,#080c1c,#242039 48%,#673e21)}.scene-art.from-red-950{background:linear-gradient(110deg,#320b12,#541c13 48%,#171326)}.scene-glow{position:absolute;inset:10% 35%;border-radius:50%;background:#e9943080;filter:blur(30px)}.scene-figure{position:absolute;left:50%;bottom:12px;width:30px;height:55px;transform:translateX(-50%);background:linear-gradient(90deg,#151217,#594126,#15131a);clip-path:polygon(35% 0,65% 0,100% 100%,0 100%)}.scene-figure i{position:absolute;top:3px;left:8px;width:14px;height:3px;background:#e9b84c}.scene-figure span{position:absolute;left:-10px;top:20px;width:50px;height:2px;background:#d8ad61;transform:rotate(-20deg)}.scene-caption{position:absolute;bottom:7px;left:9px;font:8px 'DM Mono';color:#cbd5e1}.shot-copy{padding:8px 2px}.shot-copy input{width:100%;font-size:12px;font-weight:600}.shot-copy textarea{width:100%;margin-top:6px;background:none;border:0;outline:0;resize:vertical;color:#94a3b8;font-size:10px;line-height:1.6}.prompt-block{background:#080e18;overflow:hidden}.prompt-head{padding:7px 9px;border-bottom:1px solid #1e293b}.prompt-head>span svg{color:#fbbf24}.copy-btn{display:flex;gap:5px;align-items:center;padding:6px 8px;border:1px solid #805a1e;border-radius:5px;background:#51370f;color:#ffdb89;font-size:9px}.prompt-text{padding:9px;color:#a8b4c4;font-size:9px;line-height:1.7}.prompt-foot{padding:0 9px 8px;color:#66758a;font-size:8px}.prompt-foot b{color:#e7ad42}.tweak-row{height:34px;margin-top:8px;padding:0 8px;display:flex;align-items:center;gap:7px;border:1px solid #1e293b;border-radius:6px;background:#0a111e;color:#718096}.tweak-row input{flex:1;min-width:0;border:0;outline:0;background:none;color:#cbd5e1;font-size:9px}.tweak-row button{border:0;background:transparent;color:#fbbf24}.tweak-row button:disabled{opacity:.35}.list-mode .shot-card{display:grid;grid-template-columns:120px minmax(0,1fr);gap:0 12px}.list-mode .shot-top{grid-column:1/-1}.list-mode .scene-art{grid-row:2/5;height:100%;min-height:130px;margin:0}.list-mode .shot-copy,.list-mode .prompt-block,.list-mode .tweak-row{grid-column:2}.add-shot{min-height:40px;background:none;border:1px dashed #334155;border-radius:7px;color:#e6b14c}.canvas-footer{padding-top:14px}.section-title{margin-bottom:12px}.section-title>div{display:flex;align-items:center;gap:8px}.section-icon.amber{background:#f59e0b16}.section-icon.violet{color:#b49afa;background:#8b5cf616}.character-art{height:105px;position:relative;background:radial-gradient(ellipse at 50% 43%,#90632a55,transparent 43%),linear-gradient(135deg,#211a18,#131625)}.portrait-halo{position:absolute;left:50%;top:12px;width:70px;height:70px;transform:translateX(-50%);border:1px solid #dfa94755;border-radius:50%}.portrait-body{position:absolute;left:50%;bottom:0;width:60px;height:70px;transform:translateX(-50%);background:linear-gradient(110deg,#130f11,#503a24,#15151b);clip-path:polygon(38% 0,62% 0,100% 100%,0 100%)}.portrait-circlet{position:absolute;top:33px;left:calc(50% - 12px);width:24px;height:4px;background:#e7b446}.character-info,.character-tags{padding:9px}.character-info b{font-size:11px}.character-type,.character-info p{display:block;color:#718096;font-size:9px;margin:5px 0}.character-info strong{color:#6ed3ab}.character-tags span,.tag-chip{font-size:8px;color:#b2bdcc;background:#121a27;border:1px solid #263246;border-radius:4px;padding:4px}.tag-section{padding-top:18px}.tag-group{margin:12px 0}.tag-category{display:flex;justify-content:space-between;color:#9aa6b6;font-size:9px}.tag-line{flex:1;border-top:1px solid #1b2637;margin:auto 8px}.t-amber{color:#e9b64f!important}.t-violet{color:#bd9af2!important}.t-rose{color:#f48b9b!important}.t-indigo{color:#8ab6ed!important}.insight-card{display:flex;gap:9px;padding:11px;margin-top:15px;border:1px solid #57411c75;border-radius:7px;color:#f8bb4f}.insight-card p{color:#9aa6b6;font-size:9px;line-height:1.6}.insight-card button{border:0;background:none;color:#e5b34f;font-size:9px}.upload-box{height:150px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:9px;border-style:dashed;color:#e7b34c;cursor:pointer}.upload-box b{color:#cbd5e1;font-size:10px}.upload-box span,.upload-box strong{font-size:9px;color:#94a3b8}.hidden-file{display:none}.toast{position:fixed;z-index:10;right:24px;top:80px;padding:12px 16px;border:1px solid #235443;border-radius:8px;background:#0c1a19;color:#b8e9d5;font-size:11px}.skeleton-list{display:flex;flex-direction:column;gap:12px}.skeleton-card{height:250px;padding:15px;border:1px solid #1e293b;border-radius:8px;background:#0a1120}.skeleton-line,.skeleton-image{height:10px;margin:10px 0;border-radius:8px;background:linear-gradient(90deg,#131c2a,#263448,#131c2a);background-size:200% 100%;animation:shimmer 1.3s infinite}.skeleton-image{height:140px}@keyframes shimmer{to{background-position:-200% 0}}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1150px){.workspace{grid-template-columns:230px minmax(0,1fr)}.right-panel{display:none}}@media(max-width:720px){.topbar{padding:0 12px}.project-name input{width:90px}.workspace{display:block}.left-panel,.right-panel{display:none}.canvas{padding:18px 12px}.shot-list.grid-cols-1.md\\:grid-cols-2{grid-template-columns:1fr}.list-mode .shot-card{grid-template-columns:90px minmax(0,1fr)}.collab-pill{font-size:0}}
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
/* ---- 故事板卡片：场景层与首帧 ---- */
.scene-layer{position:absolute;inset:0;pointer-events:none}
.scene-layer svg{width:100%;height:100%;display:block}
.scene-reference{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.scene-actions{position:absolute;top:6px;right:6px;display:flex;gap:4px;opacity:0;transition:opacity .15s}
.shot-card:hover .scene-actions,.scene-actions:focus-within{opacity:1}
.scene-actions button{width:22px;height:22px;display:grid;place-items:center;border:1px solid #33415a;border-radius:6px;background:#0b1220cc;color:#cbd5e1}
.scene-actions button:hover{border-color:#f59e0b88;color:#fbbf24}
.shot-top-right{display:flex;align-items:center;gap:6px}
.shot-delete{width:24px;height:24px;display:grid;place-items:center;border:1px solid #33415a;border-radius:6px;background:#0b1220;color:#64748b;opacity:.75;transition:opacity .15s,color .15s,border-color .15s}
.shot-delete:hover,.shot-delete:focus-visible{opacity:1;border-color:#f43f5e88;color:#fda4af}
.shot-meta{display:flex;gap:6px;margin:6px 0 8px}
.shot-meta span{padding:2px 6px;border:1px solid #1e293b;border-radius:4px;background:#0b1220;color:#8fa0b8;font:9px 'DM Mono';letter-spacing:.4px}
/* ---- 镜头计划面板（B4） ---- */
.plan-panel{border:1px solid #1b2739;border-radius:10px;background:#080e18;padding:14px 15px 12px;margin-bottom:14px}
.plan-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.plan-head h3{margin:3px 0 0;font-size:14px;color:#f8fafc}
.plan-head-actions{display:flex;gap:8px;align-items:center}
.plan-cancel{height:34px;padding:0 12px;flex:none}
.plan-confirm{height:34px;padding:0 14px;min-width:150px}
.plan-narrative{margin:10px 0 4px;color:#93a3b8;font-size:10px;line-height:1.6}
.plan-error{margin:6px 0;color:#fda4af;font-size:10px}
.plan-rows{display:flex;flex-direction:column;gap:6px;margin:10px 0}
.plan-row{display:grid;grid-template-columns:26px 62px 96px 62px 132px 1fr 18px 24px;gap:6px;align-items:center;padding:5px 0;border-bottom:1px solid #131c2b}
.plan-row.is-pending{opacity:.75}
.plan-row.is-error{border-bottom-color:#7f1d1d}
.plan-row select,.plan-row input{height:28px;padding:0 6px;border:1px solid #1e293b;border-radius:6px;background:#0a1120;color:#cbd5e1;font-size:10px;outline:none;min-width:0}
.plan-row select:focus,.plan-row input:focus{border-color:#f59e0b88}
.plan-index{color:#64748b;font:10px 'DM Mono'}
.plan-state{display:grid;place-items:center;color:#fbbf24}
.plan-row.is-error .plan-state{color:#f43f5e}
.plan-remove{width:24px;height:24px;display:grid;place-items:center;border:0;border-radius:6px;background:transparent;color:#64748b}
.plan-remove:hover{background:#1a2434;color:#fda4af}
.plan-add{display:inline-flex;align-items:center;gap:5px;padding:6px 10px;border:1px dashed #33415a;border-radius:7px;background:transparent;color:#8fa0b8;font-size:10px}
.plan-add:hover{border-color:#f59e0b88;color:#fbbf24}
/* ---- 缩略导航条（C3，等宽，非时间轴） ---- */
.board-strip{display:flex;gap:6px;overflow-x:auto;padding:10px 2px 4px;margin-top:10px;border-top:1px solid #131c2b}
.strip-item{flex:0 0 84px;display:flex;flex-direction:column;gap:4px;padding:0;border:1px solid transparent;border-radius:7px;background:transparent}
.strip-item.active{border-color:#f59e0b;background:#1a2434}
.strip-thumb{display:block;width:100%;aspect-ratio:16/9;border-radius:5px;overflow:hidden;background-size:cover}
.strip-thumb img{width:100%;height:100%;object-fit:cover}
.strip-index{color:#7b8798;font:9px 'DM Mono';letter-spacing:.6px}
.strip-item.active .strip-index{color:#fbbf24}
/* ---- 微调对比（B1） ---- */
.sheet-wide{max-width:720px}
.sheet-quote{margin:0;padding:8px 10px;border-left:2px solid #f59e0b;background:#0b1220;color:#cbd5e1;font-size:11px;line-height:1.6}
.diff-list{display:flex;flex-direction:column;gap:10px;max-height:46vh;overflow:auto}
.diff-row{padding:9px 10px;border:1px solid #16202f;border-radius:8px;background:#080e18}
.diff-row.changed{border-color:#3f2f14;background:#0d1017}
.diff-row header{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.diff-row header b{font-size:10px;color:#cbd5e1}
.diff-tag{padding:1px 6px;border-radius:4px;background:#1f2a3a;color:#fbbf24;font-size:8px}
.diff-tag.muted{background:#131c2b;color:#64748b}
.diff-before,.diff-after,.diff-same{margin:0;font-size:10px;line-height:1.7;white-space:pre-wrap;word-break:break-word}
.diff-before{color:#7b8798;text-decoration:line-through;text-decoration-color:#f43f5e66}
.diff-after{color:#e2e8f0}
.diff-same{color:#7b8798}
.diff-arrow{margin:3px 0;color:#f59e0b}
/* ---- 导出（E1/E3） ---- */
.export-options{display:flex;flex-direction:column;gap:6px}
.export-option{display:flex;flex-direction:column;gap:3px;padding:9px 11px;border:1px solid #1e293b;border-radius:8px;background:#0a1120;text-align:left}
.export-option.active{border-color:#f59e0b;background:#1a2434}
.export-option b{font-size:11px;color:#cbd5e1}
.export-option small{color:#64748b;font-size:9px}
.export-issues{padding:9px 10px;border:1px solid #3f2f14;border-radius:8px;background:#0d0f16}
.export-summary{display:flex;align-items:center;gap:6px;margin:0 0 6px;color:#fbbf24;font-size:10px}
.export-summary.ok{color:#86efac}
.export-issues ul{margin:0 0 8px;padding-left:16px;max-height:26vh;overflow:auto}
.export-issues li{font-size:9px;line-height:1.7;color:#93a3b8}
.export-issues li.error{color:#fda4af}
/* ---- 重排 / 角色绑定（A1 / F1 / F2） ---- */
.shot-move-group{display:flex;flex-direction:column;gap:1px}
.shot-move{width:22px;height:14px;display:grid;place-items:center;border:1px solid #33415a;border-radius:4px;background:#0b1220;color:#7b8798;padding:0}
.shot-move:hover:not(:disabled){border-color:#f59e0b88;color:#fbbf24}
.shot-move:disabled{opacity:.3;cursor:not-allowed}
.shot-bindings{display:flex;flex-wrap:wrap;align-items:center;gap:5px;margin:0 0 8px}
.binding-chip{display:inline-flex;align-items:center;gap:3px;padding:3px 7px;border:1px solid #2b3a52;border-radius:999px;background:#0d1626;color:#9fb0c8;font-size:9px}
.binding-chip.missing{border-color:#7f5f18;background:#2a1f0a;color:#fbbf24}
.binding-add,.binding-inject{display:inline-flex;align-items:center;gap:4px;padding:3px 7px;border:1px dashed #33415a;border-radius:999px;background:transparent;color:#7b8798;font-size:9px}
.binding-add:hover,.binding-inject:hover{border-color:#f59e0b88;color:#fbbf24}
.binding-inject{border-style:solid}
.binding-list{display:flex;flex-direction:column;gap:6px;max-height:44vh;overflow:auto}
.binding-option{display:flex;align-items:center;gap:10px;padding:9px 10px;border:1px solid #1e293b;border-radius:8px;background:#0a1120;text-align:left}
.binding-option.active{border-color:#f59e0b;background:#1a2434}
.binding-mark{width:16px;height:16px;flex:none;display:grid;place-items:center;border:1px solid #33415a;border-radius:4px;color:#fbbf24}
.binding-option.active .binding-mark{border-color:#f59e0b;background:#f59e0b22}
.binding-body{display:flex;flex-direction:column;gap:2px;min-width:0;flex:1}
.binding-body b{font-size:11px;color:#e2e8f0}
.binding-body small{font-size:9px;color:#64748b}
.binding-body em{font-style:normal;font-size:9px;color:#5b6779;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.binding-warn{color:#fbbf24;flex:none}
/* ---- 锚点：角色派生 + 命中统计 ---- */
.anchor-label{display:flex;align-items:center;gap:6px;margin:12px 0 6px;color:#9aa6b6;font-size:9px;letter-spacing:.3px}
.anchor-label .muted{margin-left:auto}
.anchor-char{padding:4px 9px;border:1px solid #263246;border-radius:999px;background:#0b1220;color:#7b8798;font-size:9px}
.anchor-char:hover{border-color:#f59e0b66;color:#cbd5e1}
.anchor-char.chosen{border-color:#f59e0b;background:#2a1f0a;color:#fbbf24}
.anchor-stats{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:3px}
.anchor-stats li{display:flex;align-items:center;gap:6px;font-size:9px;color:#8fa0b8}
.anchor-stats li .anchor-text{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:'DM Mono',monospace}
.anchor-stats li .anchor-hit{padding:1px 5px;border:1px solid #263246;border-radius:4px;color:#7b8798;font-size:8px}
.anchor-stats li.miss .anchor-text{color:#fbbf24}
.anchor-stats li.miss .anchor-hit{border-color:#7f5f18;color:#fbbf24}
.anchor-status{display:flex;flex-wrap:wrap;gap:3px;align-items:center;min-width:0}
.anchor-pill{display:inline-flex;align-items:center;gap:2px;padding:2px 6px;border:1px solid #263246;border-radius:999px;background:#0b1220;color:#8fa0b8;font:8px 'DM Mono',monospace}
.anchor-pill.miss{border-color:#7f5f18;background:#2a1f0a;color:#fbbf24}
.prompt-foot-right{display:flex;align-items:center;gap:6px;flex:none}
.anchor-fix{padding:2px 7px;border:1px solid #7f5f18;border-radius:999px;background:#2a1f0a;color:#fbbf24;font-size:8px}
.anchor-fix:hover{background:#3d2c0d}
/* ---- 资产中心（居中大弹窗，替代原右栏） ---- */
.asset-btn{display:flex;align-items:center;gap:6px;height:34px;padding:0 12px;border:1px solid #1e293b;border-radius:7px;background:#0b1220;color:#cbd5e1;font-size:11px}
.asset-btn:hover{border-color:#f59e0b66;color:#fbbf24}
.asset-gate{position:fixed;inset:0;z-index:60;display:grid;place-items:center;padding:24px;background:#020617cc;backdrop-filter:blur(6px)}
.asset-center{width:min(1040px,96vw);max-height:88vh;display:flex;flex-direction:column;border:1px solid #1e293b;border-radius:14px;background:#070d1a;box-shadow:0 30px 90px #000000a0;overflow:hidden}
.asset-center-head{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 20px;border-bottom:1px solid #131c2b}
.asset-center-head h2{margin:3px 0 0;font-size:15px;color:#f8fafc}
.asset-center-actions{display:flex;align-items:center;gap:8px}
.asset-search{display:flex;align-items:center;gap:6px;height:32px;padding:0 10px;border:1px solid #1e293b;border-radius:7px;background:#0a1120;color:#64748b}
.asset-search input{width:190px;border:0;background:transparent;color:#cbd5e1;font-size:11px;outline:none}
.asset-center-body{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:18px;padding:16px 20px;overflow:auto}
.asset-center-column{min-width:0;display:flex;flex-direction:column;gap:10px}
.asset-center-title{display:flex;align-items:center;gap:7px;font-size:11px;color:#cbd5e1}
.asset-center-title .subtle{margin-left:auto}
.asset-filter-clear{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border:1px solid #f59e0b66;border-radius:999px;background:#2a1f0a;color:#fbbf24;font-size:9px}
.asset-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.asset-center-state{display:flex;align-items:center;justify-content:center;gap:8px;padding:48px 20px;color:#93a3b8;font-size:11px}
.asset-center-state.error{color:#fda4af}
.asset-center-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 20px;border-top:1px solid #131c2b;color:#64748b;font-size:9px}
.asset-center-foot .subtle{display:inline-flex;align-items:center;gap:4px}
.asset-insight{margin-top:auto}
@media (max-width:1200px){.asset-center-body{grid-template-columns:minmax(0,1fr)}}
.idea-warn{color:#fbbf24}
.conflict-reload{padding:4px 10px;border:1px solid #7f5f18;border-radius:999px;background:#2a1f0a;color:#fbbf24;font-size:9px}
.conflict-reload:hover{background:#3d2c0d}
</style>
