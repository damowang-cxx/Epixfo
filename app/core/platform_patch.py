import platform


def patch_platform_wmi() -> None:
    platform.machine = lambda: "AMD64"
    platform.system = lambda: "Windows"
