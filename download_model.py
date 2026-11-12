from huggingface_hub import snapshot_download


MODELS = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
}


for name, repo_id in MODELS.items():
    print(f"Downloading {repo_id}...")
    snapshot_download(
        repo_id=repo_id,
        local_dir=f"models/faster-whisper-{name}",
    )
    print(f"Saved models/faster-whisper-{name}")
