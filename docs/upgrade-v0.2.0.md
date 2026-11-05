# Uploading the v0.2.0 copilot update

1. Extract the update ZIP. Upload its **contents** into the existing repository root,
   preserving `fleet`, `tests`, `docs` and `screenshots` folders. Replace matching files.
   Do not create a second repository or nest the entire extracted folder in the repo.
2. Commit as `Add local Llama fleet analytics copilot`.
3. Wait for the existing CI workflow to pass.
4. Start the app locally following `docs/copilot.md`. Verify the LOCAL LLAMA badge
   after pulling the model; FALLBACK means it is not using Llama for that response.
5. Run **Actions → Release and publish package → Run workflow → main** once.
   The project version is now 0.2.0, so this creates **v0.2.0** without replacing v0.1.0.

The update ZIP does not replace your workflow files: it preserves the working
container health-check fix already committed on GitHub. It does not publish changes
automatically. All existing synthetic data and serving snapshots can be reused.
The new chat UI runs locally with the backend; uploading files to GitHub does not
host a running chatbot. Optional topics: `ollama`, `llama`, `conversational-analytics`.
