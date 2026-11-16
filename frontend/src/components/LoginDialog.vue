<script setup lang="ts">
import { ref } from 'vue'
import { LoaderCircle, LockKeyhole } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'

const { login, loggingIn, loginError } = useAuth()

const email = ref('')
const password = ref('')
const remember = ref(false)

async function submit() {
  if (loggingIn.value) return
  await login(email.value.trim(), password.value, remember.value)
  password.value = ''
}
</script>

<template>
  <div class="login-gate" role="dialog" aria-modal="true" aria-label="登录">
    <form class="login-card" @submit.prevent="submit">
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
