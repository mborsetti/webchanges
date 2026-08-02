if __name__ == '__main__':
    import sys
    from pathlib import Path

    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    from webchanges.cli import main

    main()
