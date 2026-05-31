<script setup>
defineProps({
  persona: { type: String, default: 'judith' },
  personaName: { type: String, default: 'Judith' },
  type: { type: String, default: 'price_reframe · nudge' },
  primary: { type: String, default: 'Continue with Optimal' },
  ghost: { type: String, default: 'Book a 10-min call' },
  compact: { type: Boolean, default: false },
})
</script>

<template>
  <div class="hc-modal" :class="{ compact }">
    <div class="hc-nudge-head">
      <span class="spark">
        <svg width="15" height="15" viewBox="0 0 14 14"><path d="M7 0l1.6 4.2L13 5.6 9 7.8 8.2 12 7 8.6 4 11l1-4L0 5.4l4.8-.5z" fill="currentColor"/></svg>
      </span>
      <span>
        <div class="hc-nudge-kicker">Smart assist</div>
        <div class="hc-nudge-from">A nudge from HealthCover</div>
      </span>
      <span class="hc-nudge-persona"><span class="pd" :class="persona" />{{ personaName }}</span>
      <button class="hc-close">×</button>
    </div>
    <div class="hc-nudge-type">{{ type }}</div>
    <div class="hc-chat">
      <div class="hc-msg bot">
        <slot />
      </div>
      <slot name="turns" />
    </div>
    <div class="hc-actions">
      <button class="primary">{{ primary }}</button>
      <button v-if="ghost" class="ghost">{{ ghost }}</button>
    </div>
  </div>
</template>
