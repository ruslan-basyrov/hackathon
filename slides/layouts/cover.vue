<template>
  <div class="slidev-layout hc-cover">
    <div class="hc-cover-top">
      <Brand :size="30" />
      <PersonaSwitch active="judith" />
    </div>
    <div class="hc-cover-main">
      <slot />
    </div>
    <div class="hc-cover-rule" />
  </div>
</template>

<style>
.hc-cover { display: flex; flex-direction: column; padding: 0 !important; }
.hc-cover-top { display: flex; align-items: center; justify-content: space-between; padding: 1.4rem 3.5rem; border-bottom: 1px solid var(--hc-cream-line); }
.hc-cover-main { flex: 1 1 auto; display: flex; flex-direction: column; justify-content: center; padding: 0 3.5rem; }
.hc-cover-rule { height: 8px; background: linear-gradient(90deg, var(--hc-blue) 0 38%, var(--hc-amber) 38% 100%); }
.hc-cover h1 { font-family: var(--hc-font-serif) !important; font-size: 3.4rem; font-weight: 700; line-height: 1.05; letter-spacing: -.02em; margin: .2rem 0 .6rem; }
.hc-cover .hc-sub { font-size: 1.15rem; color: var(--hc-ink-2); max-width: 30em; line-height: 1.45; }
</style>
