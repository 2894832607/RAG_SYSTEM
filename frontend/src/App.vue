<template>
  <div class="app-shell">
    <header class="hero">
      <div>
        <p class="eyebrow">Poetry RAG Visualizer</p>
        <h1>Transform classical verses into evocative scenes.</h1>
        <p class="lede">
          Enter a classical poem and follow the RAG-enhanced task through retrieval, prompt enrichment, and final
          image generation.
        </p>
      </div>
    </header>
    <main>
      <RAGFlow />
    </main>
  </div>
</template>

<script setup>
import RAGFlow from './components/RAGFlow.vue';
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: radial-gradient(circle at top, #f8f3e8, #f3f0fc);
  color: #1e1e1e;
}
.hero {
  padding: 3rem clamp(1.5rem, 5vw, 4rem);
}
.eyebrow {
  letter-spacing: 0.28em;
  text-transform: uppercase;
  font-size: 0.85rem;
  color: #a8641c;
}
.lede {
  max-width: 50ch;
  line-height: 1.7;
}
main {
  padding: 2rem clamp(1rem, 4vw, 3rem);
}
</style>
