from pkg_resources import get_distribution, DistributionNotFound
import os.path

try:
    _dist = get_distribution('dev_machine')
    # Normalize case for Windows systems
    dist_loc = os.path.normcase(_dist.location)
    here = os.path.normcase(__file__)
    if not here.startswith(os.path.join(dist_loc, 'dev_machine')):
        # not installed, but there is another version that *is*
        raise DistributionNotFound
except DistributionNotFound:
    __version__ = 'Package version not available'
else:
    __version__ = _dist.version


# banner = f"""
#
#  ▄▄▄▄▄▄▄▄▄▄▄  ▄    ▄  ▄▄▄▄▄▄▄▄▄▄▄
# ▐░░░░░░░░░░░▌▐░▌  ▐░▌▐░░░░░░░░░░░▌
# ▐░█▀▀▀▀▀▀▀▀▀ ▐░▌ ▐░▌  ▀▀▀▀█░█▀▀▀▀
# ▐░▌          ▐░▌▐░▌       ▐░▌
# ▐░█▄▄▄▄▄▄▄▄▄ ▐░▌░▌        ▐░▌
# ▐░░░░░░░░░░░▌▐░░▌         ▐░▌
# ▐░█▀▀▀▀▀▀▀▀▀ ▐░▌░▌        ▐░▌
# ▐░▌          ▐░▌▐░▌       ▐░▌
# ▐░█▄▄▄▄▄▄▄▄▄ ▐░▌ ▐░▌  ▄▄▄▄█░█▄▄▄▄
# ▐░░░░░░░░░░░▌▐░▌  ▐░▌▐░░░░░░░░░░░▌
#  ▀▀▀▀▀▀▀▀▀▀▀  ▀    ▀  ▀▀▀▀▀▀▀▀▀▀▀
#
# EKI Dev Machine and Modeling Environment v{__version__}
# """

# banner = f"""
# ░        ░░  ░░░░  ░░        ░
# ▒  ▒▒▒▒▒▒▒▒  ▒▒▒  ▒▒▒▒▒▒  ▒▒▒▒
# ▓      ▓▓▓▓     ▓▓▓▓▓▓▓▓  ▓▓▓▓
# █  ████████  ███  ██████  ████
# █        ██  ████  ██        █
#
# ░       ░░░        ░░  ░░░░  ░░░░░░░░  ░░░░  ░░░      ░░░░      ░░░  ░░░░  ░░        ░░   ░░░  ░░        ░
# ▒  ▒▒▒▒  ▒▒  ▒▒▒▒▒▒▒▒  ▒▒▒▒  ▒▒▒▒▒▒▒▒   ▒▒   ▒▒  ▒▒▒▒  ▒▒  ▒▒▒▒  ▒▒  ▒▒▒▒  ▒▒▒▒▒  ▒▒▒▒▒    ▒▒  ▒▒  ▒▒▒▒▒▒▒
# ▓  ▓▓▓▓  ▓▓      ▓▓▓▓▓  ▓▓  ▓▓▓▓▓▓▓▓▓        ▓▓  ▓▓▓▓  ▓▓  ▓▓▓▓▓▓▓▓        ▓▓▓▓▓  ▓▓▓▓▓  ▓  ▓  ▓▓      ▓▓▓
# █  ████  ██  ██████████    ██████████  █  █  ██        ██  ████  ██  ████  █████  █████  ██    ██  ███████
# █       ███        █████  ███████████  ████  ██  ████  ███      ███  ████  ██        ██  ███   ██        █
#
# EKI Dev Machine and Modeling Environment v{__version__}
# """

banner = f"""
 ____|  __ \     \      \  |     \      \  |  ____|
 __|    |   |   _ \    |\/ |    _ \    |\/ |  __|  
 |      |   |  ___ \   |   |   ___ \   |   |  |    
_____| ____/ _/    _\ _|  _| _/    _\ _|  _| _____| 

EKI Dev Machine and Modeling Environment (EDAMAME) v{__version__}                                                                              
"""