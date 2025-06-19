import sys
import importlib

print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"sys.path: {sys.path}")

try:
    import pygit2
    print("Successfully imported pygit2")
    print(f"pygit2 version: {pygit2.__version__}")
    print(f"pygit2 path: {pygit2.__file__}")
except ImportError as e:
    print(f"Failed to import pygit2: {e}")
    # Let's try to see if it's findable by importlib
    spec = importlib.util.find_spec("pygit2")
    if spec:
        print("pygit2 spec found by importlib.util.find_spec")
        print(f"pygit2 spec origin: {spec.origin}")
    else:
        print("pygit2 spec NOT found by importlib.util.find_spec")

# Try to import from conftest to see if there is an issue there
try:
    from .conftest import CommitFactory, diff_summary # Use relative import for conftest
    print("Successfully imported from conftest")
except ImportError as e:
    print(f"Failed to import from conftest: {e}")

# Exit with a non-zero code if pygit2 wasn't imported, to make it clear in pytest output
if "pygit2" not in sys.modules:
    sys.exit(1)
else:
    sys.exit(0)
