import os
import sys
import subprocess
import venv
from pathlib import Path

def setup_environment():
    """Ensures the virtual environment exists and is up to date."""
    base_dir = Path(__file__).parent.absolute()
    venv_dir = base_dir / "venv"
    venv_python = venv_dir / "Scripts" / "python.exe"

    print("--- Environment Check ---")
    
    # 1. Check if venv exists
    if not venv_dir.exists():
        print(f"Creating virtual environment in {venv_dir}...")
        venv.create(venv_dir, with_pip=True)
    
    # 2. Check if we need to install/update requirements
    req_file = base_dir / "requirement.txt"
    if req_file.exists():
        print("Checking/Installing dependencies (this may take a moment)...")
        try:
            subprocess.check_call([
                str(venv_python), "-m", "pip", "install", "-r", str(req_file), "--quiet"
            ])
        except subprocess.CalledProcessError as e:
            print(f"Error installing dependencies: {e}")
            return False
            
    return True

def setup_ffmpeg():
    """Checks for ffmpeg/ffprobe and adds them to PATH if found in common locations."""
    import shutil
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True
    
    print("ffmpeg/ffprobe not in PATH, searching in common locations...")
    
    # Common winget location
    winget_base = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"))
    if winget_base.exists():
        for package_dir in winget_base.glob("Gyan.FFmpeg*"):
            # It might be directly in the package dir or in a subfolder like ffmpeg-*-full_build\bin
            for bin_dir in package_dir.rglob("bin"):
                if (bin_dir / "ffmpeg.exe").exists():
                    print(f"Found ffmpeg in {bin_dir}, adding to PATH.")
                    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
                    return True
    
    return False

def launch():
    """Launches the main application using the virtual environment."""
    base_dir = Path(__file__).parent.absolute()
    venv_python = base_dir / "venv" / "Scripts" / "python.exe"
    main_script = base_dir / "src" / "main.py"

    if not venv_python.exists():
        print("Error: Virtual environment python not found.")
        return

    setup_ffmpeg()

    print("--- Launching U2M ---")
    # Execute the main script as a module (-m src.main) from the root directory
    try:
        subprocess.run([str(venv_python), "-m", "src.main"], check=True)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Application exited with error: {e}")

if __name__ == "__main__":
    # If we are already running in the venv, just start the app
    # Otherwise, set up and then use the venv to launch
    is_venv = sys.prefix != sys.base_prefix
    
    if not is_venv:
        if setup_environment():
            launch()
    else:
        # We are already in a venv (maybe manually activated)
        # Just import and run to avoid nested subprocesses if possible, 
        # but launching via subprocess ensures the environment is fresh.
        launch()
