/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Official institution logo, e.g. /brand/giu-logo.png. Optional. */
  readonly VITE_INSTITUTION_LOGO?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
