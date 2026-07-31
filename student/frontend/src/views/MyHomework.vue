<template>
  <div class="my-homework page-fade">
    <div class="hw-header">
      <h2><el-icon><Notebook /></el-icon> 我的作业</h2>
      <el-tag v-if="pendingCount" type="danger">{{ pendingCount }} 份待提交</el-tag>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane name="pending">
        <template #label>
          <span>待提交作业 <el-badge v-if="pendingCount" :value="pendingCount" /></span>
        </template>

        <div v-loading="loading">
          <el-empty v-if="pendingList.length === 0 && !loading" description="暂无待提交作业" />
          <div class="hw-cards">
            <el-card v-for="h in pendingList" :key="h.id" class="hw-card" shadow="hover">
              <div class="hw-card-top">
                <el-tag size="small">{{ h.course_name }}</el-tag>
                <span class="deadline" :class="{ urgent: h.isUrgent }">
                  <el-icon><Clock /></el-icon>
                  {{ h.deadlineText }}
                </span>
              </div>
              <h4>{{ h.title }}</h4>
              <p v-if="h.content" class="hw-desc">{{ h.content.substring(0, 120) }}{{ h.content.length > 120 ? '...' : '' }}</p>
              <div class="hw-card-foot">
                <span>👨‍🏫 {{ h.teacher_name }}</span>
                <el-button type="primary" size="small" @click="openSubmit(h)">提交作业</el-button>
              </div>
            </el-card>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="已批改作业" name="graded">
        <div v-loading="loading2">
          <el-empty v-if="gradedList.length === 0 && !loading2" description="暂无已批改作业" />
          <div class="hw-cards">
            <el-card v-for="s in gradedList" :key="s.id" class="hw-card" shadow="hover">
              <div class="hw-card-top">
                <el-tag size="small" v-if="s.assignment">{{ s.assignment.course_name }}</el-tag>
                <el-tag :type="s.score >= 80 ? 'success' : s.score >= 60 ? 'warning' : 'danger'" size="small">
                  {{ s.score }} 分
                </el-tag>
              </div>
              <h4>{{ s.assignment?.title || '作业' }}</h4>
              <p v-if="s.feedback" class="hw-feedback">💬 {{ s.feedback }}</p>
              <div class="hw-card-foot">
                <span>👨‍🏫 {{ s.graded_by || s.assignment?.teacher_name }}</span>
                <el-tag v-if="s.graded_at" size="small">{{ fmt(s.graded_at) }}</el-tag>
              </div>
            </el-card>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 提交弹窗 -->
    <el-dialog v-model="submitOpen" :title="'提交作业: ' + (submitting?.title || '')" width="560px">
      <div class="submit-info">
        <p><strong>课程:</strong> {{ submitting?.course_name }}</p>
        <p><strong>教师:</strong> 👨‍🏫 {{ submitting?.teacher_name }}</p>
        <p v-if="submitting?.deadline"><strong>截止:</strong> {{ fmt(submitting.deadline) }}</p>
        <div v-if="submitting?.content" class="hw-content" v-html="md(submitting.content)"></div>
      </div>
      <el-input v-model="answerText" type="textarea" :rows="5" placeholder="在此输入你的答案..." />
      <template #footer>
        <el-button @click="submitOpen = false">取消</el-button>
        <el-button type="primary" @click="doSubmit" :loading="submitting2">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Notebook, Clock } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { listAssignments, submitHomework, getMySubmissions } from '../api/homework'

const route = useRoute()
const activeTab = ref('pending')
const loading = ref(false)
const loading2 = ref(false)
const assignments = ref([])
const mySubmissions = ref([])
const submitOpen = ref(false)
const submitting = ref(null)
const answerText = ref('')
const submitting2 = ref(false)

const pendingList = computed(() => {
  const subIds = new Set(mySubmissions.value.map(s => s.assignment_id))
  return assignments.value
    .filter(a => !subIds.has(a.id) && a.status !== 'closed')
    .map(a => ({
      ...a,
      isUrgent: a.deadline ? dayjs(a.deadline).diff(dayjs(), 'hour') < 24 : false,
      deadlineText: a.deadline ? `截止 ${dayjs(a.deadline).format('MM/DD HH:mm')}` : '无截止',
    }))
})

const pendingCount = computed(() => pendingList.value.length)

const gradedList = computed(() =>
  mySubmissions.value.filter(s => s.status === 'graded')
)

function fmt(d) { return d ? dayjs(d).format('MM/DD HH:mm') : '' }
function md(t) { return t.replace(/\n/g, '<br>') }

async function load() {
  loading.value = true
  try {
    const params = route.query.course ? { course: route.query.course } : {}
    const [aRes, sRes] = await Promise.all([listAssignments(params), getMySubmissions()])
    assignments.value = aRes.data?.data?.assignments || aRes.data?.assignments || []
    mySubmissions.value = sRes.data?.data?.submissions || sRes.data?.submissions || []
  } catch { /* ignore */ }
  finally { loading.value = false; loading2.value = false }
}

function openSubmit(hw) {
  submitting.value = hw
  answerText.value = ''
  submitOpen.value = true
}

async function doSubmit() {
  if (!submitting.value) return
  submitting2.value = true
  try {
    await submitHomework(submitting.value.id, { content: answerText.value })
    ElMessage.success('提交成功！')
    submitOpen.value = false
    load()
  } catch {
    ElMessage.error('提交失败')
  }
  finally { submitting2.value = false }
}

onMounted(() => { load() })
</script>

<style scoped>
.my-homework { padding: 20px; max-width: 900px; margin: 0 auto; }
.hw-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.hw-header h2 { display: flex; align-items: center; gap: 8px; margin: 0; font-weight: 700; }
.hw-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; margin-top: 12px; }
.hw-card { border-radius: 12px; }
.hw-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.deadline { font-size: 12px; color: #999; display: flex; align-items: center; gap: 4px; }
.deadline.urgent { color: #f56c6c; font-weight: 600; }
.hw-desc { font-size: 13px; color: #666; margin: 6px 0; line-height: 1.6; }
.hw-feedback { font-size: 13px; background: #f0f9eb; padding: 8px 12px; border-radius: 8px; color: #67c23a; margin: 6px 0; }
.hw-card-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; color: #999; font-size: 12px; }
.submit-info { margin-bottom: 14px; }
.submit-info p { margin: 4px 0; font-size: 13px; }
.hw-content { background: #f5f7fa; padding: 12px; border-radius: 8px; margin-top: 8px; font-size: 13px; line-height: 1.7; }
</style>
