# Industrial inference weights

Install the approved `ppe_unified_best.pt` artifact in this directory. It is the
only checkpoint the application accepts. Weights are deployment artifacts, not
substituted or renamed checkpoints. No automatic download or fallback exists.

Run `python -m app.model_check` before starting the pilot. The command validates
the file, industrial class vocabulary and optional SHA-256 pin. The service
fails closed if the artifact is missing, empty, incompatible or corrupt.
