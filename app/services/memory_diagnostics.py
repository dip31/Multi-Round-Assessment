"""Lightweight process RSS diagnostics for temporary production investigation."""

import logging
import os
import ctypes

try:
    import resource
except ImportError:  # pragma: no cover - resource is available on Render/Linux
    resource = None

logger = logging.getLogger("memory_diagnostics")


def log_memory(stage: str) -> None:
    """Log current process RSS in MB without adding a profiling dependency."""
    if resource is not None and os.name == "posix":
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports ru_maxrss in KiB (Render runs Linux).
        rss_mb = usage / 1024
    elif os.name == "nt":
        class _MemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("page_fault_count", ctypes.c_ulong),
                ("peak_working_set_size", ctypes.c_size_t),
                ("working_set_size", ctypes.c_size_t),
                ("quota_peak_paged_pool_usage", ctypes.c_size_t),
                ("quota_paged_pool_usage", ctypes.c_size_t),
                ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
                ("quota_non_paged_pool_usage", ctypes.c_size_t),
                ("pagefile_usage", ctypes.c_size_t),
                ("peak_pagefile_usage", ctypes.c_size_t),
            ]

        counters = _MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_process_memory_info.restype = ctypes.c_int
        get_process_memory_info.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_MemoryCounters),
            ctypes.c_ulong,
        ]
        if not get_process_memory_info(
            process,
            ctypes.byref(counters),
            counters.cb,
        ):
            logger.info("[MEMORY] %s: rss=unavailable on this platform", stage)
            return
        rss_mb = counters.working_set_size / (1024 * 1024)
    else:
        logger.info("[MEMORY] %s: rss=unavailable on this platform", stage)
        return
    logger.info("[MEMORY] %s: rss=%.1f MB", stage, rss_mb)
