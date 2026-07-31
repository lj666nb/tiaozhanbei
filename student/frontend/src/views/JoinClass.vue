<template>
  <div class="join-class page-fade">
    <div class="join-card">
      <div class="join-icon"><el-icon size="48"><School /></el-icon></div>
      <h2>加入班级</h2>
      <p>输入老师提供的班级编号，即可加入对应课程</p>
      <el-input v-model="code" placeholder="输入班级编号（如 AIc9896d40）" maxlength="20"
        style="width: 280px" size="large" @keydown.enter="doJoin" />
      <el-button type="primary" size="large" :loading="loading" @click="doJoin"
        style="margin-top: 16px; width: 280px">加入班级</el-button>
      <p v-if="result" class="result-msg" :class="{ ok: resultOk }">{{ result }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { School } from '@element-plus/icons-vue'
import axios from 'axios'

const code = ref('')
const loading = ref(false)
const result = ref('')
const resultOk = ref(false)

function studentName() {
  try {
    const raw = localStorage.getItem('user')
    if (raw) {
      const state = JSON.parse(raw)
      const u = state.user || state
      return u.username || u.nickname || '学生'
    }
  } catch { /* */ }
  return '学生'
}

async function doJoin() {
  if (!code.value.trim()) return
  loading.value = true
  result.value = ''
  try {
    const res = await axios.post('/api/course-mgmt/join-by-code', {
      code: code.value.trim(),
      student_name: studentName(),
    })
    result.value = res.data.message || '加入成功！'
    resultOk.value = true
    code.value = ''
  } catch (e) {
    result.value = e.response?.data?.detail || '加入失败，请检查编号是否正确'
    resultOk.value = false
  } finally { loading.value = false }
}
</script>

<style scoped>
.join-class { display: flex; justify-content: center; padding-top: 60px; }
.join-card { text-align: center; background: #fff; padding: 48px 40px; border-radius: 16px; box-shadow: 0 2px 16px rgba(0,0,0,0.06); }
.join-icon { color: #4657d8; margin-bottom: 16px; }
.join-card h2 { margin: 0 0 8px; font-weight: 700; }
.join-card p { color: #999; font-size: 14px; margin-bottom: 20px; }
.result-msg { margin-top: 12px; font-size: 14px; font-weight: 500; }
.result-msg.ok { color: #67c23a; }
.result-msg:not(.ok) { color: #f56c6c; }
</style>
