import sys
from pathlib import Path

parent_dir = Path(__file__).parent.parent
sys.path.insert(1, str(parent_dir))

if __name__ == '__main__':
    from cli import main

    main()
