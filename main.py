"""
Cascadia Digital Board Game
Main entry point - launches the GUI application
"""
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cascadia.gui.app import CascadiaApp


def main():
    """Launch the Cascadia application."""
    app = CascadiaApp()
    app.run()


if __name__ == "__main__":
    main()
