<script setup lang="ts">
/**
 * 登录 / 首次初始化。
 *
 * 库里一个账号都没有时（例如刚部署到新环境），直接显示"创建管理员"表单，
 * 免去依赖部署平台环境变量建号；建完这个入口就永久关闭。
 */
import { onMounted, ref } from 'vue'
import { LoaderCircle, LockKeyhole, ShieldCheck } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'

const { login, setup, loggingIn, loginError, needsSetup, checkSetup } = useAuth()

const email = ref('')
const password = ref('')
const confirm = ref('')
const displayName = ref('')
const remember = ref(false)
const localError = ref('')

onMounted(() => {
  // 正常情况下 bootstrap() 已经查过；这里兜底一次，避免刷新后状态丢失
  if (!needsSetup.value) void checkSetup()
})

async function submitLogin() {
  if (loggingIn.value) return
  await login(email.value.trim(), password.value, remember.value)
  password.value = ''
}

async function submitSetup() {
  if (loggingIn.value) return
  localError.value = ''
  if (!email.value.includes('@')) {
    localError.value = '请填写有效的邮箱'
    return
  }
  if (password.value.length < 10) {
    localError.value = '密码至少需要 10 位'
    return
  }
  if (password.value !== confirm.value) {
    localError.value = '两次输入的密码不一致'
    return
  }
  const ok = await setup(email.value.trim(), password.value, displayName.value.trim())
  if (ok) {
    password.value = ''
    confirm.value = ''
  }
}
</script>

<template>
  <div class="login-gate" role="dialog" aria-modal="true" :aria-label="needsSetup ? '初始化管理员' : '登录'">
    <form v-if="needsSetup" class="login-card" @submit.prevent="submitSetup">
      <div class="login-brand">
        <span class="brand-icon"><ShieldCheck :size="18" /></span>
        <div><b>首次初始化</b><small>创建第一个管理员账号</small></div>
      </div>

      <label class="login-field">
        <span>邮箱</span>
        <input v-model="email" type="email" autocomplete="username" required placeholder="you@example.com" />
      </label>

      <label class="login-field">
        <span>显示名称（可选）</span>
        <input v-model="displayName" type="text" maxlength="40" placeholder="管理员" />
      </label>

      <label class="login-field">
        <span>密码</span>
        <input
          v-model="password"
          type="password"
          autocomplete="new-password"
          required
          placeholder="至少 10 位"
        />
      </label>

      <label class="login-field">
        <span>确认密码</span>
        <input
          v-model="confirm"
          type="password"
          autocomplete="new-password"
          required
          placeholder="再输入一次"
        />
      </label>

      <p v-if="localError || loginError" class="login-error">{{ localError || loginError }}</p>

      <button class="login-submit" type="submit" :disabled="loggingIn">
        <LoaderCircle v-if="loggingIn" class="spin" :size="15" />
        {{ loggingIn ? '正在创建…' : '创建管理员并进入' }}
      </button>

      <p class="login-hint">这个入口只在系统还没有任何账号时出现；创建成功后自动关闭</p>
    </form>

    <form v-else class="login-card" @submit.prevent="submitLogin">
      <div class="login-brand">
        <span class="brand-icon"><LockKeyhole :size="18" /></span>
        <div><b>ReCut Agent</b><small>登录后继续创作</small></div>
      </div>

      <label class="login-field">
        <span>邮箱</span>
        <input
          v-model="email"
          type="email"
          autocomplete="username"
          required
          placeholder="you@example.com"
        />
      </label>

      <label class="login-field">
        <span>密码</span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          placeholder="••••••••"
        />
      </label>

      <label class="login-remember">
        <input v-model="remember" type="checkbox" />
        <span>记住我（30 天内免登录）</span>
      </label>

      <p v-if="loginError" class="login-error">{{ loginError }}</p>

      <button class="login-submit" type="submit" :disabled="loggingIn">
        <LoaderCircle v-if="loggingIn" class="spin" :size="15" />
        {{ loggingIn ? '正在登录…' : '登录' }}
      </button>

      <p class="login-hint">账号由管理员创建；连续输错会被临时锁定，忘记密码请联系管理员</p>
    </form>
  </div>
</template>
