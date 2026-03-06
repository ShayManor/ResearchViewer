import shutil
import time
from pathlib import Path
from datasets import load_dataset

while True:
    # Force redownload (bypass cache)
    dataset = load_dataset(
        "ShayManor/Labeled-arXiv",
        "authors",
        download_mode='force_redownload'
    )
    print(f"Loaded {len(dataset)} examples")

    # Delete the cache
    cache_dir = Path.home() / ".cache" / "huggingface" / "datasets" / "ShayManor___labeled-ar_xiv"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print("Cache deleted")
    time.sleep(60*5.5)
