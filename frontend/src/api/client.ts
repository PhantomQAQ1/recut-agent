/** 统一的 API 访问层：带上会话 cookie、解析后端错误、集中处理 401。 */

export class ApiError extends Error {
  readonly status: number
  /** 后端随错误返回的结构化信息，例如 used_by、current_version。 */
  readonly data: Record<string, unknown>

  constructor(message: string, status: number, data: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

/** 这些路径上的 401 是"预期结果"（未登录 / 密码错误），不该触发重新登录弹窗。 */
const AUTH_PATHS = ['/api/v1/auth/login', '/api/v1/auth/me', '/api/v1/auth/logout']

let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

type RequestOptions = { body?: unknown; form?: FormData; signal?: AbortSignal }

async function readError(
  response: Response,
): Promise<{ message: string; data: Record<string, unknown> }> {
  try {
    const data = (await response.json()) as Record<string, unknown>
    const detail = data.detail
    if (typeof detail === 'string') return { message: detail, data }
    if (Array.isArray(detail)) return { message: '请求参数不合法', data }
    return { message: `请求失败（HTTP ${response.status}）`, data }
  } catch {
    /* 非 JSON 响应，落到下面的兜底文案 */
  }
  return { message: `请求失败（HTTP ${response.status}）`, data: {} }
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const init: RequestInit = {
    method,
    credentials: 'include', // 会话 cookie 必须带上
    headers: {},
  }
  if (options.form) {
    init.body = options.form
  } else if (options.body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(options.body)
  }
  if (options.signal) init.signal = options.signal

  const response = await fetch(path, init)

  if (response.status === 401 && !AUTH_PATHS.some((item) => path.startsWith(item))) {
    // 会话过期或已被吊销：通知上层回到登录态，但不清空本地故事板。
    onUnauthorized?.()
  }
  if (!response.ok) {
    const { message, data } = await readError(response)
    throw new ApiError(message, response.status, data)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, { body }),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, { body }),
  delete: <T>(path: string) => request<T>('DELETE', path),
  upload: <T>(path: string, form: FormData) => request<T>('POST', path, { form }),
}
