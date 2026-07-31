<template>
  <header class="page-hero" :class="{ compact }">
    <div class="page-hero-copy">
      <span class="page-hero-eyebrow">{{ eyebrow }}</span>
      <div class="page-hero-title-row">
        <span v-if="icon" class="page-hero-icon">
          <el-icon><component :is="icon" /></el-icon>
        </span>
        <div>
          <h1>{{ title }}</h1>
          <p v-if="description">{{ description }}</p>
        </div>
      </div>
      <div v-if="$slots.meta" class="page-hero-meta"><slot name="meta" /></div>
    </div>
    <div v-if="$slots.actions" class="page-hero-actions"><slot name="actions" /></div>
  </header>
</template>

<script setup>
defineProps({
  eyebrow: { type: String, default: 'LEARNING WORKSPACE' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  icon: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})
</script>

<style scoped>
.page-hero {
  position: relative;
  display: flex;
  min-height: 132px;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  overflow: hidden;
  margin-bottom: 18px;
  padding: 25px 28px;
  border: 1px solid rgba(203, 211, 234, .72);
  border-radius: 20px;
  background:
    radial-gradient(circle at 89% 12%, rgba(86,183,220,.18), transparent 28%),
    linear-gradient(128deg, rgba(255,255,255,.98), rgba(244,247,255,.96));
  box-shadow: var(--shadow-sm);
}
.page-hero::after {
  position: absolute;
  right: -54px;
  bottom: -100px;
  width: 270px;
  height: 190px;
  border: 1px solid rgba(70,87,216,.12);
  border-radius: 50%;
  content: '';
  transform: rotate(-18deg);
}
.page-hero-copy,
.page-hero-actions { position: relative; z-index: 1; }
.page-hero-eyebrow {
  display: block;
  margin-bottom: 8px;
  color: var(--primary);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .17em;
}
.page-hero-title-row { display: flex; align-items: flex-start; gap: 13px; }
.page-hero-icon {
  display: grid;
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  place-items: center;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(145deg, var(--primary), #6678e8);
  box-shadow: 0 9px 20px rgba(70,87,216,.22);
}
.page-hero h1 {
  margin: 0;
  color: var(--ink-950);
  font-size: clamp(22px, 2.2vw, 30px);
  font-weight: 760;
  letter-spacing: -.04em;
}
.page-hero p {
  max-width: 680px;
  margin: 7px 0 0;
  color: var(--ink-400);
  font-size: 12px;
  line-height: 1.7;
}
.page-hero-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.page-hero-actions { display: flex; align-items: center; gap: 9px; }
.page-hero.compact { min-height: 104px; padding-block: 19px; }
@media (max-width: 720px) {
  .page-hero { min-height: 0; align-items: flex-start; flex-direction: column; padding: 21px 19px; border-radius: 17px; }
  .page-hero-actions { width: 100%; }
  .page-hero-actions :deep(.el-button) { flex: 1; }
}
</style>
