<script setup>
defineProps({
  pkey: { type: String, default: 'judith' },
  name: String,
  segment: String,
  drop: String,
  conversion: String,
  never: String,
  signal: String,
})
</script>

<template>
  <div class="hc-card flex flex-col gap-2 h-full">
    <div class="flex items-center gap-2">
      <span class="pd" :class="pkey" style="width:11px;height:11px" />
      <span class="font-800 text-[1.05rem]" style="color:var(--hc-ink)">{{ name }}</span>
      <span class="hc-kicker ml-auto">{{ segment }}</span>
    </div>
    <div class="text-[.8rem] mt-1">
      <div class="mb-1"><span class="hc-kicker">Drops at</span><br><span style="color:var(--hc-ink)">{{ drop }}</span></div>
      <div class="mb-1"><span class="hc-kicker">Win =</span><br><span style="color:var(--hc-ink)">{{ conversion }}</span></div>
      <div class="mb-1"><span class="hc-kicker">Signal</span><br><span class="font-mono text-[.72rem]" style="color:var(--hc-blue-700)">{{ signal }}</span></div>
    </div>
    <div class="hc-chip amber mt-auto" style="white-space:normal;align-self:flex-start">Never: {{ never }}</div>
  </div>
</template>
