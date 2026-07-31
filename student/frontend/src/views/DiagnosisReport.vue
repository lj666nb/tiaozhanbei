<template>
  <div class="report-page">
    <PageHero
      eyebrow="ASSESSMENT REPORT"
      :title="report ? `学情自测报告 #${report.session_id}` : '学情自测报告'"
      description="从知识掌握、能力维度和薄弱环节三个角度回看本次测评。"
      icon="DataAnalysis"
      compact
    >
      <template #actions>
        <el-button @click="$router.back()"><el-icon><ArrowLeft /></el-icon>返回</el-button>
        <el-button type="primary" @click="$router.push('/diagnosis')">再次测评</el-button>
      </template>
    </PageHero>
    <el-card v-if="report" shadow="hover" v-loading="loading">
      <el-descriptions :column="3" border style="margin-bottom:24px">
        <el-descriptions-item label="测评得分">{{ report.score }}/{{ report.total }}</el-descriptions-item>
        <el-descriptions-item label="正确率">
          <el-progress :percentage="report.correct_rate" :color="report.correct_rate >= 60 ? '#67C23A' : '#E6A23C'" :stroke-width="20" />
        </el-descriptions-item>
        <el-descriptions-item label="测评阶段">{{ report.stage }}</el-descriptions-item>
      </el-descriptions>

      <el-alert :title="report.report?.overall_assessment" type="info" :closable="false" style="margin-bottom:24px" />

      <el-row :gutter="20">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>知识点掌握分析</template>
            <div v-for="(info, tag) in report.report?.knowledge_analysis" :key="tag" class="knowledge-item">
              <div class="k-name">{{ tag }}</div>
              <el-progress :percentage="(info.mastery || 0) * 100" :color="getProgressColor(info.mastery)" />
              <div class="k-comment">{{ info.comment }}</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>能力维度分析</template>
            <div v-for="(info, ability) in report.report?.ability_analysis" :key="ability" class="ability-item">
              <div class="a-name">{{ ability }}</div>
              <el-progress :percentage="(info.score || 0) * 100" :color="getProgressColor(info.score)" :stroke-width="16" />
              <div class="a-comment">{{ info.comment }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" style="margin-top:20px">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><el-icon><Warning /></el-icon> 薄弱知识点</template>
            <el-tag v-for="w in report.report?.weak_points" :key="w" type="danger" style="margin:4px">{{ w }}</el-tag>
            <el-empty v-if="!report.report?.weak_points?.length" description="无明显薄弱点" :image-size="60" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><el-icon><Star /></el-icon> 优势领域</template>
            <el-tag v-for="s in report.report?.strong_points" :key="s" type="success" style="margin:4px">{{ s }}</el-tag>
            <el-empty v-if="!report.report?.strong_points?.length" description="继续加油" :image-size="60" />
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" style="margin-top:20px">
        <template #header><el-icon><Guide /></el-icon> 学习建议</template>
        <ul class="suggestions"><li v-for="s in report.report?.study_suggestions" :key="s">{{ s }}</li></ul>
        <el-alert :title="'下一步重点: ' + (report.report?.next_focus || '全面巩固')" type="success" :closable="false" style="margin-top:12px" />
      </el-card>
    </el-card>
    <el-empty v-else description="报告不存在" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useDiagnosisStore } from '../stores/diagnosis'
import PageHero from '../components/PageHero.vue'

const route = useRoute()
const store = useDiagnosisStore()
const report = ref(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try { report.value = await store.fetchReport(route.params.id) } catch(e) {}
  finally { loading.value = false }
})

function getProgressColor(mastery) {
  if (mastery >= 0.8) return '#67C23A'
  if (mastery >= 0.5) return '#E6A23C'
  return '#F56C6C'
}
</script>

<style scoped>
.page-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: bold; }
.knowledge-item, .ability-item { padding: 8px 0; border-bottom: 1px solid #f5f5f5; }
.k-name, .a-name { font-size: 14px; font-weight: 500; margin-bottom: 4px; }
.k-comment, .a-comment { font-size: 12px; color: #909399; margin-top: 4px; }
.suggestions li { padding: 6px 0; color: #606266; }
.report-page { padding-bottom: 30px; }
.report-page > .el-card :deep(.el-card__body) { padding: 24px !important; }
@media (max-width: 720px) {
  .report-page :deep(.el-descriptions__body .el-descriptions__table) { display: block; }
}
</style>
