<template>
  <router-view />
</template>

<script setup>
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
#app { min-height: 100vh; }

/* ===== 页面切换动画（仅透明度，避免白屏） ===== */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease;
}
.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}

/* ===== 卡片悬浮 ===== */
.el-card {
  transition: transform 0.22s ease, box-shadow 0.22s ease !important;
}
.el-card:hover {
  transform: translateY(-1px);
}

/* ===== 按钮点击反馈 ===== */
.el-button {
  transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.el-button:active {
  transform: scale(0.96) !important;
}

/* ===== 菜单项过渡 ===== */
.el-menu-item {
  transition: background 0.2s ease, color 0.2s ease, padding 0.3s ease !important;
}

/* ===== Tab 内容淡入 ===== */
.el-tab-pane {
  animation: tabFadeIn 0.3s ease;
}
@keyframes tabFadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ===== 统计卡片数字跳动 ===== */
@keyframes countUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
.stat-card-enter {
  animation: countUp 0.4s ease forwards;
}

/* ===== 侧边栏折叠过渡 ===== */
.el-aside {
  transition: width 0.3s ease !important;
}

/* ===== 标签渐入 ===== */
@keyframes fadeInScale {
  from { opacity: 0; transform: scale(0.9); }
  to   { opacity: 1; transform: scale(1); }
}
.el-tag {
  animation: fadeInScale 0.2s ease;
}

/* ===== 表格行悬浮 ===== */
.el-table tbody tr {
  transition: background 0.15s ease;
}

/* ===== 输入框聚焦动画 ===== */
.el-input__inner,
.el-textarea__inner {
  transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
</style>
