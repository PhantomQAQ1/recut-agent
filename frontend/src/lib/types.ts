/** 故事板的共享类型与常量（原先散落在 App.vue 里）。 */

export type SceneKind = 'lantern' | 'curtain' | 'sparks'

export type Shot = {
  id: number
  duration: string
  scale: string
  lens: string
  move: string
  title: string
  description: string
  prompt: string
  runwayPrompt: string
  edit: string
  palette: string
  scene: SceneKind
  /** 参考首帧（uploads.id）；老数据没有这个字段。 */
  reference_image_id?: number | null
  /** F1：绑定的角色资产 id；老数据没有这个字段。 */
  character_ids?: number[]
}

/** 绑定与一致性检查只关心这几个字段。 */
export type CharacterLike = {
  id: number
  name: string
  prompt_anchor: string
}

/** 卡片上渲染的角色绑定标签。 */
export type BindingChip = { id: number; name: string; missing: boolean }

export const MODELS = ['即梦 Jimeng', '可灵 Kling', 'Runway Gen-3'] as const
export type ModelName = (typeof MODELS)[number]

export const STYLES = ['搞笑反转', '燃向踩点', '黑深残', '日常整活'] as const

export const SCALE_OPTIONS = [
  '大远景 ELS',
  '远景 LS',
  '全景 WS',
  '中景 MS',
  '近景 CU',
  '特写 ECU',
] as const

export const LENS_OPTIONS = ['24mm', '28mm', '35mm', '50mm', '85mm'] as const

export const DURATION_OPTIONS = ['03s', '04s', '05s', '06s'] as const

export const MOVE_OPTIONS = [
  '固定机位 Static',
  '缓慢横移 Truck',
  '手持跟拍 Handheld',
  '环绕跟拍 Orbit',
  '急速推镜 Crash Zoom',
  '低机位升格 Low angle',
] as const

/** B4 阶段一的镜头计划（与后端 ShotPlan 对应）。 */
export type PlannedShot = {
  index: number
  duration: string
  scale: string
  lens: string
  move: string
  purpose: string
}

export type ShotPlan = {
  total_seconds: number
  narrative: string
  shots: PlannedShot[]
}

export function planSeconds(plan: ShotPlan): number {
  return plan.shots.reduce((sum, shot) => sum + shotSeconds(shot.duration), 0)
}

/** 生成请求里用的模型名（与后端 Literal 一致）。 */
export function isRunway(model: string): boolean {
  return model.includes('Runway')
}

export function activePrompt(shot: Shot, model: string): string {
  return isRunway(model) ? shot.runwayPrompt : shot.prompt
}

export function shotSeconds(duration: string): number {
  const parsed = Number.parseInt(duration, 10)
  return Number.isFinite(parsed) ? parsed : 0
}
