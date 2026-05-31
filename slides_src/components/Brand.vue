<script setup>
defineProps({ size: { type: Number, default: 28 }, label: { type: Boolean, default: true } })
</script>

<template>
  <span class="hc-brand">
    <svg :width="size" :height="size" viewBox="0 0 28 28">
      <rect width="28" height="28" rx="8" fill="#0a51d0" />
      <rect x="12.4" y="6.5" width="3.2" height="15" rx="1.6" fill="#fff" />
      <rect x="6.5" y="12.4" width="15" height="3.2" rx="1.6" fill="#fff" />
    </svg>
    <b v-if="label">Health<span>Cover</span></b>
  </span>
</template>
