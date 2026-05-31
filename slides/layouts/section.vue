<script setup>
defineProps({ no: { type: String, default: '' } })
</script>

<template>
  <div class="slidev-layout hc-section">
    <div class="hc-section-inner">
      <div v-if="no" class="hc-section-no">{{ no }}</div>
      <div class="hc-section-body"><slot /></div>
    </div>
  </div>
</template>

<style>
.hc-section { background: var(--hc-blue-900) !important; color: #fff; display: flex; align-items: center; }
.hc-section-inner { display: flex; align-items: baseline; gap: 1.6rem; }
.hc-section-no { font: 800 5rem/1 var(--hc-font-serif); color: var(--hc-amber); letter-spacing: -.03em; }
.hc-section h1 { font-family: var(--hc-font-serif) !important; color: #fff !important; font-size: 2.8rem; font-weight: 700; line-height: 1.08; }
.hc-section h2 { color: #fff !important; }
.hc-section .hc-eyebrow { color: var(--hc-amber); }
.hc-section p { color: rgba(255,255,255,.78); font-size: 1.1rem; max-width: 30em; }
.hc-section strong { color: #fff; }
.hc-section a { color: var(--hc-amber); border: none; }
</style>
