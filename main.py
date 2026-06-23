"""程序入口。"""

from map_tool.app import MapToolApp


def main() -> None:
    """启动地图工具。"""
    app = MapToolApp()
    app.run()


if __name__ == "__main__":
    main()
