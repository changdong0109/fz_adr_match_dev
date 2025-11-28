from .fz_adr_match import FzAdrMatchPlugin

def classFactory(iface):
    """Entry point for QGIS."""
    return FzAdrMatchPlugin(iface)