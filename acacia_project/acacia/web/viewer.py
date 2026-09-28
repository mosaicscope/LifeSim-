"""Opens the ACACIA world renderer in a native window (pywebview -> Edge
WebView2 on Windows). Launched by the app as a separate process."""
import sys
import webview

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:47833/"
webview.create_window("ACACIA — World", url, width=1600, height=900, background_color="#0c0e13")
webview.start()
