<template>
  <div class="slidev-layout hc-default">
    <div class="hc-default-main">
      <slot />
    </div>
    <div class="hc-foot-brand"><span class="sq" />Conversion&nbsp;Coach · Insurance&nbsp;AI / UNIQA</div>
    <div class="hc-page">{{ $slidev?.nav?.currentPage }}</div>
  </div>
</template>

<style>
.hc-default { display: flex; flex-direction: column; }
.hc-default-main { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; justify-content: center; }
.hc-page {
  position: absolute; right: 3.5rem; bottom: 1.4rem;
  font: 700 .72rem/1 var(--hc-font-mono);
  color: var(--hc-ink-3); font-variant-numeric: tabular-nums;
}
</style>
