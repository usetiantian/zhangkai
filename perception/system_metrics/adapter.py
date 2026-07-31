"""Read-only observations of the local runtime environment."""
import platform,shutil,sys
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True)
class SystemSnapshot:
 platform:str;python_version:str;disk_total:int;disk_free:int
class SystemMetricsAdapter:
 def observe(self,path:Path)->SystemSnapshot:
  usage=shutil.disk_usage(path)
  return SystemSnapshot(platform.platform(),sys.version.split()[0],usage.total,usage.free)
