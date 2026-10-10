/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Backend origin, for example http://127.0.0.1:8000. Unset: the in-memory mock is used.
  readonly VITE_API_BASE_URL?: string;
}
