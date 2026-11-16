/**
 * 调色板：把后端存储的 id 映射成真正的渐变色值。
 *
 * 为什么不用 Tailwind 类名：
 * 原来的 `.scene-art` 用的是写死的 `background: linear-gradient(110deg, ...)`，
 * 而 `from-* / via-* / to-*` 只是设置 CSS 变量、没有任何规则去消费它们，
 * 所以三套配色渲染出来完全一样（实测确认）。改成显式色值后，
 * 既不依赖构建期扫描，也不会再出现"线上无色"的问题。
 *
 * id 保持不变是为了兼容已保存的项目数据。
 */

export type PaletteId =
  | 'from-amber-950 via-orange-950 to-slate-950'
  | 'from-indigo-950 via-slate-900 to-amber-950'
  | 'from-red-950 via-amber-950 to-slate-950'
  | 'from-teal-950 via-emerald-950 to-slate-950'
  | 'from-violet-950 via-purple-950 to-slate-950'
  | 'from-stone-800 via-stone-950 to-slate-950'
  | 'from-sky-950 via-slate-900 to-indigo-950'
  | 'from-rose-950 via-red-950 to-stone-950'

export type PaletteDefinition = {
  id: PaletteId
  label: string
  /** [起, 中, 止] */
  stops: [string, string, string]
}

export const PALETTES: PaletteDefinition[] = [
  {
    id: 'from-amber-950 via-orange-950 to-slate-950',
    label: '琥珀金',
    stops: ['#451a03', '#431407', '#020617'],
  },
  {
    id: 'from-indigo-950 via-slate-900 to-amber-950',
    label: '暮色蓝',
    stops: ['#1e1b4b', '#0f172a', '#451a03'],
  },
  {
    id: 'from-red-950 via-amber-950 to-slate-950',
    label: '烈焰红',
    stops: ['#450a0a', '#451a03', '#020617'],
  },
  {
    id: 'from-teal-950 via-emerald-950 to-slate-950',
    label: '幽绿',
    stops: ['#042f2e', '#022c22', '#020617'],
  },
  {
    id: 'from-violet-950 via-purple-950 to-slate-950',
    label: '紫罗兰',
    stops: ['#2e1065', '#3b0764', '#020617'],
  },
  {
    id: 'from-stone-800 via-stone-950 to-slate-950',
    label: '石青灰',
    stops: ['#292524', '#0c0a09', '#020617'],
  },
  {
    id: 'from-sky-950 via-slate-900 to-indigo-950',
    label: '冷空',
    stops: ['#082f49', '#0f172a', '#1e1b4b'],
  },
  {
    id: 'from-rose-950 via-red-950 to-stone-950',
    label: '血色',
    stops: ['#4c0519', '#450a0a', '#0c0a09'],
  },
]

const BY_ID = new Map<string, PaletteDefinition>(PALETTES.map((item) => [item.id, item]))

/** 未知 id（老数据/模型乱写）回落到第一套，保证永远有背景。 */
export function paletteBackground(id: string): string {
  const palette = BY_ID.get(id) ?? PALETTES[0]!
  const [from, via, to] = palette.stops
  return `linear-gradient(110deg, ${from} 0%, ${via} 46%, ${to} 100%)`
}

export function paletteLabel(id: string): string {
  return (BY_ID.get(id) ?? PALETTES[0]!).label
}
