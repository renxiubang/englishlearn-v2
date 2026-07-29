/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  // 管理端与 Element Plus 共存：关闭 preflight 避免覆盖组件库基础样式
  corePlugins: { preflight: false },
  theme: {
    extend: {},
  },
  plugins: [],
}
