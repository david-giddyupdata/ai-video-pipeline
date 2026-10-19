// Remotion's webpack config resolves an imported .svg to a URL string that can be
// dropped straight into <img src=...>. Declare the module so TypeScript agrees.
declare module '*.svg' {
  const src: string;
  export default src;
}

// R148: the overlays import their bundled OFL fonts (src/overlays/fonts/); webpack turns each into a URL.
declare module '*.ttf' {
  const src: string;
  export default src;
}
