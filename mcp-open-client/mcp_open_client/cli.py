#!/usr/bin/env python3
"""
CLI entry point for mcp-open-client
"""

def main():
    """Main CLI entry point"""
    import subprocess
    import sys
    import os
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Run the main module
    subprocess.run([sys.executable, "-m", "mcp_open_client.main"], cwd=os.path.dirname(script_dir))

if __name__ == "__main__":
    main()