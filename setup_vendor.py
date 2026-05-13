import os
import sys
import shutil
import zipfile
import urllib.request
import json
from pathlib import Path

def get_latest_scrcpy_url():
    api_url = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
    try:
        with urllib.request.urlopen(api_url) as response:
            data = json.loads(response.read().decode())
            for asset in data['assets']:
                if asset['name'].startswith('scrcpy-win64-v') and asset['name'].endswith('.zip'):
                    return asset['browser_download_url'], asset['name']
    except Exception as e:
        print(f"Error fetching latest scrcpy release: {e}")
    return None, None

def setup_scrcpy_windows(target_dir):
    vendor_dir = Path(target_dir) / "vendor"
    scrcpy_exe = vendor_dir / "scrcpy.exe"
    
    if scrcpy_exe.exists():
        print("scrcpy.exe already exists in vendor/.")
        return

    print("scrcpy.exe not found. Downloading latest version for Windows...")
    url, filename = get_latest_scrcpy_url()
    if not url:
        print("Could not find download URL for scrcpy Windows.")
        return

    temp_zip = vendor_dir / filename
    vendor_dir.mkdir(parents=True, exist_ok=True)

    try:
        print(f"Downloading {filename}...")
        urllib.request.urlretrieve(url, temp_zip)
        
        print("Extracting...")
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            # We want to extract the contents of the internal folder (e.g., scrcpy-win64-v2.4) 
            # directly into the vendor directory
            for member in zip_ref.namelist():
                filename_in_zip = os.path.basename(member)
                if not filename_in_zip:
                    continue
                
                # Copy file to vendor/
                source = zip_ref.open(member)
                target_path = vendor_dir / filename_in_zip
                with open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)
                source.close()

        print("scrcpy setup complete.")
    except Exception as e:
        print(f"Error during scrcpy setup: {e}")
    finally:
        if temp_zip.exists():
            os.remove(temp_zip)

if __name__ == "__main__":
    project_root = Path(__file__).parent
    if os.name == 'nt':
        setup_scrcpy_windows(project_root)
    else:
        print("Not on Windows, skipping scrcpy download.")
