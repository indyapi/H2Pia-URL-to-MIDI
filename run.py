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

def launch():
    """Launches the main application using the virtual environment."""
    base_dir = Path(__file__).parent.absolute()
    venv_python = base_dir / "venv" / "Scripts" / "python.exe"
    main_script = base_dir / "src" / "main.py"

    if not venv_python.exists():
        print("Error: Virtual environment python not found.")
        return

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
