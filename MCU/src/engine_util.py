"""
Download Minecraft Simulator Engine
This script is used during Docker build to pre-download the engine.
"""
import os
from minestudio.utils import get_mine_studio_dir


def download_engine():
    import huggingface_hub, zipfile
    local_dir = get_mine_studio_dir()
    print(f"Downloading simulator engine to {local_dir}")
    huggingface_hub.hf_hub_download(repo_id='CraftJarvis/SimulatorEngine', filename='engine.zip', local_dir=local_dir)
    with zipfile.ZipFile(os.path.join(local_dir, 'engine.zip'), 'r') as zip_ref:
        zip_ref.extractall(local_dir)
    os.remove(os.path.join(local_dir, 'engine.zip'))


def check_engine():
    if not os.path.exists(os.path.join(get_mine_studio_dir(), "engine", "build", "libs", "mcprec-6.13.jar")):
        print("Simulator engine not found, downloading...")
        download_engine()
        print("Download complete.")
    else:
        print("Simulator engine already exists.")
    

if __name__ == "__main__":
    print("Checking Minecraft Simulator Engine...")
    check_engine()


