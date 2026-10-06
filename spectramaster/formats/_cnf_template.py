"""Genie-2000 CAM (CNF) template used by the ci_cnf writer.

Generated once by Canberra Genie-2000 FILECNVT (/ORTEC) from a synthetic 1024-channel,
zero-count CHN written by SpectraMaster (no third-party spectrum data).  The writer
patches channel count, block offsets, counts, times, calibration and text fields.
Layout notes are in specutils_bridge._cnf_write_genie.
"""
import base64
import zlib

TEMPLATE_CHANNELS = 1024

_DATA = (
    "eNrt3U9IFFEcwPHfjCNt0raLIZF0WMFDQVp0qaRox3X9U9Nqu6Mg2amWWgKRsk6Bnjx0MToEhkSHkOjoxU4hHcWgLkGdugfS"
    "pa723rzZVkHF1dx0/X7g7c7b/c2bN7Nvd97OvN0RR0QciajbNyrJGTkpO6k2YYlYUq8mI2Z5T9/V6xrIxeB5J4z7ZOlJFWvi"
    "69RDjWF8JCryxMSroNq5mi/2MXnrHFT5H5EaE6/Lbg7jjx8WeW+F5Yssjy2P6dsgE3FMvAqRUyb+xO9Doutn4uMybelYW9Sj"
    "smjFTXy7yrSF5X+Li1wpxn+V5tOl8v3TVqn+j8P4Z6r+52Xt+tTZJj6hpifC+IVosC5mfe1YIoiddZpUPhuLmnhbZWbC+KXo"
    "iu3ZIEkplT8iAAD83R/XlrE/BgAAAAAAwN5ijv9s+vxKYbj11t3hls5UZsC/0Zv106mbiZW2VAdnK7OEh6Mqd0iqr9cb3PIq"
    "VgmnOldLNaLG6QfnXsp44c6yVrzfb6/veHJ1vjtl7g+s87x2Lz+w/Y+Abdb516XJD7tzi+auZ329VTh0vlO68v+n3QF7Xrnj"
    "ZR6mCqs+7IMdwrjEk67qSqpRMXVBhyzYcarc89Tau4wiPZdOr1SyxtVNkNaY4YhK35Om/5HJjyYSOT/dZ5bu9vu9Hfn7hUf5"
    "22X1e93S4vVSpy6/mNLJXhGje8WfLxydK8bOJ8N7d3XfIVhfPfNG67qaLkpHzyd38MVVA5Na3NcjWXdoskqaq24oUkzrsGXj"
    "RodK9yKB3cxLflwMPllUu/3Zvq/ab7njXyv6nRwAAAAA8M+U+3vG6twKqbahrnSmJ3326lDKvdbZ46VzQzm/w+tpb8147Ylt"
    "o52B90Pl3g8r6+97pv5uxvUGcz25Vr/P4/1cGd1ptyOdLW23JjYJAAAAAAAAAAAAAAAAAAAAAAAAAAAAsIFyr0+92345rf+q"
    "sX+4MMqvswEAADbHNtf/0n2mibD/txANrgVhrv9lxxJB32/W0f/dko1tvuSK/GdOcnuzd/S7Hj1GAAAAAAAAAAAAAMDeFzXj"
    "P201OSPm/P+SOv/vFMd/NqhT7KXxnyPSm/XTKcZaVo0/BuL+kQ=="
)


def template_bytes() -> bytes:
    return zlib.decompress(base64.b64decode("".join(_DATA)))
