<template>
  <div class="slidev-layout hc-statement">
    <div class="hc-statement-inner"><slot /></div>
  </div>
</template>

<style>
.hc-statement { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.hc-statement-inner { max-width: 24em; }
.hc-statement .hc-eyebrow { display: block; margin-bottom: 1.4rem; }
.hc-statement h1 {
  font-family: var(--hc-font-serif) !important;
  font-weight: 700;
  font-size: 2.6rem;
  line-height: 1.18;
  letter-spacing: -.015em;
  color: var(--hc-ink);
}
.hc-statement h1 em { color: var(--hc-blue); font-style: normal; }
.hc-statement h1 .amber { color: var(--hc-amber-700); }
.hc-statement p { font-size: 1.05rem; color: var(--hc-ink-2); margin-top: 1.4rem; }
</style>
