<script setup>
defineProps({ active: { type: String, default: 'judith' } })
</script>

<template>
  <div class="flex items-center gap-4">
    <div class="hc-personas">
      <span class="hc-pl" :class="{ on: active === 'judith' }"><span class="pd judith" />Judith</span>
      <span class="hc-pl" :class="{ on: active === 'franz' }"><span class="pd franz" />Franz</span>
      <span class="hc-pl" :class="{ on: active === 'peter' }"><span class="pd peter" />Peter</span>
    </div>
    <span class="hc-help"><span class="dot" />Coach active</span>
  </div>
</template>
