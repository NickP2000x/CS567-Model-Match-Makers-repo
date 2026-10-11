export function ServerUnavailable({ serverUrl, detail }: { serverUrl: string; detail: string }) {
  return (
    <main>
      <h1>Model Matchmakers</h1>
      <p role="alert" className="error-message">Could not start a study session with the server at {serverUrl}.</p>
      <p>{detail}</p>
      {import.meta.env.DEV && (
        <p className="field-help">
          Development: start the backend with DEV_CONTROLS=true, or unset VITE_API_BASE_URL to use the in-memory mock.
        </p>
      )}
      <button type="button" onClick={() => window.location.reload()}>Try again</button>
    </main>
  );
}
