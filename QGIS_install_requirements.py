import importlib
import subprocess
import sys

# ✅ Cleaned list of requirements
REQUIREMENTS = {
    "affine": "affine==2.4.0",
    "attrs": "attrs==25.3.0",
    "certifi": "certifi==2025.8.3",
    "charset_normalizer": "charset-normalizer==3.4.3",
    "click": "click==8.2.1",
    "click_plugins": "click-plugins==1.1.1.2",
    "cligj": "cligj==0.7.2",
    "geopandas": "geopandas==1.1.1",
    "idna": "idna==3.10",
    "lxml": "lxml==6.0.1",
    "numpy": "numpy==2.2.6",
    "cv2": "opencv-python==4.12.0.88",
    "owslib": "OWSLib==0.34.1",
    "packaging": "packaging==25.0",
    "pandas": "pandas==2.3.2",
    "platformdirs": "platformdirs==4.4.0",
    "pyogrio": "pyogrio==0.11.1",
    "pyparsing": "pyparsing==3.2.3",
    "pyproj": "pyproj==3.7.2",
    "dateutil": "python-dateutil==2.9.0.post0",
    "pytz": "pytz==2025.2",
    "rasterio": "rasterio==1.4.3",
    "requests": "requests==2.32.5",
    "shapely": "shapely==2.1.1",
    "six": "six==1.17.0",
    "tzdata": "tzdata==2025.2",
    "urllib3": "urllib3==2.5.0",
}

def install_package(pkg_spec):
    """Install a package via pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_spec])
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {pkg_spec}: {e}")

def check_and_install():
    """Check each requirement and install if missing"""
    for module_name, pkg_spec in REQUIREMENTS.items():
        try:
            importlib.import_module(module_name)
            print(f"✅ {pkg_spec} already installed")
        except ImportError:
            print(f"📦 Installing missing package: {pkg_spec}")
            install_package(pkg_spec)

if __name__ == "__main__":
    print("🔍 Checking and installing required dependencies...")
    check_and_install()
    print("🎉 All dependencies are installed!")