import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Deployed by uploading dist/ straight into an object-storage bucket at
  // an arbitrary path (not a domain root, not a fixed subpath) — relative
  // asset URLs let the built index.html work from wherever it lands.
  base: './',
})
