/**
 * 撤销/重做（A2）。
 *
 * 做法：监听 shots 的深度变化，停顿 700ms 后把「变更前」的快照压栈。
 * 这样连续输入不会产生几十个撤销步，而每次停顿对应一步。
 *
 * 没有做成"每个字段单独的命令对象"：故事板的编辑入口太多（直接 v-model、
 * 微调采用、展开填充、绑定角色……），快照方案能一次性覆盖所有入口。
 */

import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { Shot } from '../lib/types'

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T

export function useHistory(
  source: () => Shot[],
  restore: (shots: Shot[]) => void,
  limit = 50,
) {
  const past = ref<Shot[][]>([])
  const future = ref<Shot[][]>([])
  let applying = false
  let timer: number | undefined
  let last = clone(source())

  function reset() {
    window.clearTimeout(timer)
    past.value = []
    future.value = []
    last = clone(source())
  }

  function commit() {
    if (applying) return
    past.value = [...past.value, last].slice(-limit)
    future.value = []
    last = clone(source())
  }

  watch(
    source,
    () => {
      if (applying) return
      window.clearTimeout(timer)
      timer = window.setTimeout(commit, 700)
    },
    { deep: true },
  )

  function apply(next: Shot[]) {
    applying = true
    restore(clone(next))
    last = clone(next)
    window.setTimeout(() => {
      applying = false
    }, 0)
  }

  function undo() {
    const previous = past.value[past.value.length - 1]
    if (!previous) return false
    past.value = past.value.slice(0, -1)
    future.value = [...future.value, clone(source())]
    apply(previous)
    return true
  }

  function redo() {
    const next = future.value[future.value.length - 1]
    if (!next) return false
    future.value = future.value.slice(0, -1)
    past.value = [...past.value, clone(source())]
    apply(next)
    return true
  }

  const canUndo = computed(() => past.value.length > 0)
  const canRedo = computed(() => future.value.length > 0)

  onBeforeUnmount(() => window.clearTimeout(timer))

  return { undo, redo, canUndo, canRedo, reset, commit }
}
